"""Meta message templates and the 24-hour customer service window.

Inside 24h of the customer's last message we may send free-form text. Outside it, Meta only delivers pre-approved
templates, so reminders and offers use a stored template (create and get it approved in WhatsApp Manager first,
then add the exact name + language here)."""
from . import db, tenants, whatsapp


def in_window(conv_id: int) -> bool:
    return bool(db.q("SELECT 1 FROM messages WHERE conversation_id=? AND direction='in' AND created_at > datetime('now','-24 hours') LIMIT 1",
                     (conv_id,), one=True))


def find(biz_id: int, template_id: int | None = None, purpose: str | None = None) -> dict | None:
    if template_id:
        return db.q("SELECT * FROM templates WHERE id=? AND business_id=?", (template_id, biz_id), one=True)
    if purpose:
        return db.q("SELECT * FROM templates WHERE business_id=? AND purpose=? ORDER BY id LIMIT 1", (biz_id, purpose), one=True)
    return None


def render(tpl: dict, params: list[str]) -> str:
    body = tpl.get("body") or ""
    for i, p in enumerate(params, 1):
        body = body.replace("{{%d}}" % i, str(p))
    return body


def send_smart(biz: dict, conv_id: int, phone: str, text: str, template_id: int | None = None, purpose: str | None = None,
               params: list[str] | None = None) -> dict:
    """Free text inside the 24h window; the approved template outside it; 'skipped' when neither is allowed."""
    creds = tenants.creds(biz) or ("", "")
    if in_window(conv_id):
        return {"delivery": whatsapp.send_text(phone, text, creds, biz["id"]), "via": "text"}
    tpl = find(biz["id"], template_id, purpose)
    if not tpl:
        return {"delivery": "skipped", "via": None}
    p = (params or [])[: tpl["param_count"] or 0]
    p += [""] * ((tpl["param_count"] or 0) - len(p))
    return {"delivery": whatsapp.send_template(phone, tpl["name"], tpl["language"], p, creds, biz["id"], render(tpl, p)),
            "via": "template", "template": tpl["name"]}
