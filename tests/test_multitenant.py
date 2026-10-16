import hashlib, hmac, json, sqlite3
from app import db, payments, tenants, whatsapp


def biz_id(slug):
    return db.q("SELECT id FROM businesses WHERE slug=?", (slug,), one=True)["id"]


def sim(c, text, bid, phone="+910000000201", **kw):
    return c.post("/api/simulate", json={"phone": phone, "name": "Test", "text": text, **kw}, headers={"X-Business-Id": str(bid)}).json()


def wa_payload(pnid, text="hi", wamid="wamid.T1", frm="919800000301"):
    return {"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": pnid}, "contacts": [{"profile": {"name": "Asha"}, "wa_id": frm}],
            "messages": [{"from": frm, "id": wamid, "type": "text", "text": {"body": text}}]}}]}]}


# ---------- tenants ----------
def test_three_demo_businesses_seeded(client):
    kinds = {b["slug"]: b["kind"] for b in client.get("/api/public/businesses").json()}
    assert kinds == {"spice-route": "restaurant", "sunrise-clinic": "clinic", "glow-studio": "salon"}
    assert "wa_token" not in json.dumps(client.get("/api/public/businesses").json())


def test_inbound_routed_by_phone_number_id(client, monkeypatch):
    clinic = biz_id("sunrise-clinic")
    db.x("UPDATE businesses SET phone_number_id='555000', wa_token='clinic-token' WHERE id=?", (clinic,))
    sent = []

    class R:
        status_code, text = 200, ""
        def json(self): return {"messages": [{"id": "wamid.out"}]}
    monkeypatch.setattr(whatsapp.httpx, "post", lambda url, **kw: sent.append((url, kw["headers"]["Authorization"])) or R())
    r = client.post("/webhook", json=wa_payload("555000", "Hi")).json()["results"][0]
    assert r["business_id"] == clinic and "Sunrise Family Clinic" in r["reply"] and r["delivery"] == "live"
    assert "/555000/messages" in sent[-1][0] and sent[-1][1] == "Bearer clinic-token"
    # unknown number -> default business (the existing single-number setup), simulated without env keys
    r = client.post("/webhook", json=wa_payload("999999", "Hi", wamid="wamid.T2")).json()["results"][0]
    assert r["business_id"] == tenants.default()["id"] and "Spice Route" in r["reply"] and r["delivery"] == "simulated"


def test_default_business_uses_env_credentials(client, monkeypatch):
    monkeypatch.setenv("WHATSAPP_TOKEN", "env-token"); monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "111")
    assert tenants.creds(tenants.default()) == ("111", "env-token")
    salon = tenants.get(biz_id("glow-studio"))
    assert tenants.creds(salon) is None  # demo tenant without its own number never sends from the real one


def test_data_is_isolated_per_business(client):
    clinic = biz_id("sunrise-clinic")
    r = sim(client, "menu", clinic)
    assert "Blood test" in r["reply"] and "Paneer" not in r["reply"]
    names = [c["name"] for c in client.get("/api/conversations", headers={"X-Business-Id": str(clinic)}).json()]
    assert "Priya" not in names and "Anitha" in names
    spice_conv = client.get("/api/conversations").json()[0]["id"]
    assert client.get(f"/api/conversations/{spice_conv}/messages", headers={"X-Business-Id": str(clinic)}).status_code == 404


def test_clinic_service_goes_straight_to_booking(client):
    clinic = biz_id("sunrise-clinic")
    r = sim(client, "I want a full body checkup", clinic)
    assert r["intent"] == "booking" and r["interactive"]["kind"] == "list"
    r = sim(client, "1", clinic)
    assert "SC-" in r["reply"] and "Full body checkup" in r["reply"]  # no party-size question for appointments


def test_hours_from_settings_and_language_prefs(client):
    salon = biz_id("glow-studio")
    client.put("/api/settings/business", json={"hours": {"en": "Daily 9 AM – 9 PM"}}, headers={"X-Business-Id": str(salon)})
    assert "Daily 9 AM – 9 PM" in sim(client, "what are your timings", salon)["reply"]
    assert sim(client, "नमस्ते", salon, phone="+910000000202")["lang"] == "en"  # salon doesn't offer Hindi


