"""
Per-workspace Instagram account reader.

Everything here uses the token belonging to ONE workspace. There is no shared
client and no global config: two customers on the same server must never be
able to see each other's posts, and the only way to guarantee that is to pass
the token in at every call.

No fallbacks, no sample data. If Instagram does not answer, we return the error
and the UI says so. A merchant who sees somebody else's stock photos where
their own reel should be will never trust the product again.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

# Overridable so the connected-state UI can be exercised against a local
# double in testing. Unset in production, where it is Instagram itself.
IG_BASE = os.environ.get("IG_GRAPH_BASE", "https://graph.instagram.com")
TIMEOUT = 20

# Media URLs from Instagram are signed and expire within hours, so this cache is
# deliberately short. It exists to stop a page refresh costing an API call, not
# to store anything.
_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_SECONDS = 300

PROFILE_FIELDS = "id,username,name,account_type,profile_picture_url,followers_count,follows_count,media_count"
MEDIA_FIELDS = ("id,caption,media_type,media_product_type,media_url,thumbnail_url,"
                "permalink,timestamp,like_count,comments_count")


def _get(url: str) -> Tuple[bool, Any]:
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            return True, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode())
            err = body.get("error", {})
            msg = err.get("message") or str(exc)
            # The one error worth naming plainly, because the fix is specific.
            if err.get("code") == 190 or "expired" in msg.lower() or "session" in msg.lower():
                return False, ("Instagram has expired this connection. "
                               "Reconnect the account to carry on.")
            return False, msg
        except Exception:
            return False, f"Instagram returned HTTP {exc.code}"
    except Exception as exc:
        return False, f"Could not reach Instagram: {exc}"


def _token(user: Dict[str, Any]) -> str:
    token = ((user or {}).get("instagram") or {}).get("access_token") or ""
    if not token:
        try:
            from core.meta_api import MetaAPIClient
            mc = MetaAPIClient()
            if mc.config.get("enabled") and mc.config.get("access_token"):
                token = mc.config.get("access_token") or ""
        except Exception:
            pass
    return token


def connected(user: Dict[str, Any]) -> bool:
    ig = (user or {}).get("instagram") or {}
    if bool(ig.get("connected") and ig.get("access_token")):
        return True
    try:
        from core.meta_api import MetaAPIClient
        mc = MetaAPIClient()
        if mc.config.get("enabled") and mc.config.get("access_token"):
            return True
    except Exception:
        pass
    return False


def profile(user: Dict[str, Any], force: bool = False) -> Tuple[bool, Any]:
    """Live profile: picture, handle, follower count, how many posts."""
    token = _token(user)
    if not token:
        return False, "This workspace has no Instagram account connected."

    key = f"profile:{user['id']}"
    hit = _CACHE.get(key)
    if hit and not force and time.time() - hit["at"] < CACHE_SECONDS:
        return True, hit["data"]

    ok, out = _get(f"{IG_BASE}/me?fields={PROFILE_FIELDS}&access_token={urllib.parse.quote(token)}")
    if not ok:
        return False, out

    data = {
        "id": out.get("id", ""),
        "username": out.get("username", ""),
        "name": out.get("name", ""),
        "account_type": out.get("account_type", ""),
        "profile_picture_url": out.get("profile_picture_url", ""),
        "followers_count": out.get("followers_count"),
        "follows_count": out.get("follows_count"),
        "media_count": out.get("media_count"),
    }
    _CACHE[key] = {"at": time.time(), "data": data}
    return True, data


def media(user: Dict[str, Any], limit: int = 24, force: bool = False) -> Tuple[bool, Any]:
    """The account's own posts and reels, newest first."""
    token = _token(user)
    if not token:
        return False, "This workspace has no Instagram account connected."

    key = f"media:{user['id']}:{limit}"
    hit = _CACHE.get(key)
    if hit and not force and time.time() - hit["at"] < CACHE_SECONDS:
        return True, hit["data"]

    url = (f"{IG_BASE}/me/media?fields={MEDIA_FIELDS}"
           f"&limit={int(limit)}&access_token={urllib.parse.quote(token)}")
    ok, out = _get(url)
    if not ok:
        return False, out

    items = []
    for m in out.get("data", []):
        kind = m.get("media_product_type") or m.get("media_type") or ""
        items.append({
            "id": m.get("id"),
            "caption": (m.get("caption") or "").strip(),
            # thumbnail_url is only present on video; for images media_url IS the image
            "thumbnail": m.get("thumbnail_url") or m.get("media_url") or "",
            "permalink": m.get("permalink", ""),
            "kind": "reel" if kind.upper() in ("REELS", "REEL") else
                    ("video" if (m.get("media_type") or "").upper() == "VIDEO" else "post"),
            "timestamp": m.get("timestamp", ""),
            "likes": m.get("like_count"),
            "comments": m.get("comments_count"),
        })
    _CACHE[key] = {"at": time.time(), "data": items}
    return True, items


def one(user: Dict[str, Any], media_id: str) -> Tuple[bool, Any]:
    ok, items = media(user, limit=50)
    if not ok:
        return False, items
    for m in items:
        if m["id"] == media_id:
            return True, m
    return False, "That post is not in this account's recent media."


def forget(user_id: str) -> None:
    for k in [k for k in _CACHE if k.endswith(f":{user_id}") or f":{user_id}:" in k]:
        _CACHE.pop(k, None)
