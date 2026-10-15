"""Cyberfield WhatsApp Assistant — FastAPI app (API + webhook + built frontend)."""
import json, os
from pathlib import Path

# Load KEY=VALUE pairs from the project-root .env file (does not override real env vars)
_env = Path(__file__).resolve().parents[2] / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8-sig").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from . import db, engine, llm, seed, whatsapp

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(_app):
    seed.seed()
    yield


app = FastAPI(title="Cyberfield WhatsApp Assistant", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class SimIn(BaseModel):
    phone: str
    name: str | None = None
    text: str


class ReplyIn(BaseModel):
    text: str


class BroadcastIn(BaseModel):
    title: str
    body: str
    audience: str = "all"


class StatusIn(BaseModel):
    status: str


@app.get("/api/health")
def health():
    return {"ok": True, "llm": "live" if llm.enabled() else "mock", "whatsapp": "live" if whatsapp.live() else "simulated",
            "business": seed.BUSINESS}


# ---------- WhatsApp Cloud API webhook ----------
@app.get("/webhook")
def verify(mode: str = Query(None, alias="hub.mode"), token: str = Query(None, alias="hub.verify_token"),
           challenge: str = Query(None, alias="hub.challenge")):
    if mode == "subscribe" and token == os.environ.get("WHATSAPP_VERIFY_TOKEN", "cyberfield-demo-token"):
        return PlainTextResponse(challenge or "")
    raise HTTPException(403, "verification failed")


@app.post("/webhook")
async def inbound(req: Request):
    payload = await req.json()
    results = []
    for phone, name, text in whatsapp.parse_inbound(payload):
        r = engine.handle_message(phone, name, text)
        if r["reply"]:
            r["delivery"] = whatsapp.send_text(phone, r["reply"])
        results.append(r)
    return {"processed": len(results), "results": results}


# ---------- simulator ----------
@app.post("/api/simulate")
def simulate(m: SimIn):
    return engine.handle_message(m.phone, m.name, m.text)


@app.post("/api/reset")
def reset():
    seed.seed(force=True)
    return {"ok": True}


# ---------- dashboard ----------
@app.get("/api/stats")
def stats():
    c = lambda sql: db.q(sql, one=True)["n"]
    return {"conversations": c("SELECT COUNT(*) n FROM conversations"), "orders": c("SELECT COUNT(*) n FROM orders"),
            "revenue": c("SELECT COALESCE(SUM(total),0) n FROM orders"), "bookings": c("SELECT COUNT(*) n FROM bookings"),
            "leads": c("SELECT COUNT(*) n FROM leads"), "handoffs": c("SELECT COUNT(*) n FROM conversations WHERE needs_human=1"),
            "pending_broadcasts": c("SELECT COUNT(*) n FROM broadcasts WHERE status='pending_approval'")}


@app.get("/api/conversations")
def conversations():
    return db.q("""SELECT c.id,c.phone,c.name,c.lang,c.needs_human,c.handoff_reason,c.updated_at,
        (SELECT text FROM messages m WHERE m.conversation_id=c.id ORDER BY m.id DESC LIMIT 1) last_text,
        (SELECT COUNT(*) FROM messages m WHERE m.conversation_id=c.id) n_messages
        FROM conversations c ORDER BY c.updated_at DESC, c.id DESC""")


@app.get("/api/conversations/{cid}/messages")
def messages(cid: int):
    return db.q("SELECT * FROM messages WHERE conversation_id=? ORDER BY id", (cid,))


@app.post("/api/conversations/{cid}/reply")
def owner_reply(cid: int, r: ReplyIn):
    c = db.q("SELECT * FROM conversations WHERE id=?", (cid,), one=True)
    if not c:
        raise HTTPException(404)
    engine.log(cid, "out", "owner", r.text, "owner_reply", c["lang"])
    return {"delivery": whatsapp.send_text(c["phone"], r.text)}


@app.post("/api/conversations/{cid}/resolve")
def resolve(cid: int):
    db.x("UPDATE conversations SET needs_human=0, handoff_reason=NULL WHERE id=?", (cid,))
    return {"ok": True}


def _with_customer(table):
    return db.q(f"SELECT t.*, c.name customer, c.phone FROM {table} t LEFT JOIN conversations c ON c.id=t.conversation_id ORDER BY t.id DESC")


@app.get("/api/orders")
def orders():
    rows = _with_customer("orders")
    for r in rows:
        r["items"] = json.loads(r["items"])
    return rows


@app.patch("/api/orders/{oid}")
def order_status(oid: int, s: StatusIn):
    if s.status not in ("new", "preparing", "out_for_delivery", "completed", "cancelled"):
        raise HTTPException(400, "bad status")
    db.x("UPDATE orders SET status=? WHERE id=?", (s.status, oid))
    return {"ok": True}


@app.get("/api/bookings")
def bookings():
    return db.q("""SELECT b.*, s.starts_at, c.name customer, c.phone FROM bookings b JOIN slots s ON s.id=b.slot_id
                   LEFT JOIN conversations c ON c.id=b.conversation_id ORDER BY s.starts_at""")


@app.get("/api/leads")
def leads():
    return _with_customer("leads")


@app.get("/api/handoffs")
def handoffs():
    return [c for c in conversations() if c["needs_human"]]


@app.get("/api/knowledge")
def knowledge():
    return {"faq": db.q("SELECT id,topic,answer_en,answer_hi,answer_ta FROM faq"), "menu": engine.menu_items(),
            "slots": db.q("SELECT * FROM slots ORDER BY starts_at")}


# ---------- broadcasts: always require human approval ----------
@app.get("/api/broadcasts")
def broadcasts():
    return db.q("SELECT * FROM broadcasts ORDER BY id DESC")


@app.post("/api/broadcasts")
def create_broadcast(b: BroadcastIn):
    bid = db.x("INSERT INTO broadcasts(title,body,audience) VALUES(?,?,?)", (b.title, b.body, b.audience))
    return db.q("SELECT * FROM broadcasts WHERE id=?", (bid,), one=True)


@app.post("/api/broadcasts/{bid}/approve")
def approve_broadcast(bid: int, approver: str = "owner"):
    b = db.q("SELECT * FROM broadcasts WHERE id=?", (bid,), one=True)
    if not b:
        raise HTTPException(404)
    if b["status"] != "pending_approval":
        raise HTTPException(409, "broadcast is not awaiting approval")
    phones = [c["phone"] for c in db.q("SELECT phone FROM conversations")]
    for p in phones:
        whatsapp.send_text(p, b["body"])
    db.x("UPDATE broadcasts SET status='sent', approved_by=?, recipients=?, sent_at=CURRENT_TIMESTAMP WHERE id=?",
         (approver, len(phones), bid))
    return db.q("SELECT * FROM broadcasts WHERE id=?", (bid,), one=True)


@app.post("/api/broadcasts/{bid}/reject")
def reject_broadcast(bid: int):
    db.x("UPDATE broadcasts SET status='rejected' WHERE id=? AND status='pending_approval'", (bid,))
    return db.q("SELECT * FROM broadcasts WHERE id=?", (bid,), one=True)


# ---------- serve built frontend ----------
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")
