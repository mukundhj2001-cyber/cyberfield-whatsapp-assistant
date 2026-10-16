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
            _v = _v.strip().strip('"').strip("'")
            if _v:  # blank lines in .env mean "not set"
                os.environ.setdefault(_k.strip(), _v)
import time
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from . import admin, auth, db, engine, llm, media, payments, seed, templates, tenants, whatsapp
from .deps import current_biz, deliver
from .logs import log_event, mask_phone, setup as setup_logging

setup_logging()

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(_app):
    seed.seed()
    log_event("startup", whatsapp="live" if whatsapp.live() else "simulated", llm="live" if llm.enabled() else "mock",
              auth="demo" if auth.demo_mode() else "configured", signature_check=bool(os.environ.get("WHATSAPP_APP_SECRET")))
    auth._credentials()  # logs the demo-login warning at startup if needed
    yield


app = FastAPI(title="Cyberfield WhatsApp Assistant", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# API routes anyone may call. Everything else under /api needs a dashboard session.
PUBLIC_API = {"/api/health", "/api/simulate", "/api/auth/login", "/api/auth/logout", "/api/auth/me"}
PUBLIC_PREFIXES = ("/api/public/", "/api/payments/")


@app.middleware("http")
async def guard(request: Request, call_next):
    t0 = time.perf_counter()
    path = request.url.path
    if path.startswith("/api/") and path not in PUBLIC_API and not path.startswith(PUBLIC_PREFIXES) and request.method != "OPTIONS":
        if not auth.check(request.cookies.get(auth.COOKIE)):
            return JSONResponse({"detail": "login required"}, status_code=401)
    resp = await call_next(request)
    if path.startswith(("/api/", "/webhook")):
        log_event("http", method=request.method, path=path, status=resp.status_code, ms=round((time.perf_counter() - t0) * 1000, 1))
    return resp


class SimIn(BaseModel):
    phone: str
    name: str | None = None
    text: str = ""
    type: str = "text"            # text | audio | image  (audio/image are mocked: text is the transcript / photo contents)
    action: str | None = None     # id of a tapped button or list row


class ReplyIn(BaseModel):
    text: str


class BroadcastIn(BaseModel):
    title: str
    body: str
    audience: str = "all"
    template_id: int | None = None


class StatusIn(BaseModel):
    status: str


class LoginIn(BaseModel):
    username: str
    password: str


# ---------- auth ----------
@app.post("/api/auth/login")
def login(body: LoginIn, response: Response, request: Request):
    if not auth.verify(body.username, body.password):
        log_event("login_failed", "warning", user=body.username[:40])
        raise HTTPException(401, "invalid username or password")
    secure = (os.environ.get("COOKIE_SECURE") or "").lower() in ("1", "true", "yes") or request.url.scheme == "https"
    response.set_cookie(auth.COOKIE, auth.issue(body.username), max_age=auth.MAX_AGE, httponly=True, samesite="lax", secure=secure)
    log_event("login_ok", user=body.username[:40])
    return {"ok": True, "user": body.username, "demo_credentials": auth.demo_mode()}


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(auth.COOKIE)
    return {"ok": True}


@app.get("/api/auth/me")
def me(request: Request):
    return {"user": auth.check(request.cookies.get(auth.COOKIE)), "demo_credentials": auth.demo_mode()}


@app.get("/api/health")
def health():
    return {"ok": True, "llm": "live" if llm.enabled() else "mock",
            "voice": "live" if llm.stt_enabled() else "mock", "whatsapp": "live" if whatsapp.live() else "simulated",
            "business": {"name": (tenants.default() or {}).get("name"), "type": (tenants.default() or {}).get("tagline")}, "auth": "demo" if auth.demo_mode() else "configured",
            "payments": payments.mode(), "businesses": len(tenants.all_())}


# ---------- WhatsApp Cloud API webhook ----------
@app.get("/webhook")
def verify(mode: str = Query(None, alias="hub.mode"), token: str = Query(None, alias="hub.verify_token"),
           challenge: str = Query(None, alias="hub.challenge")):
    if mode == "subscribe" and token == (os.environ.get("WHATSAPP_VERIFY_TOKEN") or "cyberfield-demo-token"):
        return PlainTextResponse(challenge or "")
    raise HTTPException(403, "verification failed")


@app.post("/webhook")
async def inbound(req: Request, background: BackgroundTasks):
    raw = await req.body()
    if not whatsapp.verify_signature(raw, req.headers.get("x-hub-signature-256")):
        log_event("webhook_signature_invalid", "warning")
        raise HTTPException(401, "invalid signature")
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        raise HTTPException(400, "invalid JSON")
    statuses = whatsapp.record_statuses(payload)
    results, duplicates = [], 0
    queued = 0
    for m in whatsapp.parse_inbound(payload):
        if not whatsapp.claim_message(m["wa_id"]):
            duplicates += 1
            log_event("webhook_duplicate_skipped", wa_id=m["wa_id"])
            continue
        log_event("webhook_message", wa_id=m["wa_id"], type=m["type"], frm=mask_phone(m["phone"]))
        m["biz"] = tenants.by_phone_number_id(m.get("phone_number_id"))
        if m["type"] in ("audio", "image") and tenants.creds(m["biz"]):
            # downloading + transcribing/vision can take seconds; answer Meta now, reply when done
            background.add_task(process_inbound, m)
            queued += 1
            continue
        r = process_inbound(m)
        if r:
            results.append(r)
    return {"processed": len(results), "queued": queued, "duplicates": duplicates, "statuses": statuses, "results": results}


def process_inbound(m: dict) -> dict | None:
    biz = m.get("biz") or tenants.by_phone_number_id(m.get("phone_number_id"))
    try:
        r = media.handle({**m, "biz": biz}) if m["type"] in ("audio", "image") else \
            engine.handle_message(m["phone"], m["name"], m["text"], action=m.get("action"), biz=biz)
    except Exception:
        log_event("engine_error", "error", wa_id=m["wa_id"], exc_info=True)
        return None  # still return 200 so Meta doesn't retry a message that crashes us
    if r["reply"]:
        r["delivery"] = deliver(biz, m["phone"], r["reply"], r.get("interactive"))
    return r


@app.get("/api/outbox")
def outbox(limit: int = 100):
    return db.q("SELECT * FROM outbox ORDER BY id DESC LIMIT ?", (limit,))


# ---------- simulator ----------
@app.get("/api/public/businesses")
def public_businesses():
    return [tenants.public(b) for b in tenants.all_()]


@app.post("/api/simulate")
def simulate(m: SimIn, biz: dict = Depends(current_biz)):
    if m.type in ("audio", "image"):
        return media.handle({"phone": m.phone, "name": m.name, "type": m.type, "text": m.text, "mock": True, "biz": biz})
    return engine.handle_message(m.phone, m.name, m.text, action=m.action, biz=biz)


@app.post("/api/reset")
def reset():
    seed.seed(force=True)
    return {"ok": True}


# ---------- dashboard (everything scoped to the selected business) ----------
@app.get("/api/stats")
def stats(biz: dict = Depends(current_biz)):
    b = biz["id"]
    c = lambda sql: db.q(sql, (b,), one=True)["n"]
    return {"conversations": c("SELECT COUNT(*) n FROM conversations WHERE business_id=?"),
            "orders": c("SELECT COUNT(*) n FROM orders WHERE business_id=?"),
            "revenue": c("SELECT COALESCE(SUM(total),0) n FROM orders WHERE business_id=? AND status!='cancelled'"),
            "bookings": c("SELECT COUNT(*) n FROM bookings WHERE business_id=?"),
            "leads": c("SELECT COUNT(*) n FROM leads WHERE business_id=?"),
            "handoffs": c("SELECT COUNT(*) n FROM conversations WHERE business_id=? AND needs_human=1"),
            "pending_broadcasts": c("SELECT COUNT(*) n FROM broadcasts WHERE business_id=? AND status='pending_approval'")}


@app.get("/api/conversations")
def conversations(biz: dict = Depends(current_biz)):
    return db.q("""SELECT c.id,c.phone,c.name,c.lang,c.needs_human,c.handoff_reason,c.updated_at,
        (SELECT text FROM messages m WHERE m.conversation_id=c.id ORDER BY m.id DESC LIMIT 1) last_text,
        (SELECT COUNT(*) FROM messages m WHERE m.conversation_id=c.id) n_messages,
        (SELECT MAX(created_at) FROM messages m WHERE m.conversation_id=c.id AND m.direction='in') last_inbound_at
        FROM conversations c WHERE c.business_id=? ORDER BY c.updated_at DESC, c.id DESC""", (biz["id"],))


def _conv(cid, biz):
    c = db.q("SELECT * FROM conversations WHERE id=? AND business_id=?", (cid, biz["id"]), one=True)
    if not c:
        raise HTTPException(404)
    return c


@app.get("/api/conversations/{cid}/messages")
def messages(cid: int, biz: dict = Depends(current_biz)):
    _conv(cid, biz)
    return db.q("SELECT * FROM messages WHERE conversation_id=? ORDER BY id", (cid,))


@app.post("/api/conversations/{cid}/reply")
def owner_reply(cid: int, r: ReplyIn, biz: dict = Depends(current_biz)):
    c = _conv(cid, biz)
    if not templates.in_window(cid):
        raise HTTPException(409, "Outside WhatsApp's 24-hour window: send an approved template instead")
    engine.log(cid, "out", "owner", r.text, "owner_reply", c["lang"])
    return {"delivery": deliver(biz, c["phone"], r.text)}


@app.post("/api/conversations/{cid}/resolve")
def resolve(cid: int, biz: dict = Depends(current_biz)):
    _conv(cid, biz)
    db.x("UPDATE conversations SET needs_human=0, handoff_reason=NULL WHERE id=?", (cid,))
    return {"ok": True}


def _with_customer(table, bid):
    return db.q(f"SELECT t.*, c.name customer, c.phone FROM {table} t LEFT JOIN conversations c ON c.id=t.conversation_id "
                f"WHERE t.business_id=? ORDER BY t.id DESC", (bid,))


@app.get("/api/orders")
def orders(biz: dict = Depends(current_biz)):
    rows = _with_customer("orders", biz["id"])
    for r in rows:
        r["items"] = json.loads(r["items"])
    return rows


@app.patch("/api/orders/{oid}")
def order_status(oid: int, s: StatusIn, biz: dict = Depends(current_biz)):
    if s.status not in ("new", "preparing", "out_for_delivery", "completed", "cancelled"):
        raise HTTPException(400, "bad status")
    db.x("UPDATE orders SET status=? WHERE id=? AND business_id=?", (s.status, oid, biz["id"]))
    return {"ok": True}


@app.post("/api/orders/{oid}/paid")
def order_mark_paid(oid: int, biz: dict = Depends(current_biz)):
    """Owner confirms a UPI / cash payment by hand."""
    if not db.q("SELECT 1 FROM orders WHERE id=? AND business_id=?", (oid, biz["id"]), one=True):
        raise HTTPException(404)
    payments.mark_paid(oid, "manual", "manual")
    return db.q("SELECT * FROM orders WHERE id=?", (oid,), one=True)


@app.get("/api/bookings")
def bookings(biz: dict = Depends(current_biz)):
    return db.q("""SELECT b.*, s.starts_at, c.name customer, c.phone FROM bookings b JOIN slots s ON s.id=b.slot_id
                   LEFT JOIN conversations c ON c.id=b.conversation_id WHERE b.business_id=? ORDER BY s.starts_at""", (biz["id"],))


@app.post("/api/bookings/{bk}/remind")
def booking_remind(bk: int, biz: dict = Depends(current_biz)):
    b = db.q("""SELECT b.*, s.starts_at, c.name customer, c.phone FROM bookings b JOIN slots s ON s.id=b.slot_id
                JOIN conversations c ON c.id=b.conversation_id WHERE b.id=? AND b.business_id=?""", (bk, biz["id"]), one=True)
    if not b:
        raise HTTPException(404)
    when = engine.fmt_slot(b)
    params = [(b["customer"] or "there").split()[0], when, b["code"]]
    out = templates.send_smart(biz, b["conversation_id"], b["phone"], purpose="reminder", params=params,
                               text=f"⏰ Reminder: your booking at {biz['name']} is on *{when}*. Code: *{b['code']}*. Reply CANCEL if you can't make it.")
    if out["delivery"] == "skipped":
        raise HTTPException(409, "Customer is outside the 24-hour window and no approved reminder template is set up")
    db.x("UPDATE bookings SET reminded_at=CURRENT_TIMESTAMP WHERE id=?", (bk,))
    return out


@app.get("/api/leads")
def leads(biz: dict = Depends(current_biz)):
    return _with_customer("leads", biz["id"])


@app.get("/api/handoffs")
def handoffs(biz: dict = Depends(current_biz)):
    return [c for c in conversations(biz) if c["needs_human"]]


@app.get("/api/knowledge")
def knowledge(biz: dict = Depends(current_biz)):
    return {"faq": db.q("SELECT id,topic,answer_en,answer_hi,answer_ta FROM faq WHERE business_id=?", (biz["id"],)),
            "menu": engine.menu_items(biz["id"]), "slots": db.q("SELECT * FROM slots WHERE business_id=? ORDER BY starts_at", (biz["id"],))}


# ---------- broadcasts: always require human approval ----------
@app.get("/api/broadcasts")
def broadcasts(biz: dict = Depends(current_biz)):
    return db.q("SELECT * FROM broadcasts WHERE business_id=? ORDER BY id DESC", (biz["id"],))


@app.post("/api/broadcasts")
def create_broadcast(b: BroadcastIn, biz: dict = Depends(current_biz)):
    if b.template_id and not db.q("SELECT 1 FROM templates WHERE id=? AND business_id=?", (b.template_id, biz["id"]), one=True):
        raise HTTPException(400, "unknown template")
    bid = db.x("INSERT INTO broadcasts(business_id,title,body,audience,template_id) VALUES(?,?,?,?,?)",
               (biz["id"], b.title, b.body, b.audience, b.template_id))
    return db.q("SELECT * FROM broadcasts WHERE id=?", (bid,), one=True)


@app.post("/api/broadcasts/{bid}/approve")
def approve_broadcast(bid: int, approver: str = "owner", biz: dict = Depends(current_biz)):
    b = db.q("SELECT * FROM broadcasts WHERE id=? AND business_id=?", (bid, biz["id"]), one=True)
    if not b:
        raise HTTPException(404)
    if b["status"] != "pending_approval":
        raise HTTPException(409, "broadcast is not awaiting approval")
    sent = skipped = 0
    for c in db.q("SELECT id, phone, name FROM conversations WHERE business_id=?", (biz["id"],)):
        out = templates.send_smart(biz, c["id"], c["phone"], text=b["body"], template_id=b["template_id"],
                                   params=[(c["name"] or "there").split()[0]])
        if out["delivery"] == "skipped":
            skipped += 1
        else:
            sent += 1
    db.x("UPDATE broadcasts SET status='sent', approved_by=?, recipients=?, skipped=?, sent_at=CURRENT_TIMESTAMP WHERE id=?",
         (approver, sent, skipped, bid))
    log_event("broadcast_sent", business_id=biz["id"], broadcast_id=bid, recipients=sent, skipped=skipped)
    return db.q("SELECT * FROM broadcasts WHERE id=?", (bid,), one=True)


@app.post("/api/broadcasts/{bid}/reject")
def reject_broadcast(bid: int, biz: dict = Depends(current_biz)):
    db.x("UPDATE broadcasts SET status='rejected' WHERE id=? AND business_id=? AND status='pending_approval'", (bid, biz["id"]))
    return db.q("SELECT * FROM broadcasts WHERE id=?", (bid,), one=True)


# ---------- Razorpay payment webhook (public, signature-checked) ----------
@app.post("/api/payments/razorpay/webhook")
async def razorpay_webhook(req: Request):
    raw = await req.body()
    if not os.environ.get("RAZORPAY_WEBHOOK_SECRET"):
        raise HTTPException(503, "RAZORPAY_WEBHOOK_SECRET is not configured")
    if not payments.verify_razorpay_signature(raw, req.headers.get("x-razorpay-signature")):
        log_event("razorpay_signature_invalid", "warning")
        raise HTTPException(401, "invalid signature")
    event = json.loads(raw or b"{}")
    if event.get("event") != "payment_link.paid":
        return {"ok": True, "ignored": event.get("event")}
    oid, pay_id = payments.order_from_razorpay_event(event)
    o = db.q("SELECT o.*, c.phone FROM orders o LEFT JOIN conversations c ON c.id=o.conversation_id WHERE o.id=?", (oid,), one=True) if oid else None
    if not o:
        log_event("razorpay_unknown_order", "warning", order_id=oid)
        return {"ok": True, "matched": False}
    first = payments.mark_paid(o["id"], pay_id, "razorpay")
    log_event("order_paid", order_id=o["id"], provider="razorpay", first=first)
    if first and o["phone"]:
        biz = tenants.get(o["business_id"]) or tenants.default()
        deliver(biz, o["phone"], f"✅ Payment of ₹{o['total']} received for order *#{o['id']}*. Thank you!")
    return {"ok": True, "matched": True, "order_id": o["id"]}


app.include_router(admin.router)


# ---------- serve built frontend ----------
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")
