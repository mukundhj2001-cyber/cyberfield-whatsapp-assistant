"""SQLite helpers. One file DB, path configurable via DB_PATH."""
import json, os, sqlite3, threading
from pathlib import Path

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS businesses(id INTEGER PRIMARY KEY, slug TEXT UNIQUE, name TEXT, kind TEXT DEFAULT 'restaurant',
  tagline TEXT, phone_number_id TEXT UNIQUE, wa_token TEXT, upi_id TEXT, hours TEXT DEFAULT '{}', languages TEXT DEFAULT '["en","hi","ta"]',
  default_lang TEXT DEFAULT 'en', orders_enabled INTEGER DEFAULT 1, code_prefix TEXT DEFAULT 'BK', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS conversations(id INTEGER PRIMARY KEY, business_id INTEGER DEFAULT 1, phone TEXT, name TEXT, lang TEXT DEFAULT 'en',
  state TEXT DEFAULT '{}', needs_human INTEGER DEFAULT 0, handoff_reason TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(business_id, phone));
CREATE TABLE IF NOT EXISTS templates(id INTEGER PRIMARY KEY, business_id INTEGER DEFAULT 1, name TEXT, language TEXT DEFAULT 'en',
  category TEXT DEFAULT 'UTILITY', purpose TEXT DEFAULT 'other', body TEXT, param_count INTEGER DEFAULT 0,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
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
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS processed_messages(wa_id TEXT PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS message_status(id INTEGER PRIMARY KEY, wa_message_id TEXT, status TEXT, recipient TEXT, error TEXT,
  ts TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS ix_status_wamid ON message_status(wa_message_id);
"""

# Columns added after v1. Existing databases are upgraded in place on startup.
COLUMNS = {
    "outbox": {"wa_message_id": "TEXT", "status": "TEXT", "error": "TEXT", "attempts": "INTEGER DEFAULT 0", "business_id": "INTEGER DEFAULT 1"},
    "menu": {"business_id": "INTEGER DEFAULT 1"},
    "faq": {"business_id": "INTEGER DEFAULT 1"},
    "slots": {"business_id": "INTEGER DEFAULT 1"},
    "orders": {"business_id": "INTEGER DEFAULT 1", "payment_status": "TEXT DEFAULT 'unpaid'", "payment_provider": "TEXT",
               "payment_link": "TEXT", "payment_link_id": "TEXT", "payment_ref": "TEXT", "paid_at": "TEXT"},
    "bookings": {"business_id": "INTEGER DEFAULT 1", "service": "TEXT", "reminded_at": "TEXT"},
    "leads": {"business_id": "INTEGER DEFAULT 1"},
    "broadcasts": {"business_id": "INTEGER DEFAULT 1", "template_id": "INTEGER", "skipped": "INTEGER DEFAULT 0"},
}


def db_path() -> str:
    return (os.environ.get("DB_PATH") or str(Path(__file__).resolve().parents[2] / "data" / "assistant.db"))


def connect() -> sqlite3.Connection:
    p = db_path()
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init():
    with _lock, connect() as con:
        con.executescript(SCHEMA)
        migrate(con)


def migrate(con):
    # v1 had conversations.phone UNIQUE; multi-tenant needs UNIQUE(business_id, phone). SQLite can't drop a constraint, so rebuild.
    sql = (con.execute("SELECT sql FROM sqlite_master WHERE name='conversations'").fetchone() or [""])[0]
    if "phone TEXT UNIQUE" in sql:
        con.executescript("""
            ALTER TABLE conversations RENAME TO conversations_v1;
            CREATE TABLE conversations(id INTEGER PRIMARY KEY, business_id INTEGER DEFAULT 1, phone TEXT, name TEXT, lang TEXT DEFAULT 'en',
              state TEXT DEFAULT '{}', needs_human INTEGER DEFAULT 0, handoff_reason TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(business_id, phone));
            INSERT INTO conversations(id,business_id,phone,name,lang,state,needs_human,handoff_reason,updated_at)
              SELECT id,1,phone,name,lang,state,needs_human,handoff_reason,updated_at FROM conversations_v1;
            DROP TABLE conversations_v1;""")
    for table, cols in COLUMNS.items():
        have = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        for name, decl in cols.items():
            if name not in have:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
    con.executescript("""
        CREATE INDEX IF NOT EXISTS ix_msg_conv ON messages(conversation_id);
        CREATE INDEX IF NOT EXISTS ix_conv_biz ON conversations(business_id);
        CREATE INDEX IF NOT EXISTS ix_orders_biz ON orders(business_id);""")
    con.commit()


def q(sql, args=(), one=False):
    with _lock, connect() as con:
        rows = [dict(r) for r in con.execute(sql, args).fetchall()]
    return (rows[0] if rows else None) if one else rows


def x(sql, args=()) -> int:
    with _lock, connect() as con:
        cur = con.execute(sql, args)
        con.commit()
        return cur.lastrowid


def xc(sql, args=()) -> int:
    """Execute and return the number of affected rows."""
    with _lock, connect() as con:
        cur = con.execute(sql, args)
        con.commit()
        return cur.rowcount


def jload(s, default=None):
    try:
        return json.loads(s) if s else default
    except Exception:
        return default
