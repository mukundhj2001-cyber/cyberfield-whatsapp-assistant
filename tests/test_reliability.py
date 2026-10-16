import hashlib, hmac, json
import httpx
from app import auth, whatsapp


def payload(wamid="wamid.A1", text="menu", frm="919811100001"):
    return {"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"phone_number_id": "123"},
        "contacts": [{"profile": {"name": "Devi"}, "wa_id": frm}],
        "messages": [{"from": frm, "id": wamid, "timestamp": "1700000000", "type": "text", "text": {"body": text}}]}}]}]}


# ---------- login ----------
def test_dashboard_requires_login(anon):
    assert anon.get("/api/orders").status_code == 401
    assert anon.get("/api/health").status_code == 200
    assert anon.post("/api/simulate", json={"phone": "+911", "text": "hi"}).status_code == 200  # public demo chat
    assert anon.post("/api/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
    r = anon.post("/api/auth/login", json={"username": "admin", "password": "cyberfield"})
    assert r.status_code == 200 and r.json()["demo_credentials"] is True
    assert anon.get("/api/orders").status_code == 200
    anon.post("/api/auth/logout")
    anon.cookies.clear()
    assert anon.get("/api/orders").status_code == 401


def test_env_credentials_and_hash(anon, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "mukundh")
    monkeypatch.setenv("ADMIN_PASSWORD", auth.make_hash("s3cret!"))
    assert anon.post("/api/auth/login", json={"username": "admin", "password": "cyberfield"}).status_code == 401
    assert anon.post("/api/auth/login", json={"username": "mukundh", "password": "s3cret!"}).status_code == 200
    assert anon.get("/api/auth/me").json()["user"] == "mukundh"
    monkeypatch.setenv("ADMIN_PASSWORD", "plain-pass")  # plain text works too; old session (different creds hash) stays valid by username
    assert auth.verify("mukundh", "plain-pass") and not auth.verify("mukundh", "nope")


def test_tampered_session_rejected(anon):
    tok = auth.issue("admin")
    assert auth.check(tok) == "admin"
    assert auth.check(tok[:-2] + ("00" if not tok.endswith("00") else "11")) is None
    assert auth.check("garbage") is None


# ---------- signature ----------
def test_signature_check(client, monkeypatch):
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "app-secret")
    raw = json.dumps(payload("wamid.SIG")).encode()
    good = "sha256=" + hmac.new(b"app-secret", raw, hashlib.sha256).hexdigest()
    h = {"content-type": "application/json"}
    assert client.post("/webhook", content=raw, headers=h).status_code == 401
    assert client.post("/webhook", content=raw, headers={**h, "X-Hub-Signature-256": "sha256=deadbeef"}).status_code == 401
    r = client.post("/webhook", content=raw, headers={**h, "X-Hub-Signature-256": good})
    assert r.status_code == 200 and r.json()["processed"] == 1


def test_signature_skipped_without_secret(client):
    assert client.post("/webhook", json=payload("wamid.NOSIG")).status_code == 200


# ---------- idempotency + statuses ----------
def test_duplicate_message_ids_processed_once(client):
    first = client.post("/webhook", json=payload("wamid.DUP")).json()
    again = client.post("/webhook", json=payload("wamid.DUP")).json()
    assert first["processed"] == 1 and again["processed"] == 0 and again["duplicates"] == 1
    conv = [c for c in client.get("/api/conversations").json() if c["phone"] == "+919811100001"][0]
    msgs = client.get(f"/api/conversations/{conv['id']}/messages").json()
    assert len([m for m in msgs if m["direction"] == "in"]) == 1


def test_status_webhooks_stored(client):
    from app import db
    db.x("INSERT INTO outbox(phone,text,mode,wa_message_id,status) VALUES('+91','x','live','wamid.OUT1','sent')")
    for st in ("delivered", "read"):
        client.post("/webhook", json={"entry": [{"changes": [{"value": {"statuses": [
            {"id": "wamid.OUT1", "status": st, "timestamp": "1700000001", "recipient_id": "9198"}]}}]}]})
    r = client.post("/webhook", json={"entry": [{"changes": [{"value": {"statuses": [
        {"id": "wamid.OUT2", "status": "failed", "recipient_id": "9198", "errors": [{"code": 131047, "title": "Re-engagement message"}]}]}}]}]}).json()
    assert r["statuses"] == 1
    rows = db.q("SELECT status FROM message_status WHERE wa_message_id='wamid.OUT1' ORDER BY id")
    assert [x["status"] for x in rows] == ["delivered", "read"]
    assert db.q("SELECT status FROM outbox WHERE wa_message_id='wamid.OUT1'", one=True)["status"] == "read"
    assert "131047" in db.q("SELECT error FROM message_status WHERE wa_message_id='wamid.OUT2'", one=True)["error"]


# ---------- send retry ----------
class FakeResp:
    def __init__(self, code, data=None):
        self.status_code, self._d, self.text = code, data or {}, json.dumps(data or {})

    def json(self):
        return self._d


def test_send_retries_with_backoff(client, monkeypatch):
    calls = []

    def fake_post(url, **kw):
        calls.append(kw["json"])
        if len(calls) == 1:
            raise httpx.ConnectError("boom")
        if len(calls) == 2:
            return FakeResp(503)
        return FakeResp(200, {"messages": [{"id": "wamid.SENT"}]})

    monkeypatch.setattr(whatsapp.httpx, "post", fake_post)
    assert whatsapp.send_text("+919800000000", "hello", creds=("PNID", "TOKEN")) == "live"
    assert len(calls) == 3 and calls[0]["to"] == "919800000000"
    from app import db
    row = db.q("SELECT * FROM outbox ORDER BY id DESC LIMIT 1", one=True)
    assert row["wa_message_id"] == "wamid.SENT" and row["attempts"] == 3


def test_send_does_not_retry_client_errors(client, monkeypatch):
    calls = []
    monkeypatch.setattr(whatsapp.httpx, "post", lambda url, **kw: calls.append(1) or FakeResp(400, {"error": "bad"}))
    assert whatsapp.send_text("+919800000000", "hello", creds=("PNID", "TOKEN")) == "failed"
    assert len(calls) == 1
