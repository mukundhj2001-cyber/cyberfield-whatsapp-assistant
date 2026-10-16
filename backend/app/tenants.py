"""Businesses (tenants). Each has its own WhatsApp number, token, knowledge base, menu/services, hours and languages.

Inbound webhooks are routed by value.metadata.phone_number_id. Anything that matches no business goes to the default
business (the lowest id), which sends with WHATSAPP_PHONE_NUMBER_ID / WHATSAPP_TOKEN from the environment, so a single-number
setup works exactly as before.
"""
import os
from . import db

PUBLIC_FIELDS = ("id", "slug", "name", "kind", "tagline")


def _load(row):
    if not row:
        return None
    row = dict(row)
    row["hours"] = db.jload(row.get("hours"), {}) or {}
    row["languages"] = db.jload(row.get("languages"), ["en", "hi", "ta"]) or ["en"]
    return row


def default() -> dict:
    return _load(db.q("SELECT * FROM businesses ORDER BY id LIMIT 1", one=True))


def get(bid) -> dict | None:
    return _load(db.q("SELECT * FROM businesses WHERE id=?", (bid,), one=True))


def all_() -> list[dict]:
    return [_load(r) for r in db.q("SELECT * FROM businesses ORDER BY id")]


def by_phone_number_id(pnid: str | None) -> dict:
    if pnid:
        b = db.q("SELECT * FROM businesses WHERE phone_number_id=?", (str(pnid),), one=True)
        if b:
            return _load(b)
    return default()


def is_default(biz) -> bool:
    d = default()
    return bool(d and biz and d["id"] == biz["id"])


def creds(biz) -> tuple[str, str] | None:
    """(phone_number_id, token) to send as this business, or None to simulate.

    A business's own values win; the default business falls back to the env vars. Other businesses without their own
    phone_number_id are simulated so demo tenants never send from the real number. One System User token can cover
    several numbers on the same WABA, so the env token is used when a business has a number but no token of its own."""
    pnid = (biz or {}).get("phone_number_id") or (os.environ.get("WHATSAPP_PHONE_NUMBER_ID") if is_default(biz) else None)
    token = (biz or {}).get("wa_token") or os.environ.get("WHATSAPP_TOKEN")
    return (pnid, token) if pnid and token else None


def public(biz) -> dict:
    return {k: biz.get(k) for k in PUBLIC_FIELDS}


def admin_view(biz) -> dict:
    """Business settings for the dashboard. The token is never returned, only whether one is set."""
    out = {k: v for k, v in biz.items() if k != "wa_token"}
    out["has_token"] = bool(biz.get("wa_token"))
    out["live"] = creds(biz) is not None
    return out
