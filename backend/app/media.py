"""Voice notes and photos.

Live: download from the Graph API, then speech-to-text (voice) or vision (photo) through the OpenAI-compatible env config.
Demo/mock: the simulator sends the 'transcript' or a description of the photo as text, so the flow works with no keys.
"""
from . import engine, llm, whatsapp
from .logs import log_event

VISION_PROMPT = """You read photos customers send to a business on WhatsApp.
Business menu / services (match to these names when possible): {menu}
Return ONLY JSON: {{"kind": "prescription" | "product" | "menu_item" | "receipt" | "other",
 "items": [{{"name": "<item as written or closest menu name>", "qty": <int>}}], "summary": "<one short sentence>"}}
Do not invent items you cannot read."""


def mock_vision(text: str) -> dict:
    """Demo stand-in for a vision model: read the photo 'contents' from the simulator text."""
    kind = "prescription" if any(w in text.lower() for w in ("prescription", "rx", "tablet", "mg", "पर्चा", "மருந்து")) else "product"
    items = [{"name": m["name"], "qty": q} for m, q in engine.parse_items(text)] if kind != "prescription" else []
    return {"kind": kind, "items": items, "summary": text[:150]}


def handle(m: dict) -> dict:
    phone, name, caption, mock = m["phone"], m.get("name"), m.get("text") or "", m.get("mock", False)
    if m["type"] == "audio":
        if mock:
            tr = {"text": caption, "lang": None}
        else:
            got = whatsapp.download_media(m.get("media_id"))
            tr = llm.transcribe(*got) if got else None
        if not tr or not tr["text"]:
            log_event("voice_unavailable", reason="no STT configured" if not llm.stt_enabled() else "download/transcribe failed")
            conv = engine.get_conv(phone, name)
            lang = conv["lang"] or "en"
            engine.log(conv["id"], "in", "customer", "🎤 Voice note", "voice", lang)
            engine.log(conv["id"], "out", "bot", engine.T["voice_off"][lang], "voice", lang)
            return {"reply": engine.T["voice_off"][lang], "intent": "voice", "lang": lang, "interactive": None}
        r = engine.handle_message(phone, name, tr["text"], lang_hint=tr.get("lang"), log_text=f"🎤 {tr['text']}")
        return {**r, "transcript": tr["text"]}

    # image
    if mock:
        found = mock_vision(caption)
    else:
        found = None
        got = whatsapp.download_media(m.get("media_id"))
        if got and llm.enabled():
            menu = ", ".join(x["name"] for x in engine.menu_items())
            found = llm.parse_json(llm.vision(VISION_PROMPT.format(menu=menu) + (f"\nCustomer caption: {caption}" if caption else ""), *got))
        if found is None and caption:
            found = mock_vision(caption)  # no vision model: still use the caption
    r = engine.handle_image(phone, name, caption, found)
    return {**r, "vision": found}