# ---------- settings ----------
def test_settings_crud(client):
    h = {"X-Business-Id": str(biz_id("glow-studio"))}
    f = client.post("/api/settings/faq", json={"topic": "Kids", "keywords": "kids children child", "answer_en": "Kids haircut is ₹249."}, headers=h).json()
    assert "₹249" in sim(client, "do you cut children's hair", biz_id("glow-studio"))["reply"]
    client.put(f"/api/settings/faq/{f['id']}", json={"answer_en": "Kids haircut is ₹299."}, headers=h)
    assert "₹299" in sim(client, "kids haircut?", biz_id("glow-studio"), phone="+910000000203")["reply"]
    m = client.post("/api/settings/menu", json={"name": "Beard trim", "price": 199, "category": "Hair", "aliases": "beard, shave"}, headers=h).json()
    assert json.loads(m["aliases"]) == ["beard", "shave"]
    assert client.delete(f"/api/settings/menu/{m['id']}", headers=h).json()["ok"]
    assert client.delete(f"/api/settings/menu/{m['id']}", headers=h).status_code == 404
    assert client.post("/api/settings/slots/generate", json={"days": 2, "hours": [9]}, headers=h).json()["added"] == 2
    s = client.get("/api/settings", headers=h).json()
    assert s["business"]["name"] == "Glow Studio Salon" and "wa_token" not in s["business"]
    client.put("/api/settings/business", json={"wa_token": "secret-tok", "phone_number_id": "777"}, headers=h)
    s = client.get("/api/settings", headers=h).json()["business"]
    assert s["has_token"] and s["live"] and "secret-tok" not in json.dumps(s)
    assert client.post("/api/settings/templates", json={"name": "Bad Name!"}, headers=h).status_code == 400
    assert client.get("/api/settings", headers={}).status_code == 200


# ---------- templates / 24h window ----------
def _age_conversation(cid):
    db.x("UPDATE messages SET created_at=datetime('now','-2 days') WHERE conversation_id=?", (cid,))


def test_reminder_uses_template_outside_24h(client):
    sim(client, "book a table", tenants.default()["id"], phone="+910000000210")
    sim(client, "1", tenants.default()["id"], phone="+910000000210")
    sim(client, "2", tenants.default()["id"], phone="+910000000210")
    bk = [b for b in client.get("/api/bookings").json() if b["phone"] == "+910000000210"][0]
    assert client.post(f"/api/bookings/{bk['id']}/remind").json()["via"] == "text"
    _age_conversation(bk["conversation_id"])
    r = client.post(f"/api/bookings/{bk['id']}/remind").json()
    assert r["via"] == "template" and r["template"] == "booking_reminder"
    last = db.q("SELECT text FROM outbox ORDER BY id DESC LIMIT 1", one=True)["text"]
    assert last.startswith("[template booking_reminder]") and bk["code"] in last
    # owner free text is blocked outside the window
    assert client.post(f"/api/conversations/{bk['conversation_id']}/reply", json={"text": "hi"}).status_code == 409


def test_broadcast_outside_window_needs_template_and_approval(client):
    for c in client.get("/api/conversations").json():
        _age_conversation(c["id"])
    b = client.post("/api/broadcasts", json={"title": "Plain", "body": "hello"}).json()
    sent = client.post(f"/api/broadcasts/{b['id']}/approve").json()
    assert sent["recipients"] == 0 and sent["skipped"] > 0
    tpl = db.q("SELECT id FROM templates WHERE name='weekend_offer'", one=True)["id"]
    b = client.post("/api/broadcasts", json={"title": "Offer", "body": "15% off", "template_id": tpl}).json()
    assert b["status"] == "pending_approval"
    before = db.q("SELECT COUNT(*) n FROM outbox", one=True)["n"]
    assert db.q("SELECT COUNT(*) n FROM outbox", one=True)["n"] == before  # nothing sent before approval
    sent = client.post(f"/api/broadcasts/{b['id']}/approve").json()
    assert sent["recipients"] > 0 and sent["skipped"] == 0


# ---------- payments ----------
def order(c, bid=None, phone="+910000000220"):
    bid = bid or tenants.default()["id"]
    sim(c, "2 masala dosa", bid, phone); sim(c, "confirm", bid, phone)
    return sim(c, "pickup", bid, phone)


def test_upi_link_when_no_razorpay(client):
    r = order(client)
    assert "upi://pay?pa=spiceroute.demo@upi" in r["reply"] and "am=298.00" in r["reply"]
    o = [o for o in client.get("/api/orders").json() if o["phone"] == "+910000000220"][0]
    assert o["payment_provider"] == "upi" and o["payment_status"] == "unpaid"
    assert client.post(f"/api/orders/{o['id']}/paid").json()["payment_status"] == "paid"


def test_no_link_without_upi_or_razorpay(client):
    db.x("UPDATE businesses SET upi_id='' WHERE id=?", (tenants.default()["id"],))
    assert "upi://" not in order(client, phone="+910000000221")["reply"]


def razorpay_event(link_id, order_id=None):
    return {"event": "payment_link.paid", "payload": {
        "payment_link": {"entity": {"id": link_id, "status": "paid", "notes": {"order_id": str(order_id or "")}}},
        "payment": {"entity": {"id": "pay_ABC", "amount": 29800, "status": "captured"}}}}


