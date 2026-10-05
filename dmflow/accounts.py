"""
The connected Instagram account, as a lifecycle.

  connect     OAuth code -> long-lived token -> /me -> subscribe -> saved
  status      asks Instagram, at most every few minutes. A name is shown only
              when Instagram itself just answered with it.
  disconnect  unsubscribes webhooks, asks Instagram to drop permissions,
              then deletes the token and everything cached from it.

A workspace has at most one account, and an Instagram account belongs to at
most one workspace - so an event can only ever reach its owner.
"""

import hashlib
import hmac
import secrets
import time
from typing import Any, Dict, Optional, Tuple

from dmflow import db, instagram, settings

STATE_TTL = 15 * 60
CHECK_EVERY = 5 * 60
REFRESH_WHEN_LEFT = 10 * 86400
BUSINESS_TYPES = {"BUSINESS", "MEDIA_CREATOR", "CREATOR"}


def _state_key() -> bytes:
    key = settings._raw("state_secret")
    if not key:
        key = secrets.token_hex(32)
        settings.put("state_secret", key)
    return key.encode()


def make_state(user_id: str) -> str:
    payload = f"{user_id}.{int(time.time())}"
    sig = hmac.new(_state_key(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{payload}.{sig}"


def read_state(state: str) -> Tuple[bool, str]:
    try:
        user_id, ts, sig = (state or "").rsplit(".", 2)
    except ValueError:
        return False, "That connect link is malformed. Start again from the dashboard."
    want = hmac.new(_state_key(), f"{user_id}.{ts}".encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, want):
        return False, "That connect link was not issued by DM Flow."
    if time.time() - int(ts) > STATE_TTL:
        return False, "That connect link expired. Start again from the dashboard."
    return True, user_id


def redirect_uri(base: str) -> str:
    return f"{base}/api/instagram/callback"  # already registered in Meta; must not move


def get(user_id: str) -> Optional[Dict[str, Any]]:
    return db.one("SELECT * FROM dm_ig WHERE user_id = ?", (user_id,))


def by_ig_id(ig_user_id: str) -> Optional[Dict[str, Any]]:
    if not ig_user_id:
        return None
    return db.one("SELECT * FROM dm_ig WHERE ig_user_id = ? OR app_user_id = ?",
                  (str(ig_user_id), str(ig_user_id)))


def public(row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """What the dashboard may see. Never the token. No name unless connected."""
    if not row:
        return {"connected": False}
    if row["status"] != "connected":
        return {"connected": False, "status": row["status"], "note": row["status_note"]}
    return {"connected": True, "status": "connected", "username": row["username"],
            "name": row["name"], "picture": row["picture"], "followers": row["followers"],
            "media_count": row["media_count"], "account_type": row["account_type"],
            "ig_user_id": row["ig_user_id"], "connected_at": row["connected_at"],
            "checked_at": row["checked_at"]}


def complete(code: str, state: str, base: str) -> Tuple[bool, str]:
    ok, user_id = read_state(state)
    if not ok:
        return False, user_id
    if not db.one("SELECT id FROM dm_users WHERE id = ?", (user_id,)):
        return False, "The workspace for this connection no longer exists."

    ok, short = instagram.exchange_code(code, redirect_uri(base))
    if not ok:
        return False, short
    ok, longt = instagram.long_lived(short["token"])
    token, expires = (longt["token"], int(time.time()) + longt["expires_in"]) if ok \
        else (short["token"], int(time.time()) + 3600)

    ok, me = instagram.profile(token)
    if not ok:
        return False, f"Connected, but Instagram would not describe the account: {me}"
    kind = (me.get("account_type") or "").upper()
    if kind and kind not in BUSINESS_TYPES:
        return False, (f"@{me.get('username')} is a personal account. Instagram only allows "
                       f"automated DMs from Business or Creator accounts - switch it in the "
                       f"Instagram app (Settings > Account type), then connect again.")
    ig_user_id = str(me.get("user_id") or me.get("id") or "")
    taken = db.one("SELECT user_id FROM dm_ig WHERE ig_user_id = ? AND user_id <> ?",
                   (ig_user_id, user_id))
    if taken:
        return False, (f"@{me.get('username')} is already connected to another DM Flow "
                       f"workspace. Disconnect it there first.")

    now = db.now()
    db.execute("DELETE FROM dm_ig WHERE user_id = ?", (user_id,))
    db.execute(
        "INSERT INTO dm_ig (user_id, ig_user_id, app_user_id, username, name, picture, followers, "
        "media_count, account_type, token, token_expires, connected_at, checked_at, status, status_note) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'connected', '')",
        (user_id, ig_user_id, str(me.get("id") or short.get("app_user_id") or ""),
         me.get("username") or "", me.get("name") or "", me.get("profile_picture_url") or "",
         int(me.get("followers_count") or 0), int(me.get("media_count") or 0), kind,
         token, expires, now, now))
    db.execute("DELETE FROM dm_poll WHERE user_id = ?", (user_id,))

    sub_ok, sub = instagram.subscribe(token)
    note = "" if sub_ok else f" (webhook subscription failed: {sub})"
    from dmflow import engine
    engine.log(user_id, "account", "connected", username=me.get("username") or "",
               note=f"Connected @{me.get('username')}{note}")
    return True, user_id


def status(user_id: str, force: bool = False) -> Dict[str, Any]:
    """Ask Instagram whether the connection is still real."""
    row = get(user_id)
    if not row:
        return {"connected": False}
    if not force and row["status"] == "connected" and db.now() - row["checked_at"] < CHECK_EVERY:
        return public(row)

    token = row["token"]
    if row["token_expires"] and row["token_expires"] - db.now() < REFRESH_WHEN_LEFT:
        ok, fresh = instagram.refresh(token)
        if ok:
            token = fresh["token"]
            db.execute("UPDATE dm_ig SET token = ?, token_expires = ? WHERE user_id = ?",
                       (token, db.now() + fresh["expires_in"], user_id))

    ok, me = instagram.profile(token)
    if ok:
        db.execute("UPDATE dm_ig SET username = ?, name = ?, picture = ?, followers = ?, media_count = ?, "
                   "account_type = ?, checked_at = ?, status = 'connected', status_note = '' WHERE user_id = ?",
                   (me.get("username") or row["username"], me.get("name") or "",
                    me.get("profile_picture_url") or "", int(me.get("followers_count") or 0),
                    int(me.get("media_count") or 0), (me.get("account_type") or "").upper(),
                    db.now(), user_id))
    else:
        db.execute("UPDATE dm_ig SET status = 'expired', status_note = ?, checked_at = ? WHERE user_id = ?",
                   (f"Instagram refused the saved token: {me}", db.now(), user_id))
    return public(get(user_id))


def disconnect(user_id: str) -> Dict[str, Any]:
    """Undo the connection on Instagram's side first, then ours."""
    row = get(user_id)
    report = {"was_connected": bool(row), "unsubscribed": None, "revoked": None}
    if row and row.get("token"):
        ok, out = instagram.unsubscribe(row["token"])
        report["unsubscribed"] = True if ok else str(out)
        ok, out = instagram.revoke(row["token"])
        report["revoked"] = True if ok else str(out)
    forget(user_id)
    from dmflow import engine
    engine.log(user_id, "account", "disconnected", username=(row or {}).get("username", ""),
               note=f"Disconnected. Webhooks: {report['unsubscribed']}. Revoke: {report['revoked']}.")
    return report


def forget(user_id: str) -> None:
    """Delete the token and everything learned with it. Flows are kept but
    paused, so reconnecting does not start sending on its own."""
    db.execute("DELETE FROM dm_ig WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM dm_poll WHERE user_id = ?", (user_id,))
    db.execute("UPDATE dm_flows SET status = 'paused' WHERE user_id = ? AND status = 'live'", (user_id,))
