from app import engine


def sim(c, text, phone="+910000000001"):
    return c.post("/api/simulate", json={"phone": phone, "name": "Test", "text": text}).json()


def test_language_detection():
    assert engine.detect_lang("Hello, are you open?") == "en"
    assert engine.detect_lang("आप कितने बजे खुलते हैं") == "hi"
    assert engine.detect_lang("வணக்கம்") == "ta"
    assert engine.detect_lang("namaste bhai menu kya hai") == "hi"
    assert engine.detect_lang("vanakkam, enna irukku") == "ta"


def test_faq_multilingual(client):
    assert "11:00 AM" in sim(client, "What are your opening hours?")["reply"]
    r = sim(client, "डिलीवरी करते हो?", "+910000000002")
    assert r["intent"] == "faq" and r["lang"] == "hi" and "किमी" in r["reply"]
    r = sim(client, "பார்க்கிங் இருக்கா?", "+910000000003")
    assert r["lang"] == "ta" and "பார்க்கிங்" in r["reply"]


def test_order_flow(client):
    r = sim(client, "2 masala dosa and 1 filter coffee")
    assert r["intent"] == "order" and "₹357" in r["reply"]
    sim(client, "add one mango lassi")
    assert "Great" in sim(client, "confirm")["reply"]
    assert "Order" in sim(client, "PICKUP")["reply"]
    o = client.get("/api/orders").json()
    mine = [x for x in o if x["phone"] == "+910000000001"][0]
    assert mine["total"] == 2 * 149 + 59 + 99 and mine["fulfilment"] == "Pickup"


def test_booking_flow_and_capacity(client):
    r = sim(client, "I want to book a table")
    assert r["intent"] == "booking" and "1." in r["reply"]
    assert "How many" in sim(client, "1")["reply"]
    r = sim(client, "3")
    assert "SR-" in r["reply"]
    assert any(b["party_size"] == 3 and b["phone"] == "+910000000001" for b in client.get("/api/bookings").json())


def test_lead_capture(client):
    assert sim(client, "Do you do catering for a wedding?")["intent"] == "lead"
    assert "Thanks" in sim(client, "Asha Menon, asha@example.com")["reply"]
    assert any(l["contact"] == "asha@example.com" for l in client.get("/api/leads").json())


def test_handoff_pauses_bot_and_owner_can_resolve(client):
    sim(client, "I want to speak to a human")
    assert sim(client, "hello?")["reply"] is None  # bot stays quiet while human is needed
    h = client.get("/api/handoffs").json()
    cid = [c for c in h if c["phone"] == "+910000000001"][0]["id"]
    assert client.post(f"/api/conversations/{cid}/reply", json={"text": "Hi, this is the manager"}).json()["delivery"] == "simulated"
    client.post(f"/api/conversations/{cid}/resolve")
    assert sim(client, "menu")["intent"] == "menu"


def test_broadcast_requires_approval(client):
    b = client.post("/api/broadcasts", json={"title": "T", "body": "Hello all"}).json()
    assert b["status"] == "pending_approval" and b["recipients"] == 0
    sent = client.post(f"/api/broadcasts/{b['id']}/approve").json()
    assert sent["status"] == "sent" and sent["recipients"] > 0
    assert client.post(f"/api/broadcasts/{b['id']}/approve").status_code == 409


def test_webhook_verify_and_inbound(client):
    ok = client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "cyberfield-demo-token", "hub.challenge": "42"})
    assert ok.text == "42"
    assert client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "1"}).status_code == 403
    payload = {"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"phone_number_id": "123"},
        "contacts": [{"profile": {"name": "Devi"}, "wa_id": "919811122233"}],
        "messages": [{"from": "919811122233", "id": "wamid.x", "timestamp": "1700000000", "type": "text", "text": {"body": "menu"}}]}}]}]}
    r = client.post("/webhook", json=payload).json()
    assert r["processed"] == 1 and r["results"][0]["intent"] == "menu" and r["results"][0]["delivery"] == "simulated"


def test_seeded_dashboard(client):
    s = client.get("/api/stats").json()
    assert s["orders"] >= 1 and s["bookings"] >= 1 and s["leads"] >= 1 and s["handoffs"] >= 1