def test_razorpay_link_and_signed_webhook(client, monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_x"); monkeypatch.setenv("RAZORPAY_KEY_SECRET", "s")
    calls = []

    class R:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"id": "plink_123", "short_url": "https://rzp.io/i/abc"}
    monkeypatch.setattr(payments.httpx, "post", lambda url, **kw: calls.append((url, kw)) or R())
    r = order(client, phone="+910000000222")
    assert "https://rzp.io/i/abc" in r["reply"]
    url, kw = calls[0]
    assert url.endswith("/payment_links") and kw["json"]["amount"] == 29800 and kw["auth"] == ("rzp_test_x", "s")

    raw = json.dumps(razorpay_event("plink_123")).encode()
    hook = "/api/payments/razorpay/webhook"
    assert client.post(hook, content=raw).status_code == 503  # refuses when the webhook secret isn't configured
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "whsec")
    assert client.post(hook, content=raw, headers={"X-Razorpay-Signature": "bad"}).status_code == 401
    sig = hmac.new(b"whsec", raw, hashlib.sha256).hexdigest()
    client.cookies.clear()  # webhook is public: works without a dashboard session
    r = client.post(hook, content=raw, headers={"X-Razorpay-Signature": sig}).json()
    assert r["matched"]
    o = db.q("SELECT * FROM orders WHERE id=?", (r["order_id"],), one=True)
    assert o["payment_status"] == "paid" and o["payment_ref"] == "pay_ABC"
    n = db.q("SELECT COUNT(*) n FROM outbox WHERE text LIKE '%Payment of%'", one=True)["n"]
    client.post(hook, content=raw, headers={"X-Razorpay-Signature": sig})  # Razorpay retry: no second thank-you
    assert db.q("SELECT COUNT(*) n FROM outbox WHERE text LIKE '%Payment of%'", one=True)["n"] == n == 1


# ---------- analytics ----------
def test_analytics(client):
    a = client.get("/api/analytics").json()
    assert a["chats"] >= 4 and a["orders"] >= 1 and a["revenue"] > 0 and a["leads"] >= 1 and a["handoffs"] >= 1
    assert len(a["busy_hours"]) == 24 and sum(h["messages"] for h in a["busy_hours"]) == a["messages_in"]
    assert len(a["daily"]) == 14
    sim(client, "qwerty asdfgh zxcvb", tenants.default()["id"], phone="+910000000230")
    assert client.get("/api/analytics").json()["missed"] == a["missed"] + 1


# ---------- upgrade from the v1 single-business database ----------
V1 = """CREATE TABLE conversations(id INTEGER PRIMARY KEY, phone TEXT UNIQUE, name TEXT, lang TEXT DEFAULT 'en',
  state TEXT DEFAULT '{}', needs_human INTEGER DEFAULT 0, handoff_reason TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE messages(id INTEGER PRIMARY KEY, conversation_id INTEGER, direction TEXT, sender TEXT, text TEXT, intent TEXT, lang TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE menu(id INTEGER PRIMARY KEY, name TEXT, price INTEGER, category TEXT, aliases TEXT);
CREATE TABLE orders(id INTEGER PRIMARY KEY, conversation_id INTEGER, items TEXT, total INTEGER, fulfilment TEXT, status TEXT DEFAULT 'new', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE outbox(id INTEGER PRIMARY KEY, phone TEXT, text TEXT, mode TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
INSERT INTO conversations(phone,name) VALUES('+919000000001','Live Customer');
INSERT INTO messages(conversation_id,direction,sender,text) VALUES(1,'in','customer','hello');
INSERT INTO menu(name,price,category,aliases) VALUES('Idli',40,'Breakfast','["idli"]');
INSERT INTO orders(conversation_id,items,total,fulfilment) VALUES(1,'[]',40,'Pickup');"""


def test_upgrade_from_v1_database(tmp_path, monkeypatch):
    p = tmp_path / "v1.db"
    con = sqlite3.connect(p); con.executescript(V1); con.close()
    monkeypatch.setenv("DB_PATH", str(p))
    from app import seed, engine
    seed.seed()
    assert db.q("SELECT name FROM businesses WHERE id=1", one=True)["name"] == "Spice Route Kitchen"
    assert db.q("SELECT upi_id FROM businesses WHERE id=1", one=True)["upi_id"] == ""  # no demo UPI on a live install
    assert db.q("SELECT business_id FROM conversations WHERE phone='+919000000001'", one=True)["business_id"] == 1
    assert [m["name"] for m in engine.menu_items(1)] == ["Idli"]  # existing menu kept, not overwritten
    assert engine.handle_message("+919000000001", None, "2 idli")["reply"].count("₹80") == 2
    assert db.q("SELECT COUNT(*) n FROM businesses", one=True)["n"] == 3
