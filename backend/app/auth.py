"""Dashboard login: ADMIN_USERNAME / ADMIN_PASSWORD from env, hashed with PBKDF2, signed session cookie.

If either variable is unset we fall back to the demo login admin / cyberfield and log a warning.
ADMIN_PASSWORD may be plain text or a precomputed hash: python -m app.auth "your-password"
"""
import base64, hashlib, hmac, os, secrets, sys, time
from . import db
from .logs import log_event

COOKIE = "cf_session"
MAX_AGE = 7 * 24 * 3600
DEMO_USER, DEMO_PASS = "admin", "cyberfield"
_ITER = 200_000
_cache: dict = {}
_warned = False


def make_hash(password: str, salt: str | None = None, iterations: int = _ITER) -> str:
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${h}"


def _check_hash(password: str, stored: str) -> bool:
    try:
        _, it, salt, h = stored.split("$")
    except ValueError:
        return False
    cand = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(it)).hex()
    return hmac.compare_digest(cand, h)


def demo_mode() -> bool:
    return not (os.environ.get("ADMIN_USERNAME") and os.environ.get("ADMIN_PASSWORD"))


def _credentials():
    """(username, password_hash). Plain-text passwords are hashed once in memory and never stored."""
    global _warned
    if demo_mode():
        if not _warned:
            log_event("auth_demo_credentials", "warning", hint="Set ADMIN_USERNAME and ADMIN_PASSWORD; using demo login admin/cyberfield")
            _warned = True
        user, raw = DEMO_USER, DEMO_PASS
    else:
        user, raw = os.environ["ADMIN_USERNAME"], os.environ["ADMIN_PASSWORD"]
    key = (user, hashlib.sha256(raw.encode()).hexdigest())
    if key not in _cache:
        _cache.clear()
        _cache[key] = raw if raw.startswith("pbkdf2_sha256$") else make_hash(raw)
    return user, _cache[key]


def verify(username: str, password: str) -> bool:
    user, h = _credentials()
    return hmac.compare_digest(username.encode(), user.encode()) & _check_hash(password, h)


def _secret() -> bytes:
    s = os.environ.get("SESSION_SECRET")
    if not s:  # persisted random secret so sessions survive restarts
        row = db.q("SELECT value FROM settings WHERE key='session_secret'", one=True)
        if not row:
            db.x("INSERT OR IGNORE INTO settings(key,value) VALUES('session_secret',?)", (secrets.token_hex(32),))
            row = db.q("SELECT value FROM settings WHERE key='session_secret'", one=True)
        s = row["value"]
    return s.encode()


def issue(username: str) -> str:
    body = base64.urlsafe_b64encode(f"{username}|{int(time.time()) + MAX_AGE}".encode()).decode()
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def check(token: str | None) -> str | None:
    """Return the username for a valid, unexpired session token."""
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()):
        return None
    try:
        user, exp = base64.urlsafe_b64decode(body.encode()).decode().rsplit("|", 1)
    except Exception:
        return None
    if int(exp) < time.time() or user != _credentials()[0]:
        return None
    return user


if __name__ == "__main__":
    print(make_hash(sys.argv[1] if len(sys.argv) > 1 else input("Password: ")))
