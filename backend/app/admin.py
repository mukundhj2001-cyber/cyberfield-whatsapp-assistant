"""Owner settings (business profile, FAQs, menu/services, hours, slots, templates) and analytics. All behind login."""
import datetime as dt, json, os, re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from . import db, payments, seed, tenants
from .deps import current_biz

router = APIRouter(prefix="/api")

# editable columns per collection (business_id is always forced to the selected business)
FIELDS = {
    "faq": ("topic", "keywords", "answer_en", "answer_hi", "answer_ta"),
    "menu": ("name", "price", "category", "aliases"),
    "slots": ("starts_at", "capacity"),
    "templates": ("name", "language", "category", "purpose", "body", "param_count"),
}
TEMPLATE_NAME = re.compile(r"^[a-z0-9_]{1,512}$")


class BusinessIn(BaseModel):
    name: str | None = None
    tagline: str | None = None
    kind: str | None = None
    hours: dict | None = None
    languages: list[str] | None = None
    default_lang: str | None = None
    upi_id: str | None = None
    phone_number_id: str | None = None
    wa_token: str | None = None      # write-only; "" leaves the stored token unchanged
    clear_token: bool = False
    orders_enabled: bool | None = None
    code_prefix: str | None = None


class NewBusinessIn(BaseModel):
    name: str
    kind: str = "restaurant"
    tagline: str = ""


class SlotGenIn(BaseModel):
    days: int = 7
    hours: list[int] = [10, 12, 15, 18]
    capacity: int = 1
    start: int = 1


def _clean(kind: str, data: dict) -> dict:
    out = {k: data[k] for k in FIELDS[kind] if k in data}
    if kind == "menu":
        if "price" in out:
            out["price"] = max(0, int(out["price"]))
        if "aliases" in out:
            a = out["aliases"]
            out["aliases"] = json.dumps([x.strip() for x in (a.split(",") if isinstance(a, str) else a) if x.strip()], ensure_ascii=False)
    if kind == "slots":
        if "starts_at" in out:
            try:
                out["starts_at"] = dt.datetime.fromisoformat(out["starts_at"]).isoformat(timespec="minutes")
            except ValueError:
                raise HTTPException(400, "starts_at must be like 2026-10-20T18:00")
        if "capacity" in out:
            out["capacity"] = max(1, int(out["capacity"]))
    if kind == "templates":
        if "name" in out and not TEMPLATE_NAME.match(out["name"]):
            raise HTTPException(400, "template name must match Meta's: lowercase letters, digits and underscores")
        if "body" in out and "param_count" not in out:
            out["param_count"] = len(set(re.findall(r"\{\{(\d+)\}\}", out["body"] or "")))
    return out


@router.get("/settings")
def get_settings(biz: dict = Depends(current_biz)):
    b = biz["id"]
    menu = [dict(m, aliases=json.loads(m["aliases"] or "[]")) for m in db.q("SELECT * FROM menu WHERE business_id=? ORDER BY category, id", (b,))]
    return {"business": tenants.admin_view(biz), "faq": db.q("SELECT * FROM faq WHERE business_id=? ORDER BY id", (b,)), "menu": menu,
            "slots": db.q("SELECT * FROM slots WHERE business_id=? AND starts_at > ? ORDER BY starts_at",
                          (b, (dt.datetime.now() - dt.timedelta(days=1)).isoformat(timespec="minutes"))),
            "templates": db.q("SELECT * FROM templates WHERE business_id=? ORDER BY id", (b,)),
            "payments": {"mode": payments.mode(), "razorpay_webhook": bool(os.environ.get("RAZORPAY_WEBHOOK_SECRET"))}}


