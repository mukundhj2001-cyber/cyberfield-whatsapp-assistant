from app import llm, media, whatsapp


def sim(c, text="", phone="+910000000101", **kw):
    return c.post("/api/simulate", json={"phone": phone, "name": "Test", "text": text, **kw}).json()


def wa(c, msg, frm="919811100009", wamid="wamid.I1"):
    return c.post("/webhook", json={"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "123"},
        "contacts": [{"profile": {"name": "Devi"}, "wa_id": frm}], "messages": [{"from": frm, "id": wamid, **msg}]}}]}]}).json()


# ---------- interactive ----------
def test_menu_is_a_list_and_category_tap_adds_items(client):
    r = sim(client, "menu")
    assert r["interactive"]["kind"] == "list"
    cats = [x["id"] for x in r["interactive"]["sections"][0]["rows"]]
    assert "cat:Drinks" in cats
    r = sim(client, action="cat:Drinks", text="Drinks")
    item = [x for x in r["interactive"]["sections"][0]["rows"] if x["title"] == "Mango Lassi"][0]
    r = sim(client, action=item["id"], text="Mango Lassi")
    assert r["intent"] == "order" and "₹99" in r["reply"] and [b["id"] for b in r["interactive"]["buttons"]] == ["confirm", "more", "cancel"]
    r = sim(client, action="confirm", text="✅ Confirm")
    assert [b["id"] for b in r["interactive"]["buttons"]] == ["pickup", "cancel"]
    assert "Order" in sim(client, action="pickup", text="🏃 Pickup")["reply"]


def test_booking_slot_list_reply_via_webhook(client):
    r = wa(client, {"type": "text", "text": {"body": "book a table"}}, wamid="wamid.B1")["results"][0]
    slot = r["interactive"]["sections"][0]["rows"][0]
    r = wa(client, {"type": "interactive", "interactive": {"type": "list_reply", "list_reply": {"id": slot["id"], "title": slot["title"]}}},
           wamid="wamid.B2")["results"][0]
    assert "How many" in r["reply"]
    r = wa(client, {"type": "text", "text": {"body": "2"}}, wamid="wamid.B3")["results"][0]
    assert "SR-" in r["reply"]


def test_cancel_button_reply(client):
    sim(client, "2 masala dosa")
    r = wa(client, {"type": "interactive", "interactive": {"type": "button_reply", "button_reply": {"id": "cancel", "title": "✖ Cancel"}}},
           frm="910000000101", wamid="wamid.C1")["results"][0]
    assert r["intent"] == "cancel"


def test_interactive_payload_shapes():
    btn = whatsapp.interactive_message("Hi", {"kind": "buttons", "buttons": [{"id": "menu", "title": "x" * 30}]})
    assert btn["interactive"]["type"] == "button" and len(btn["interactive"]["action"]["buttons"][0]["reply"]["title"]) == 20
    lst = whatsapp.interactive_message("Pick", {"kind": "list", "button": "View", "sections": [{"title": "S", "rows": [
        {"id": f"r{i}", "title": "t", "description": "d"} for i in range(15)]}]})
    assert lst["interactive"]["type"] == "list" and len(lst["interactive"]["action"]["sections"][0]["rows"]) == 10


def test_live_send_uses_interactive(client, monkeypatch):
    sent = []

    class R:
        status_code, text = 200, ""
        def json(self): return {"messages": [{"id": "wamid.Z"}]}
    monkeypatch.setattr(whatsapp.httpx, "post", lambda url, **kw: sent.append(kw["json"]) or R())
    monkeypatch.setenv("WHATSAPP_TOKEN", "t"); monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "123")
    r = wa(client, {"type": "text", "text": {"body": "hi"}}, wamid="wamid.L1")
    assert r["results"][0]["delivery"] == "live" and sent[-1]["type"] == "interactive"


# ---------- grounded LLM ----------
def test_llm_fallback_grounded_and_refuses(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    seen = {}

    def fake_chat(system, user, timeout=20):
        seen["system"] = system
        return "UNKNOWN" if "wifi" in user else "Yes, Mango Lassi is ₹99."
    monkeypatch.setattr(llm, "chat", fake_chat)
    r = sim(client, "which dish would you recommend for kids")
    assert r["intent"] == "llm" and "₹99" in r["reply"]
    assert "Mango Lassi" in seen["system"] and "ONLY the FACTS" in seen["system"] and "11:00 AM" in seen["system"]
    r = sim(client, "do you have free wifi for guests")
    assert r["intent"] == "llm_unknown" and "HUMAN" in r["reply"]


def test_no_llm_falls_back(client):
    assert sim(client, "qwertyuiop zxcvbnm")["intent"] == "fallback"


# ---------- voice + images ----------
def test_mock_voice_note_hindi(client):
    r = sim(client, "मुझे 2 लस्सी चाहिए", type="audio")
    assert r["lang"] == "hi" and r["intent"] == "order" and "₹198" in r["reply"] and r["transcript"]


def test_live_voice_note_transcribed(client, monkeypatch):
    monkeypatch.setattr(whatsapp, "live", lambda: False)  # process inline in the test
    monkeypatch.setattr(whatsapp, "download_media", lambda mid, creds=None: (b"OggS...", "audio/ogg"))
    monkeypatch.setattr(llm, "transcribe", lambda audio, mime: {"text": "வணக்கம், டெலிவரி இருக்கா?", "lang": "ta"})
    r = wa(client, {"type": "audio", "audio": {"id": "MEDIA1", "mime_type": "audio/ogg; codecs=opus"}}, wamid="wamid.V1")["results"][0]
    assert r["lang"] == "ta" and r["intent"] == "faq"


def test_voice_without_stt_asks_to_type(client):
    r = wa(client, {"type": "audio", "audio": {"id": "MEDIA2"}}, wamid="wamid.V2")["results"][0]
    assert r["intent"] == "voice" and "type" in r["reply"]


def test_mock_photo_adds_to_cart_and_prescription_hands_off(client):
    r = sim(client, "photo of 2 butter chicken and 1 coffee", type="image")
    assert r["intent"] == "order" and "₹717" in r["reply"]
    r = sim(client, "prescription: Paracetamol 500mg x 10 tablets", type="image", phone="+910000000102")
    assert r["intent"] == "handoff"
    assert any(h["phone"] == "+910000000102" for h in client.get("/api/handoffs").json())


def test_live_photo_uses_vision(client, monkeypatch):
    monkeypatch.setattr(whatsapp, "live", lambda: False)
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setattr(whatsapp, "download_media", lambda mid, creds=None: (b"\xff\xd8", "image/jpeg"))
    monkeypatch.setattr(llm, "vision", lambda prompt, img, mime: '{"kind":"product","items":[{"name":"Veg Biryani","qty":2}],"summary":"biryani"}')
    r = wa(client, {"type": "image", "image": {"id": "IMG1", "mime_type": "image/jpeg"}}, wamid="wamid.P1")["results"][0]
    assert r["intent"] == "order" and "₹458" in r["reply"]
