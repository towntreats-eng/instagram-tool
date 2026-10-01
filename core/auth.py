"""
Authentication and authorisation.

What this replaces: `current_workspace()` used to return `users[0]` — the first
account in the file — for every request, from anyone. The login screen checked
a password and then set nothing, so it decided nothing. And all thirty
/api/admin/* routes were open to any visitor who typed the URL.

How it works now:
  * Signing in mints a 32-byte random token. The browser gets it in an
    HttpOnly, SameSite=Lax cookie; the server stores only its SHA-256, so a
    database leak does not hand over live sessions.
  * Every request resolves its own workspace from that cookie. There is no
    ambient "current user" any more.
  * Admin routes require role == "admin". A customer who finds the URL gets a
    403, not a control panel.

Passwords move to PBKDF2-HMAC-SHA256 at 240,000 iterations. The old scheme was
a single round of SHA-256, which a GPU tries in the billions per second. Old
hashes still verify and are transparently re-hashed the next time that person
signs in, so nobody is locked out by the upgrade.
"""

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from core import db, store

SESSION_COOKIE = "cf_session"
SESSION_DAYS = 14
PBKDF2_ROUNDS = 240_000
SESSIONS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sessions.json")


# ------------------------------------------------------------------ passwords
def hash_password(raw: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", raw.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS)
    return f"pbkdf2${PBKDF2_ROUNDS}${salt}${dk.hex()}"


def verify_password(raw: str, stored: str) -> Tuple[bool, bool]:
    """Returns (ok, needs_rehash). Legacy hashes verify but ask to be upgraded."""
    if not stored:
        return False, False
    if stored.startswith("pbkdf2$"):
        try:
            _, rounds, salt, want = stored.split("$", 3)
            dk = hashlib.pbkdf2_hmac("sha256", raw.encode("utf-8"), salt.encode("utf-8"), int(rounds))
            return hmac.compare_digest(dk.hex(), want), int(rounds) < PBKDF2_ROUNDS
        except Exception:
            return False, False
    # Legacy: salt$sha256(salt + raw)
    if "$" in stored:
        salt, want = stored.split("$", 1)
        got = hashlib.sha256((salt + raw).encode("utf-8")).hexdigest()
        return hmac.compare_digest(got, want), True
    return False, False


# ------------------------------------------------------------------- sessions
def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _file_sessions() -> Dict[str, Any]:
    return store.read(SESSIONS_FILE, {}) or {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def start_session(user: Dict[str, Any], user_agent: str = "", ip: str = "") -> Tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    th = _token_hash(token)
    expires = _now() + timedelta(days=SESSION_DAYS)
    role = "admin" if user.get("role") == "admin" else "owner"

    if store.using_postgres():
        try:
            db.session_create(th, user["id"], role, expires, user_agent, ip)
            return token, expires
        except Exception as exc:
            print(f"[auth] Postgres session write failed, using file store: {exc}")

    sessions = _file_sessions()
    sessions[th] = {"user_id": user["id"], "role": role,
                    "expires_at": expires.isoformat(), "created_at": _now().isoformat()}
    # Opportunistic cleanup so the file cannot grow without bound.
    sessions = {k: v for k, v in sessions.items()
                if v.get("expires_at", "") > _now().isoformat()}
    store.write(SESSIONS_FILE, sessions)
    return token, expires


def read_session(token: Optional[str]) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    th = _token_hash(token)
    if store.using_postgres():
        try:
            return db.session_get(th)
        except Exception as exc:
            print(f"[auth] Postgres session read failed, using file store: {exc}")
    row = _file_sessions().get(th)
    if not row:
        return None
    if row.get("expires_at", "") <= _now().isoformat():
        return None
    return {"user_id": row["user_id"], "role": row.get("role", "owner")}


def end_session(token: Optional[str]) -> None:
    if not token:
        return
    th = _token_hash(token)
    if store.using_postgres():
        try:
            db.session_delete(th)
            return
        except Exception:
            pass
    sessions = _file_sessions()
    if sessions.pop(th, None) is not None:
        store.write(SESSIONS_FILE, sessions)


def end_all_sessions(user_id: str) -> None:
    """Called when an account is suspended or its password changes."""
    if store.using_postgres():
        try:
            db.session_delete_for_user(user_id)
            return
        except Exception:
            pass
    sessions = _file_sessions()
    keep = {k: v for k, v in sessions.items() if v.get("user_id") != user_id}
    if len(keep) != len(sessions):
        store.write(SESSIONS_FILE, keep)


# ----------------------------------------------------------------- audit trail
AUDIT_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "audit.json")


def audit(actor: Optional[Dict[str, Any]], action: str, subject_id: str = "",
          old_value: Any = None, new_value: Any = None, note: str = "") -> None:
    actor_id = (actor or {}).get("id", "system")
    actor_email = (actor or {}).get("email", "")
    if store.using_postgres():
        try:
            db.audit_write(actor_id, actor_email, action, subject_id, old_value, new_value, note)
            return
        except Exception as exc:
            print(f"[auth] Postgres audit write failed, using file store: {exc}")
    rows = store.read(AUDIT_FILE, []) or []
    rows.insert(0, {"at": _now().isoformat(), "actor_id": actor_id, "actor_email": actor_email,
                    "action": action, "subject_id": subject_id, "old_value": old_value,
                    "new_value": new_value, "note": note})
    store.write(AUDIT_FILE, rows[:5000])


def audit_read(limit: int = 200, subject_id: str = "") -> list:
    if store.using_postgres():
        try:
            return db.audit_read(limit, subject_id)
        except Exception:
            pass
    rows = store.read(AUDIT_FILE, []) or []
    if subject_id:
        rows = [r for r in rows if r.get("subject_id") == subject_id]
    return rows[:limit]
