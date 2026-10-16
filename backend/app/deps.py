"""Shared request helpers: which business the dashboard/simulator is working on, and sending as that business."""
from fastapi import HTTPException, Request
from . import tenants, whatsapp


def current_biz(request: Request) -> dict:
    """Selected business from the X-Business-Id header (or ?business_id=), else the default business."""
    raw = request.headers.get("x-business-id") or request.query_params.get("business_id")
    biz = tenants.get(int(raw)) if raw and str(raw).isdigit() else tenants.default()
    if not biz:
        raise HTTPException(404, "unknown business")
    return biz


def deliver(biz: dict, phone: str, text: str, ui: dict | None = None) -> str:
    return whatsapp.send_reply(phone, text, ui, creds=tenants.creds(biz) or ("", ""), bid=biz["id"])
