"""
Accounts and sessions.

Password hashes use the same format as the old app (pbkdf2$rounds$salt$hex),
so every existing login keeps working after the switch. Old single-round
hashes still verify and are upgraded on the next sign-in.
"""

import hashlib
import hmac
import os
import secrets
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException, Request

from dmflow import db

COOKIE = "dmf_session"
SESSION_DAYS = 14
ROUNDS = 240_000
COOKIE_SECURE = (os.environ.get("COOKIE_SECURE", "1") or "1").strip() not in ("0", "false", "no")


def hash_password(raw: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", raw.encode(), salt.encode(), ROUNDS)
    return f"pbkdf2${ROUNDS}${salt}${dk.hex()}"


def verify_password(raw: str, stored: str) -> Tuple[bool, bool]:
    """(matches, should_rehash)"""
    if not stored:
        return False, False
    if stored.startswith("pbkdf2$"):
        try:
            _, rounds, salt, want = stored.split("$", 3)
            dk = hashlib.pbkdf2_hmac("sha256", raw.encode(), salt.encode(), int(rounds))
            return hmac.compare_digest(dk.hex(), want), int(rounds) < ROUNDS
        except Exception:
            return False, False
    if "$" in stored:  # legacy salt$sha256(salt+raw)
        salt, want = stored.split("$", 1)
        got = hashlib.sha256((salt + raw).encode()).hexdigest()
        return hmac.compare_digest(got, want), True
    return False, False


def _th(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    db.execute("INSERT INTO dm_sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
               (_th(token), user_id, db.now() + SESSION_DAYS * 86400))
    return token


def end_session(token: Optional[str]) -> None:
    if token:
        db.execute("DELETE FROM dm_sessions WHERE token_hash = ?", (_th(token),))


def end_all_sessions(user_id: str) -> None:
    db.execute("DELETE FROM dm_sessions WHERE user_id = ?", (user_id,))


def set_cookie(response, token: str) -> None:
    response.set_cookie(COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True,
                        samesite="lax", secure=COOKIE_SECURE, path="/")


def clear_cookie(response) -> None:
    response.delete_cookie(COOKIE, path="/")


def user_from_request(request: Request) -> Optional[Dict[str, Any]]:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    row = db.one("SELECT u.* FROM dm_sessions s JOIN dm_users u ON u.id = s.user_id "
                 "WHERE s.token_hash = ? AND s.expires_at > ?", (_th(token), db.now()))
    if not row or row.get("status") == "suspended":
        return None
    return row


def require_user(request: Request) -> Dict[str, Any]:
    user = user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return user


def require_admin(request: Request) -> Dict[str, Any]:
    user = require_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admins only.")
    return user


def public_user(u: Dict[str, Any]) -> Dict[str, Any]:
    return {k: u.get(k) for k in ("id", "email", "name", "role", "plan", "created_at")}


def create_user(name: str, email: str, password: str, role: str = "owner") -> Dict[str, Any]:
    email = (email or "").strip().lower()
    uid = db.new_id("u_")
    db.execute("INSERT INTO dm_users (id, email, name, password_hash, role, status, plan, created_at) "
               "VALUES (?, ?, ?, ?, ?, 'active', 'free', ?)",
               (uid, email, (name or "").strip(), hash_password(password), role, db.now()))
    return db.one("SELECT * FROM dm_users WHERE id = ?", (uid,))


def ensure_admin_from_env() -> None:
    """ADMIN_EMAIL + ADMIN_PASSWORD create (or promote) the first admin."""
    email = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD") or ""
    if not email:
        return
    row = db.one("SELECT id FROM dm_users WHERE email = ?", (email,))
    if row:
        db.execute("UPDATE dm_users SET role = 'admin' WHERE id = ?", (row["id"],))
    elif password:
        create_user("Admin", email, password, role="admin")