@router.put("/settings/business")
def update_business(body: BusinessIn, biz: dict = Depends(current_biz)):
    d = body.model_dump(exclude_none=True)
    sets = {}
    for k in ("name", "tagline", "kind", "default_lang", "upi_id", "code_prefix"):
        if k in d:
            sets[k] = str(d[k]).strip()
    if "kind" in sets and sets["kind"] not in ("restaurant", "clinic", "salon", "retail", "other"):
        raise HTTPException(400, "bad kind")
    if "hours" in d:
        sets["hours"] = json.dumps({k: str(v).strip() for k, v in d["hours"].items() if k in ("en", "hi", "ta") and str(v).strip()}, ensure_ascii=False)
    if "languages" in d:
        langs = [x for x in d["languages"] if x in ("en", "hi", "ta")] or ["en"]
        sets["languages"] = json.dumps(langs)
    if "orders_enabled" in d:
        sets["orders_enabled"] = int(d["orders_enabled"])
    if "phone_number_id" in d:
        pnid = d["phone_number_id"].strip() or None
        if pnid and db.q("SELECT 1 FROM businesses WHERE phone_number_id=? AND id!=?", (pnid, biz["id"]), one=True):
            raise HTTPException(409, "another business already uses that phone_number_id")
        sets["phone_number_id"] = pnid
    if d.get("wa_token"):
        sets["wa_token"] = d["wa_token"].strip()
    if body.clear_token:
        sets["wa_token"] = None
    if sets:
        db.x(f"UPDATE businesses SET {', '.join(f'{k}=?' for k in sets)} WHERE id=?", (*sets.values(), biz["id"]))
    return tenants.admin_view(tenants.get(biz["id"]))


@router.post("/businesses")
def create_business(body: NewBusinessIn):
    slug = re.sub(r"[^a-z0-9]+", "-", body.name.lower()).strip("-") or "business"
    while db.q("SELECT 1 FROM businesses WHERE slug=?", (slug,), one=True):
        slug += "-2"
    bid = db.x("INSERT INTO businesses(slug,name,kind,tagline,orders_enabled,code_prefix) VALUES(?,?,?,?,?,?)",
               (slug, body.name.strip(), body.kind, body.tagline, int(body.kind in ("restaurant", "retail")),
                "".join(w[0] for w in body.name.split()[:2]).upper() or "BK"))
    return tenants.public(tenants.get(bid))


@router.post("/settings/slots/generate")
def generate_slots(body: SlotGenIn, biz: dict = Depends(current_biz)):
    hours = [h for h in body.hours if 0 <= int(h) <= 23]
    return {"added": seed.add_slots(biz["id"], days=max(1, min(body.days, 60)), hours=hours, capacity=max(1, body.capacity), start=body.start)}


@router.post("/settings/{kind}")
def create_item(kind: str, data: dict, biz: dict = Depends(current_biz)):
    if kind not in FIELDS:
        raise HTTPException(404)
    row = _clean(kind, data)
    required = {"faq": "topic", "menu": "name", "slots": "starts_at", "templates": "name"}[kind]
    if not row.get(required):
        raise HTTPException(400, f"{required} is required")
    row["business_id"] = biz["id"]
    new_id = db.x(f"INSERT INTO {kind}({','.join(row)}) VALUES({','.join('?' * len(row))})", tuple(row.values()))
    return db.q(f"SELECT * FROM {kind} WHERE id=?", (new_id,), one=True)


@router.put("/settings/{kind}/{item_id}")
def update_item(kind: str, item_id: int, data: dict, biz: dict = Depends(current_biz)):
    if kind not in FIELDS:
        raise HTTPException(404)
    row = _clean(kind, data)
    if row and not db.xc(f"UPDATE {kind} SET {', '.join(f'{k}=?' for k in row)} WHERE id=? AND business_id=?", (*row.values(), item_id, biz["id"])):
        raise HTTPException(404)
    return db.q(f"SELECT * FROM {kind} WHERE id=?", (item_id,), one=True)


@router.delete("/settings/{kind}/{item_id}")
def delete_item(kind: str, item_id: int, biz: dict = Depends(current_biz)):
    if kind not in FIELDS:
        raise HTTPException(404)
    if kind == "slots" and db.q("SELECT 1 FROM bookings WHERE slot_id=? AND status='confirmed'", (item_id,), one=True):
        raise HTTPException(409, "slot has bookings")
    if not db.xc(f"DELETE FROM {kind} WHERE id=? AND business_id=?", (item_id, biz["id"])):
        raise HTTPException(404)
    return {"ok": True}


