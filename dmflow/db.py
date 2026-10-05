"""
Storage. One small layer, two engines.

Production runs on PostgreSQL (DATABASE_URL, set by Railway). A laptop with no
DATABASE_URL runs on a SQLite file, so the whole product can be started and
tested with nothing installed. SQL is written once, with `?` placeholders, in
the subset both engines understand.

Every table is prefixed `dm_` so this sits beside the old app's tables in the
same database without touching them.
"""

import json
import os
import sqlite3
import threading
import time
import uuid
from typing import Any, Dict, Iterable, List, Optional

DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip()
SQLITE_PATH = os.environ.get("DMFLOW_SQLITE",
                             os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                          "data", "dmflow.db"))

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS dm_users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL DEFAULT '',
        password_hash TEXT NOT NULL DEFAULT '',
        role TEXT NOT NULL DEFAULT 'customer',
        status TEXT NOT NULL DEFAULT 'active',
        plan TEXT NOT NULL DEFAULT 'free',
        is_lifetime INTEGER NOT NULL DEFAULT 0,
        plan_expires_at BIGINT NOT NULL DEFAULT 0,
        notes TEXT NOT NULL DEFAULT '',
        created_at BIGINT NOT NULL DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS dm_sessions (
        token_hash TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        expires_at BIGINT NOT NULL)""",
    # One Instagram account per workspace. `ig_user_id` is the professional
    # account id Meta puts in every webhook (entry.id) - it is how an event
    # finds its owner, so it is indexed.
    """CREATE TABLE IF NOT EXISTS dm_ig (
        user_id TEXT PRIMARY KEY,
        ig_user_id TEXT NOT NULL DEFAULT '',
        app_user_id TEXT NOT NULL DEFAULT '',
        username TEXT NOT NULL DEFAULT '',
        name TEXT NOT NULL DEFAULT '',
        picture TEXT NOT NULL DEFAULT '',
        followers BIGINT NOT NULL DEFAULT 0,
        media_count BIGINT NOT NULL DEFAULT 0,
        account_type TEXT NOT NULL DEFAULT '',
        token TEXT NOT NULL DEFAULT '',
        token_expires BIGINT NOT NULL DEFAULT 0,
        connected_at BIGINT NOT NULL DEFAULT 0,
        checked_at BIGINT NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'connected',
        status_note TEXT NOT NULL DEFAULT '')""",
    "CREATE INDEX IF NOT EXISTS dm_ig_igid ON dm_ig (ig_user_id)",
    # A flow's whole configuration lives in `body` (JSON). The columns are only
    # what gets queried.
    """CREATE TABLE IF NOT EXISTS dm_flows (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'draft',
        body TEXT NOT NULL DEFAULT '{}',
        created_at BIGINT NOT NULL DEFAULT 0,
        updated_at BIGINT NOT NULL DEFAULT 0)""",
    "CREATE INDEX IF NOT EXISTS dm_flows_user ON dm_flows (user_id)",
    """CREATE TABLE IF NOT EXISTS dm_contacts (
        user_id TEXT NOT NULL,
        ig_id TEXT NOT NULL,
        username TEXT NOT NULL DEFAULT '',
        flow_id TEXT NOT NULL DEFAULT '',
        follows INTEGER NOT NULL DEFAULT 0,
        link_sent INTEGER NOT NULL DEFAULT 0,
        first_seen BIGINT NOT NULL DEFAULT 0,
        last_seen BIGINT NOT NULL DEFAULT 0,
        last_text TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (user_id, ig_id))""",
    """CREATE TABLE IF NOT EXISTS dm_events (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL DEFAULT '',
        at BIGINT NOT NULL,
        source TEXT NOT NULL DEFAULT '',
        kind TEXT NOT NULL DEFAULT '',
        flow_id TEXT NOT NULL DEFAULT '',
        username TEXT NOT NULL DEFAULT '',
        text TEXT NOT NULL DEFAULT '',
        verdict TEXT NOT NULL DEFAULT '',
        note TEXT NOT NULL DEFAULT '')""",
    "CREATE INDEX IF NOT EXISTS dm_events_user_at ON dm_events (user_id, at)",
    # Whoever claims a comment id first - webhook or poller - answers it.
    """CREATE TABLE IF NOT EXISTS dm_handled (
        comment_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL DEFAULT '',
        at BIGINT NOT NULL DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS dm_poll (
        user_id TEXT NOT NULL,
        media_id TEXT NOT NULL,
        primed_at BIGINT NOT NULL DEFAULT 0,
        PRIMARY KEY (user_id, media_id))""",
    """CREATE TABLE IF NOT EXISTS dm_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL DEFAULT '')""",
    # Customer support tickets
    """CREATE TABLE IF NOT EXISTS dm_tickets (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        user_email TEXT NOT NULL DEFAULT '',
        user_name TEXT NOT NULL DEFAULT '',
        subject TEXT NOT NULL DEFAULT '',
        category TEXT NOT NULL DEFAULT 'general',
        priority TEXT NOT NULL DEFAULT 'medium',
        status TEXT NOT NULL DEFAULT 'open',
        created_at BIGINT NOT NULL DEFAULT 0,
        updated_at BIGINT NOT NULL DEFAULT 0)""",
    "CREATE INDEX IF NOT EXISTS dm_tickets_user ON dm_tickets (user_id)",
    "CREATE INDEX IF NOT EXISTS dm_tickets_status ON dm_tickets (status)",
    # Ticket conversation messages
    """CREATE TABLE IF NOT EXISTS dm_ticket_messages (
        id TEXT PRIMARY KEY,
        ticket_id TEXT NOT NULL,
        sender_role TEXT NOT NULL DEFAULT 'customer',
        sender_id TEXT NOT NULL DEFAULT '',
        sender_name TEXT NOT NULL DEFAULT '',
        message TEXT NOT NULL DEFAULT '',
        created_at BIGINT NOT NULL DEFAULT 0)""",
    "CREATE INDEX IF NOT EXISTS dm_ticket_msgs_ticket ON dm_ticket_messages (ticket_id)",
    # Promotional offers & coupon codes
    """CREATE TABLE IF NOT EXISTS dm_offers (
        id TEXT PRIMARY KEY,
        code TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        discount_type TEXT NOT NULL DEFAULT 'percentage',
        discount_val REAL NOT NULL DEFAULT 0,
        applicable_plans TEXT NOT NULL DEFAULT 'all',
        max_uses INTEGER NOT NULL DEFAULT -1,
        used_count INTEGER NOT NULL DEFAULT 0,
        valid_until BIGINT NOT NULL DEFAULT 0,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at BIGINT NOT NULL DEFAULT 0)""",
    "CREATE INDEX IF NOT EXISTS dm_offers_code ON dm_offers (code)",
]


def now() -> int:
    return int(time.time())


def new_id(prefix: str = "") -> str:
    return prefix + uuid.uuid4().hex[:16]


class _Sqlite:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError:
            pass  # some shared/network folders cannot do WAL; default journal still works
        self.lock = threading.RLock()

    def execute(self, sql: str, params: Iterable = ()) -> int:
        with self.lock:
            cur = self.conn.execute(sql, tuple(params))
            return cur.rowcount

    def query(self, sql: str, params: Iterable = ()) -> List[Dict[str, Any]]:
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, tuple(params)).fetchall()]


class _Postgres:
    def __init__(self, url: str):
        from psycopg_pool import ConnectionPool
        from psycopg.rows import dict_row
        self.pool = ConnectionPool(url, min_size=1, max_size=8,
                                   kwargs={"autocommit": True, "row_factory": dict_row})

    @staticmethod
    def _sql(sql: str) -> str:
        # psycopg reads every % as the start of a placeholder, so a literal one
        # (LIKE 'x%') must be doubled before ? becomes %s - otherwise a query
        # that works on SQLite crashes only in production.
        return sql.replace("%", "%%").replace("?", "%s")

    def execute(self, sql: str, params: Iterable = ()) -> int:
        with self.pool.connection() as c:
            cur = c.execute(self._sql(sql), tuple(params))
            return cur.rowcount

    def query(self, sql: str, params: Iterable = ()) -> List[Dict[str, Any]]:
        with self.pool.connection() as c:
            return list(c.execute(self._sql(sql), tuple(params)).fetchall())


_engine = None
_lock = threading.Lock()


def _ensure_migrations(eng) -> None:
    # Ensure columns exist on dm_users if table already existed prior
    for col, col_type in (("is_lifetime", "INTEGER NOT NULL DEFAULT 0"),
                          ("plan_expires_at", "BIGINT NOT NULL DEFAULT 0"),
                          ("notes", "TEXT NOT NULL DEFAULT ''")):
        try:
            eng.execute(f"ALTER TABLE dm_users ADD COLUMN {col} {col_type}")
        except Exception:
            pass


def engine():
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                _engine = _Postgres(DATABASE_URL) if DATABASE_URL else _Sqlite(SQLITE_PATH)
                for stmt in SCHEMA:
                    try:
                        _engine.execute(stmt)
                    except Exception:
                        pass
                _ensure_migrations(_engine)
    return _engine


def is_postgres() -> bool:
    return bool(DATABASE_URL)


def execute(sql: str, params: Iterable = ()) -> int:
    return engine().execute(sql, params)


def query(sql: str, params: Iterable = ()) -> List[Dict[str, Any]]:
    return engine().query(sql, params)


def one(sql: str, params: Iterable = ()) -> Optional[Dict[str, Any]]:
    rows = query(sql, params)
    return rows[0] if rows else None


def jload(text: Any, default: Any = None) -> Any:
    try:
        return json.loads(text) if isinstance(text, str) and text else (default if text in (None, "") else text)
    except Exception:
        return default


def jdump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
