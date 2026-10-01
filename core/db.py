"""
PostgreSQL connection and schema for ConverFlow.

Design decision worth stating plainly, because it is a staged migration and
not a full relational rewrite:

  * The collections the app already keeps as JSON documents (users, plans,
    settings, automations, contacts…) move into a `documents` table, one row
    per collection, written atomically. Every existing manager keeps its shape
    and its code; only the read/write primitive underneath it changes. That is
    why this lands without breaking eight working modules at once.

  * The things that are append-heavy and must be *queried* get real tables
    from the start — sessions and the audit log. Those were never going to work
    as a rewritten-whole-file blob.

Later phases promote contacts, conversations, messages and events to their own
tables. The document table is the bridge, not the destination.

With DATABASE_URL unset the whole module reports unavailable and the app keeps
using JSON files, so nothing breaks before Postgres is provisioned.
"""

import json
import os
import threading
from typing import Any, Dict, List, Optional, Tuple

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

_pool = None
_lock = threading.Lock()
_init_done = False
_last_error = ""


def _driver():
    try:
        import psycopg
        from psycopg_pool import ConnectionPool
        return psycopg, ConnectionPool
    except Exception:
        return None, None


def configured() -> bool:
    return bool(DATABASE_URL)


def available() -> bool:
    """True only when a real connection has been proven, not merely configured."""
    if not DATABASE_URL:
        return False
    try:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True
    except Exception as exc:
        global _last_error
        _last_error = str(exc)
        return False


def last_error() -> str:
    return _last_error


def connection():
    global _pool, _last_error
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    psycopg, ConnectionPool = _driver()
    if psycopg is None:
        raise RuntimeError("psycopg is not installed — add psycopg[binary] to requirements.txt")
    with _lock:
        if _pool is None:
            _pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=8, open=True,
                                   kwargs={"autocommit": True})
    return _pool.connection()


SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    name        TEXT PRIMARY KEY,
    body        JSONB NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash  TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'owner',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL,
    last_seen   TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_agent  TEXT DEFAULT '',
    ip          TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions (user_id);
CREATE INDEX IF NOT EXISTS sessions_expiry_idx ON sessions (expires_at);

CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_id    TEXT NOT NULL,
    actor_email TEXT NOT NULL DEFAULT '',
    action      TEXT NOT NULL,
    subject_id  TEXT NOT NULL DEFAULT '',
    old_value   JSONB,
    new_value   JSONB,
    note        TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS audit_at_idx ON audit_log (at DESC);
CREATE INDEX IF NOT EXISTS audit_subject_idx ON audit_log (subject_id);
"""


def init() -> Tuple[bool, str]:
    """Create the schema if it is not already there. Safe to call repeatedly."""
    global _init_done
    if not DATABASE_URL:
        return False, "DATABASE_URL is not set — running on JSON files."
    try:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA)
        _init_done = True
        return True, "Postgres ready."
    except Exception as exc:
        return False, f"Postgres is configured but unreachable: {exc}"


_init_attempted = False


def ensure_init() -> bool:
    """Initialise on first use, not on an app startup event.

    The managers (UserManager, PlansManager, …) are constructed at module
    import time, which happens BEFORE FastAPI fires @app.on_event("startup").
    When init only ran in that event, every manager had already read from an
    empty disk, seeded itself, and written that emptiness back over the live
    database. One lazy call removes the ordering problem entirely.
    """
    global _init_attempted
    if _init_done:
        return True
    if _init_attempted or not DATABASE_URL:
        return _init_done
    _init_attempted = True
    ok, msg = init()
    if not ok:
        print(f"[db] {msg}")
    return ok


def ready() -> bool:
    return _init_done


# ----------------------------------------------------------------- documents
def read_document(name: str) -> Optional[Any]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT body FROM documents WHERE name = %s", (name,))
            row = cur.fetchone()
    return row[0] if row else None


def write_document(name: str, body: Any) -> None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO documents (name, body, updated_at) VALUES (%s, %s, now()) "
                "ON CONFLICT (name) DO UPDATE SET body = EXCLUDED.body, updated_at = now()",
                (name, json.dumps(body, ensure_ascii=False)),
            )


def list_documents() -> List[Dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, updated_at, pg_column_size(body) FROM documents ORDER BY name")
            rows = cur.fetchall()
    return [{"name": r[0], "updated_at": r[1].isoformat(), "bytes": r[2]} for r in rows]


# ------------------------------------------------------------------ sessions
def session_create(token_hash: str, user_id: str, role: str, expires_at,
                   user_agent: str = "", ip: str = "") -> None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sessions (token_hash, user_id, role, expires_at, user_agent, ip) "
                "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (token_hash) DO NOTHING",
                (token_hash, user_id, role, expires_at, user_agent[:400], ip[:64]),
            )


def session_get(token_hash: str) -> Optional[Dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sessions SET last_seen = now() WHERE token_hash = %s AND expires_at > now() "
                "RETURNING user_id, role, expires_at",
                (token_hash,),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {"user_id": row[0], "role": row[1], "expires_at": row[2]}


def session_delete(token_hash: str) -> None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE token_hash = %s", (token_hash,))


def session_delete_for_user(user_id: str) -> None:
    """Used when an account is suspended or its password changes."""
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))


def session_purge_expired() -> int:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE expires_at < now()")
            return cur.rowcount


# ----------------------------------------------------------------- audit log
def audit_write(actor_id: str, actor_email: str, action: str, subject_id: str = "",
                old_value: Any = None, new_value: Any = None, note: str = "") -> None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO audit_log (actor_id, actor_email, action, subject_id, old_value, new_value, note) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (actor_id, actor_email, action, subject_id,
                 json.dumps(old_value) if old_value is not None else None,
                 json.dumps(new_value) if new_value is not None else None,
                 note),
            )


def audit_read(limit: int = 200, subject_id: str = "") -> List[Dict[str, Any]]:
    sql = ("SELECT at, actor_id, actor_email, action, subject_id, old_value, new_value, note "
           "FROM audit_log")
    args: List[Any] = []
    if subject_id:
        sql += " WHERE subject_id = %s"
        args.append(subject_id)
    sql += " ORDER BY at DESC LIMIT %s"
    args.append(min(int(limit), 1000))
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            rows = cur.fetchall()
    return [{"at": r[0].isoformat(), "actor_id": r[1], "actor_email": r[2], "action": r[3],
             "subject_id": r[4], "old_value": r[5], "new_value": r[6], "note": r[7]} for r in rows]
