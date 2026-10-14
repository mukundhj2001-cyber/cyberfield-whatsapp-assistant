"""SQLite helpers. One file DB, path configurable via DB_PATH."""
import json, os, sqlite3, threading
from pathlib import Path

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations(id INTEGER PRIMARY KEY, phone TEXT UNIQUE, name TEXT, lang TEXT DEFAULT 'en',
  state TEXT DEFAULT '{}', needs_human INTEGER DEFAULT 0, handoff_reason TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, conversation_id INTEGER, direction TEXT, sender TEXT, text TEXT,
  intent TEXT, lang TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS menu(id INTEGER PRIMARY KEY, name TEXT, price INTEGER, category TEXT, aliases TEXT);
CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, conversation_id INTEGER, items TEXT, total INTEGER, fulfilment TEXT,
  status TEXT DEFAULT 'new', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS slots(id INTEGER PRIMARY KEY, starts_at TEXT, capacity INTEGER DEFAULT 1, booked INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS bookings(id INTEGER PRIMARY KEY, conversation_id INTEGER, slot_id INTEGER, party_size INTEGER,
  code TEXT, status TEXT DEFAULT 'confirmed', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS leads(id INTEGER PRIMARY KEY, conversation_id INTEGER, name TEXT, contact TEXT, interest TEXT,
  status TEXT DEFAULT 'new', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS faq(id INTEGER PRIMARY KEY, topic TEXT, keywords TEXT, answer_en TEXT, answer_hi TEXT, answer_ta TEXT);
CREATE TABLE IF NOT EXISTS broadcasts(id INTEGER PRIMARY KEY, title TEXT, body TEXT, audience TEXT, status TEXT DEFAULT 'pending_approval',
  approved_by TEXT, recipients INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP, sent_at TEXT);
CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY, phone TEXT, text TEXT, mode TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""


def db_path() -> str:
    return os.environ.get("DB_PATH", str(Path(__file__).resolve().parents[2] / "data" / "assistant.db"))


def connect() -> sqlite3.Connection:
    p = db_path()
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init():
    with _lock, connect() as con:
        con.executescript(SCHEMA)


def q(sql, args=(), one=False):
    with _lock, connect() as con:
        rows = [dict(r) for r in con.execute(sql, args).fetchall()]
    return (rows[0] if rows else None) if one else rows


def x(sql, args=()) -> int:
    with _lock, connect() as con:
        cur = con.execute(sql, args)
        con.commit()
        return cur.lastrowid


def jload(s, default=None):
    try:
        return json.loads(s) if s else default
    except Exception:
        return default