# ---------- analytics ----------
def _offset_minutes() -> int:
    """Local time offset for 'busy hours' (APP_UTC_OFFSET like +05:30; default India)."""
    m = re.match(r"^([+-])(\d{1,2}):?(\d{2})$", (os.environ.get("APP_UTC_OFFSET") or "+05:30").strip())
    if not m:
        return 330
    return (1 if m.group(1) == "+" else -1) * (int(m.group(2)) * 60 + int(m.group(3)))


@router.get("/analytics")
def analytics(days: int = 30, biz: dict = Depends(current_biz)):
    b, days = biz["id"], max(1, min(days, 365))
    since = f"-{days} days"
    off = f"{_offset_minutes():+d} minutes"
    one = lambda sql, *a: db.q(sql, (b, since, *a), one=True)["n"] or 0
    inbound = """FROM messages m JOIN conversations c ON c.id=m.conversation_id
                 WHERE c.business_id=? AND m.created_at > datetime('now', ?) AND m.direction='in'"""
    hours = {r["h"]: r["n"] for r in db.q(f"SELECT CAST(strftime('%H', m.created_at, '{off}') AS INTEGER) h, COUNT(*) n {inbound} GROUP BY h", (b, since))}
    daily_msgs = {r["d"]: r["n"] for r in db.q(f"SELECT date(m.created_at, '{off}') d, COUNT(DISTINCT m.conversation_id) n {inbound} GROUP BY d", (b, since))}
    daily_orders = {r["d"]: r for r in db.q(f"""SELECT date(created_at, '{off}') d, COUNT(*) n, COALESCE(SUM(total),0) revenue FROM orders
                                               WHERE business_id=? AND created_at > datetime('now', ?) AND status!='cancelled' GROUP BY d""", (b, since))}
    today = (dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(minutes=_offset_minutes())).date()
    series = []
    for i in range(min(days, 14) - 1, -1, -1):
        d = (today - dt.timedelta(days=i)).isoformat()
        o = daily_orders.get(d) or {}
        series.append({"date": d[5:], "chats": daily_msgs.get(d, 0), "orders": o.get("n", 0), "revenue": o.get("revenue", 0)})
    intents = db.q(f"SELECT COALESCE(m.intent,'other') intent, COUNT(*) n {inbound} GROUP BY intent ORDER BY n DESC", (b, since))
    return {
        "days": days,
        "chats": one("SELECT COUNT(DISTINCT m.conversation_id) n " + inbound),
        "messages_in": one("SELECT COUNT(*) n " + inbound),
        "orders": one("SELECT COUNT(*) n FROM orders WHERE business_id=? AND created_at > datetime('now', ?) AND status!='cancelled'"),
        "revenue": one("SELECT COALESCE(SUM(total),0) n FROM orders WHERE business_id=? AND created_at > datetime('now', ?) AND status!='cancelled'"),
        "revenue_paid": one("SELECT COALESCE(SUM(total),0) n FROM orders WHERE business_id=? AND created_at > datetime('now', ?) AND payment_status='paid'"),
        "bookings": one("SELECT COUNT(*) n FROM bookings WHERE business_id=? AND created_at > datetime('now', ?)"),
        "leads": one("SELECT COUNT(*) n FROM leads WHERE business_id=? AND created_at > datetime('now', ?)"),
        "missed": one("SELECT COUNT(*) n " + inbound + " AND m.intent IN ('fallback','llm_unknown')"),
        "handoffs": one("SELECT COUNT(*) n " + inbound + " AND m.intent='handoff'"),
        "waiting_now": db.q("SELECT COUNT(*) n FROM conversations WHERE business_id=? AND needs_human=1", (b,), one=True)["n"],
        "busy_hours": [{"hour": h, "label": f"{h % 12 or 12}{'a' if h < 12 else 'p'}", "messages": hours.get(h, 0)} for h in range(24)],
        "daily": series,
        "intents": intents,
    }
