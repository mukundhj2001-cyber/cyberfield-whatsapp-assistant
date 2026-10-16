"""Payment links for WhatsApp orders.

- Razorpay Payment Links API when RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are set. Paid status arrives on
  POST /api/payments/razorpay/webhook, verified with RAZORPAY_WEBHOOK_SECRET (X-Razorpay-Signature, HMAC-SHA256 of the raw body).
- Otherwise a UPI deep link (upi://pay?...) built from the business's UPI ID. The owner marks UPI payments paid in the dashboard.
- Neither configured: no link (pay on delivery / at the counter).
"""
import hashlib, hmac, os, urllib.parse
import httpx
from . import db
from .logs import log_event

RAZORPAY_API = "https://api.razorpay.com/v1"


def razorpay_enabled() -> bool:
    return bool(os.environ.get("RAZORPAY_KEY_ID") and os.environ.get("RAZORPAY_KEY_SECRET"))


def mode() -> str:
    return "razorpay" if razorpay_enabled() else "upi"


def upi_link(upi_id: str, payee: str, amount: int, note: str) -> str:
    params = {"pa": upi_id.strip(), "pn": payee[:40], "am": f"{amount:.2f}", "cu": "INR", "tn": note[:60]}
    return "upi://pay?" + "&".join(f"{k}={urllib.parse.quote(v, safe='@.')}" for k, v in params.items())


def razorpay_link(order_id: int, biz: dict, amount: int, customer: dict) -> dict | None:
    body = {"amount": int(amount) * 100, "currency": "INR", "accept_partial": False,
            "reference_id": f"cf-{biz['id']}-{order_id}", "description": f"{biz['name']} order #{order_id}"[:255],
            "customer": {k: v for k, v in {"name": customer.get("name"), "contact": customer.get("phone")}.items() if v},
            "notify": {"sms": False, "email": False}, "reminder_enable": False,
            "notes": {"order_id": str(order_id), "business_id": str(biz["id"])}}
    try:
        r = httpx.post(f"{RAZORPAY_API}/payment_links", json=body, timeout=15,
                       auth=(os.environ["RAZORPAY_KEY_ID"], os.environ["RAZORPAY_KEY_SECRET"]))
        r.raise_for_status()
        d = r.json()
        return {"id": d["id"], "url": d["short_url"]}
    except Exception as e:
        log_event("razorpay_link_failed", "error", order_id=order_id, error=f"{type(e).__name__}: {getattr(getattr(e, 'response', None), 'text', '')[:200]}")
        return None


def create_for_order(order_id: int, biz: dict, conv: dict) -> str | None:
    """Create and store a payment link for an order. Returns the URL to send, or None."""
    o = db.q("SELECT * FROM orders WHERE id=?", (order_id,), one=True)
    if not o or not o["total"]:
        return None
    if razorpay_enabled():
        link = razorpay_link(order_id, biz, o["total"], conv)
        if link:
            db.x("UPDATE orders SET payment_provider='razorpay', payment_link=?, payment_link_id=? WHERE id=?", (link["url"], link["id"], order_id))
            log_event("payment_link_created", provider="razorpay", order_id=order_id)
            return link["url"]
    if biz.get("upi_id"):
        url = upi_link(biz["upi_id"], biz["name"], o["total"], f"{biz['name']} order {order_id}")
        db.x("UPDATE orders SET payment_provider='upi', payment_link=? WHERE id=?", (url, order_id))
        return url
    return None


def verify_razorpay_signature(raw: bytes, signature: str | None) -> bool:
    secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET")
    if not secret or not signature:
        return False
    return hmac.compare_digest(hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest(), signature)


def mark_paid(order_id: int, ref: str | None, provider: str) -> bool:
    """Idempotent. Returns True only the first time an order flips to paid."""
    return db.xc("UPDATE orders SET payment_status='paid', payment_ref=?, payment_provider=COALESCE(payment_provider, ?), "
                 "paid_at=CURRENT_TIMESTAMP WHERE id=? AND payment_status!='paid'", (ref, provider, order_id)) == 1


def order_from_razorpay_event(event: dict) -> tuple[int | None, str | None]:
    """(order_id, payment_id) from a payment_link.paid webhook."""
    p = event.get("payload", {})
    link = (p.get("payment_link") or {}).get("entity", {})
    pay_id = (p.get("payment") or {}).get("entity", {}).get("id")
    if link.get("id"):
        row = db.q("SELECT id FROM orders WHERE payment_link_id=?", (link["id"],), one=True)
        if row:
            return row["id"], pay_id
    oid = (link.get("notes") or {}).get("order_id")
    return (int(oid) if str(oid or "").isdigit() else None), pay_id
