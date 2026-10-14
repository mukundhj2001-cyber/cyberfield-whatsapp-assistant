"""WhatsApp Cloud API adapter. Real sending only when WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID are set."""
import os
import httpx
from . import db


def live() -> bool:
    return bool(os.environ.get("WHATSAPP_TOKEN") and os.environ.get("WHATSAPP_PHONE_NUMBER_ID"))


def send_text(phone: str, text: str) -> str:
    """Send (or simulate) an outbound text. Returns mode used: 'live' | 'simulated' | 'failed'."""
    mode = "simulated"
    if live():
        try:
            r = httpx.post(f"https://graph.facebook.com/v20.0/{os.environ['WHATSAPP_PHONE_NUMBER_ID']}/messages", timeout=15,
                           headers={"Authorization": f"Bearer {os.environ['WHATSAPP_TOKEN']}"},
                           json={"messaging_product": "whatsapp", "to": phone.lstrip("+"), "type": "text", "text": {"body": text}})
            r.raise_for_status()
            mode = "live"
        except Exception:
            mode = "failed"
    db.x("INSERT INTO outbox(phone,text,mode) VALUES(?,?,?)", (phone, text, mode))
    return mode


def parse_inbound(payload: dict):
    """Yield (phone, name, text) for each text message in a Cloud API webhook payload."""
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            names = {c.get("wa_id"): c.get("profile", {}).get("name") for c in value.get("contacts", [])}
            for m in value.get("messages", []):
                if m.get("type") == "text":
                    yield "+" + m["from"].lstrip("+"), names.get(m["from"]), m["text"]["body"]
                elif m.get("type") == "interactive":
                    i = m["interactive"]
                    title = (i.get("button_reply") or i.get("list_reply") or {}).get("title", "")
                    yield "+" + m["from"].lstrip("+"), names.get(m["from"]), title
