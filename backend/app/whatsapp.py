"""WhatsApp Cloud API adapter.

Real sending only when WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID are set; otherwise every send is logged as 'simulated'.
Sends retry with exponential backoff on network errors, HTTP 429 and 5xx. 4xx errors are not retried.
"""
import hashlib, hmac, os, time
import httpx
from . import db
from .logs import log_event, mask_phone

GRAPH_VERSION = os.environ.get("WHATSAPP_GRAPH_VERSION", "v20.0")
_sig_warned = False


def graph_url(path: str) -> str:
    return f"https://graph.facebook.com/{os.environ.get('WHATSAPP_GRAPH_VERSION', GRAPH_VERSION)}/{path.lstrip('/')}"


def live() -> bool:
    return bool(os.environ.get("WHATSAPP_TOKEN") and os.environ.get("WHATSAPP_PHONE_NUMBER_ID"))


# ---------- webhook signature ----------
def verify_signature(raw: bytes, header: str | None) -> bool:
    """Check X-Hub-Signature-256 against WHATSAPP_APP_SECRET. If the secret is unset, allow and warn once."""
    global _sig_warned
    secret = os.environ.get("WHATSAPP_APP_SECRET")
    if not secret:
        if not _sig_warned:
            log_event("webhook_signature_unchecked", "warning", hint="Set WHATSAPP_APP_SECRET to verify X-Hub-Signature-256")
            _sig_warned = True
        return True
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header[7:], expected)


# ---------- sending ----------
def _post_with_retry(url: str, token: str, body: dict):
    """Returns (ok, response_json_or_None, error_text, attempts)."""
    tries = max(1, int(os.environ.get("WHATSAPP_SEND_RETRIES", "3")))
    base = float(os.environ.get("WHATSAPP_RETRY_BASE_DELAY", "0.5"))
    err = ""
    for i in range(1, tries + 1):
        try:
            r = httpx.post(url, timeout=15, headers={"Authorization": f"Bearer {token}"}, json=body)
            if r.status_code < 400:
                return True, r.json(), "", i
            err = f"HTTP {r.status_code}: {r.text[:300]}"
            if r.status_code != 429 and r.status_code < 500:
                return False, None, err, i  # bad request / auth: retrying won't help
        except httpx.HTTPError as e:
            err = f"{type(e).__name__}: {e}"[:300]
        if i < tries:
            delay = base * 2 ** (i - 1)
            log_event("whatsapp_send_retry", "warning", attempt=i, delay_s=delay, error=err)
            time.sleep(delay)
    return False, None, err, tries


def send(phone: str, message: dict, log_text: str, creds: tuple[str, str] | None = None) -> str:
    """Send one message object (the part after messaging_product/to). Returns 'live' | 'simulated' | 'failed'."""
    if creds is None and live():
        creds = (os.environ["WHATSAPP_PHONE_NUMBER_ID"], os.environ["WHATSAPP_TOKEN"])
    mode, wamid, err, attempts = "simulated", None, None, 0
    if creds and creds[0] and creds[1]:
        body = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": phone.lstrip("+"), **message}
        ok, data, err, attempts = _post_with_retry(graph_url(f"{creds[0]}/messages"), creds[1], body)
        if ok:
            mode = "live"
            wamid = ((data or {}).get("messages") or [{}])[0].get("id")
        else:
            mode = "failed"
        log_event("whatsapp_send", "info" if ok else "error", to=mask_phone(phone), type=message.get("type"),
                  mode=mode, attempts=attempts, wa_message_id=wamid, error=err or None)
    db.x("INSERT INTO outbox(phone,text,mode,wa_message_id,status,error,attempts) VALUES(?,?,?,?,?,?,?)",
         (phone, log_text, mode, wamid, "sent" if mode == "live" else mode, err or None, attempts))
    return mode


def send_text(phone: str, text: str, creds=None) -> str:
    return send(phone, {"type": "text", "text": {"body": text[:4096], "preview_url": False}}, text, creds)


# ---------- inbound ----------
def claim_message(wa_id: str | None) -> bool:
    """Idempotency: True the first time we see a WhatsApp message id, False on Meta's retries/duplicates."""
    if not wa_id:
        return True
    return db.xc("INSERT OR IGNORE INTO processed_messages(wa_id) VALUES(?)", (wa_id,)) == 1


def record_statuses(payload: dict) -> int:
    """Store sent/delivered/read/failed status callbacks and update the outbox row."""
    n = 0
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for s in change.get("value", {}).get("statuses", []) or []:
                errs = "; ".join(f"{e.get('code')}: {e.get('title')}" for e in s.get("errors", []) or []) or None
                db.x("INSERT INTO message_status(wa_message_id,status,recipient,error,ts) VALUES(?,?,?,?,?)",
                     (s.get("id"), s.get("status"), s.get("recipient_id"), errs, s.get("timestamp")))
                db.x("UPDATE outbox SET status=?, error=COALESCE(?, error) WHERE wa_message_id=?", (s.get("status"), errs, s.get("id")))
                log_event("whatsapp_status", "warning" if s.get("status") == "failed" else "info",
                          wa_message_id=s.get("id"), status=s.get("status"), to=mask_phone(s.get("recipient_id")), error=errs)
                n += 1
    return n


def parse_inbound(payload: dict):
    """Yield one dict per inbound message: phone, name, wa_id, type, text, plus phone_number_id."""
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            pnid = (value.get("metadata") or {}).get("phone_number_id")
            names = {c.get("wa_id"): c.get("profile", {}).get("name") for c in value.get("contacts", [])}
            for m in value.get("messages", []) or []:
                base = {"phone": "+" + m["from"].lstrip("+"), "name": names.get(m["from"]), "wa_id": m.get("id"),
                        "type": m.get("type"), "phone_number_id": pnid, "text": ""}
                if m.get("type") == "text":
                    yield {**base, "text": m["text"]["body"]}
                elif m.get("type") == "interactive":
                    i = m["interactive"]
                    rep = i.get("button_reply") or i.get("list_reply") or {}
                    yield {**base, "text": rep.get("title", ""), "action": rep.get("id")}
                elif m.get("type") == "button":  # quick-reply button on a template
                    yield {**base, "text": m["button"].get("text", ""), "action": m["button"].get("payload")}
                else:
                    yield base
