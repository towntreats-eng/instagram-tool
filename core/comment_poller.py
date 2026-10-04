"""
Reading comments ourselves, because Meta will not send them yet.

Meta's own dashboard states the rule plainly on the webhook screen:

    "Apps will only be able to receive test webhooks sent from the dashboard
     while the app is unpublished. No production data, including from app
     admins, developers or testers, will be delivered unless the app has been
     published."

So until App Review passes and the app goes Live, a real comment produces
exactly nothing - no webhook, for anybody, not even the app's own owner. Every
subscription can be perfect and the product still looks broken. That is not a
bug to fix; it is a door that opens on Meta's schedule, not ours.

Reading is not gated the same way. `GET /{media-id}/comments` answers today for
the accounts the app already has a token for. So this polls, builds the exact
payload Meta would have sent, and hands it to the real webhook handler - the
same matching, the same follow-gate, the same send. When the app does go Live
and webhooks start arriving, nothing has to change: the two paths already run
the same code, and the seen-set stops the same comment being answered twice.

Safety properties, in order of how badly each would hurt:

  * The first time a post is seen, every comment already on it is marked seen
    and NOT acted on. Without this, switching the poller on would DM everyone
    who ever commented on the merchant's back catalogue.
  * A comment is delivered once. The seen-set is persisted, so a restart does
    not replay the backlog.
  * Comments by the connected account itself are never delivered.
  * Only posts with a live flow are polled, and only for connected accounts.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

from core import store

IG_BASE = os.environ.get("IG_GRAPH_BASE", "https://graph.instagram.com").rstrip("/")
TIMEOUT = 20
STATE_FILE = "data/poll_state.json"

# Per post. Comment ids are ~20 chars, so this is a few KB at worst and keeps
# the state file from growing without bound on a popular reel.
KEEP_SEEN = 400

# How far back to look on a post we are already watching. A comment older than
# this was either already handled or is past Meta's 7-day private-reply window.
MAX_AGE_SECONDS = 6 * 24 * 3600

COMMENT_FIELDS = "id,text,timestamp,username,from{id,username}"


def _get(url: str) -> Tuple[bool, Any]:
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as res:
            return True, json.loads(res.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            err = json.loads(exc.read().decode()).get("error", {})
            return False, err.get("message") or f"HTTP {exc.code}"
        except Exception:
            return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)


# Deliberately a separate file from the poll state. Once the Meta app is
# published, both paths run at once: a webhook can arrive for a comment the
# poller is about to read. The handler writes here the moment it handles one,
# and the poller checks here before delivering. Keeping it out of the poll
# state file means a poll pass saving its own state cannot overwrite an id the
# handler recorded while that pass was running - which would have cost the
# commenter a second, duplicate DM.
HANDLED_FILE = "data/handled_comments.json"
KEEP_HANDLED = 2000


def mark_handled(comment_id: str) -> None:
    if not comment_id:
        return
    try:
        ids = store.read(HANDLED_FILE, []) if store.exists(HANDLED_FILE) else []
        ids = ids if isinstance(ids, list) else []
        cid = str(comment_id)
        if cid in ids:
            return
        ids.append(cid)
        store.write(HANDLED_FILE, ids[-KEEP_HANDLED:])
    except Exception:
        pass


def was_handled(comment_id: str) -> bool:
    try:
        ids = store.read(HANDLED_FILE, []) if store.exists(HANDLED_FILE) else []
        return str(comment_id) in (ids if isinstance(ids, list) else [])
    except Exception:
        return False


def handled_set() -> set:
    try:
        ids = store.read(HANDLED_FILE, []) if store.exists(HANDLED_FILE) else []
        return set(str(i) for i in (ids if isinstance(ids, list) else []))
    except Exception:
        return set()


def _state() -> Dict[str, Any]:
    try:
        s = store.read(STATE_FILE, {}) if store.exists(STATE_FILE) else {}
        return s if isinstance(s, dict) else {}
    except Exception:
        return {}


def _save(state: Dict[str, Any]) -> None:
    try:
        store.write(STATE_FILE, state)
    except Exception:
        pass


def comments(media_id: str, token: str, limit: int = 25) -> Tuple[bool, Any]:
    url = (f"{IG_BASE}/{urllib.parse.quote(str(media_id))}/comments"
           f"?fields={urllib.parse.quote(COMMENT_FIELDS)}&limit={int(limit)}"
           f"&access_token={urllib.parse.quote(token)}")
    ok, out = _get(url)
    if not ok:
        # `from` is not always readable. Losing it costs us the follow-gate,
        # not the DM - a private reply is addressed by comment id - so retry
        # without it rather than giving up on the post.
        url2 = (f"{IG_BASE}/{urllib.parse.quote(str(media_id))}/comments"
                f"?fields=id,text,timestamp,username&limit={int(limit)}"
                f"&access_token={urllib.parse.quote(token)}")
        ok2, out2 = _get(url2)
        if ok2:
            return True, out2
    return ok, out


def watched_media(user: Dict[str, Any], rules: List[Dict[str, Any]]) -> List[str]:
    """Posts with a live comment flow belonging to this workspace."""
    out: List[str] = []
    for r in rules:
        if not r.get("is_active") or r.get("type") != "comment_to_dm":
            continue
        if r.get("created_by") and r.get("created_by") != user.get("id"):
            continue
        mid = r.get("post_media_id")
        if mid and str(mid) not in out:
            out.append(str(mid))
    return out


def recent_media(token: str, limit: int = 6) -> List[str]:
    """For a catch-all flow with no post bound to it."""
    ok, out = _get(f"{IG_BASE}/me/media?fields=id&limit={int(limit)}"
                   f"&access_token={urllib.parse.quote(token)}")
    if not ok:
        return []
    return [str(m.get("id")) for m in (out or {}).get("data", []) if m.get("id")]


def poll_user(user: Dict[str, Any], rules: List[Dict[str, Any]],
              deliver: Callable[[Dict[str, Any]], Any],
              state: Dict[str, Any]) -> Dict[str, Any]:
    """One workspace, one pass. `deliver` takes a Meta-shaped payload."""
    ig = (user or {}).get("instagram") or {}
    token = ig.get("access_token", "")
    if not (ig.get("connected") and token):
        return {"polled": 0, "new": 0, "primed": 0, "errors": []}

    owner_id = str(ig.get("user_id") or ig.get("instagram_account_id") or "")
    owner_name = (ig.get("username") or "").lower()

    media_ids = watched_media(user, rules)
    has_catch_all = any(
        r.get("is_active") and r.get("type") == "comment_to_dm"
        and (not r.get("created_by") or r.get("created_by") == user.get("id")) and not r.get("post_media_id")
        for r in rules)
    if has_catch_all:
        for mid in recent_media(token):
            if mid not in media_ids:
                media_ids.append(mid)

    stats = {"polled": 0, "new": 0, "primed": 0, "errors": []}
    now = time.time()
    already = handled_set()

    for mid in media_ids[:10]:
        ok, out = comments(mid, token)
        stats["polled"] += 1
        if not ok:
            stats["errors"].append(f"{mid}: {out}")
            continue

        rows = (out or {}).get("data", []) or []
        key = f"{user.get('id')}:{mid}"
        entry = state.get(key) or {}
        seen = set(entry.get("seen") or [])
        first_time = not entry.get("primed")

        fresh: List[Dict[str, Any]] = []
        for c in rows:
            cid = str(c.get("id") or "")
            if not cid or cid in seen:
                continue
            seen.add(cid)
            if cid in already:
                continue  # a webhook already answered this one
            if first_time:
                stats["primed"] += 1
                continue
            frm = c.get("from") or {}
            who_id = str(frm.get("id") or "")
            who = (frm.get("username") or c.get("username") or "").strip()
            if (owner_id and who_id == owner_id) or (owner_name and who.lower() == owner_name):
                continue  # the account's own comment
            if _too_old(c.get("timestamp"), now):
                continue
            fresh.append({"id": cid, "text": c.get("text") or "",
                          "from_id": who_id, "username": who})

        state[key] = {"seen": list(seen)[-KEEP_SEEN:], "primed": True, "at": now}

        for c in fresh:
            payload = {"object": "instagram", "entry": [{
                "id": owner_id or str(user.get("id")), "time": int(now),
                "changes": [{"field": "comments", "value": {
                    "id": c["id"], "text": c["text"], "media": {"id": str(mid)},
                    "from": {"id": c["from_id"], "username": c["username"]},
                }}]}]}
            try:
                deliver(payload)
                stats["new"] += 1
            except Exception as exc:
                stats["errors"].append(f"{c['id']}: {exc}")

    return stats


def _too_old(timestamp: Optional[str], now: float) -> bool:
    if not timestamp:
        return False
    try:
        from datetime import datetime
        ts = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S%z").timestamp()
        return (now - ts) > MAX_AGE_SECONDS
    except Exception:
        return False


def poll_all(users: List[Dict[str, Any]], rules: List[Dict[str, Any]],
             deliver: Callable[[Dict[str, Any]], Any]) -> Dict[str, Any]:
    state = _state()
    total = {"workspaces": 0, "polled": 0, "new": 0, "primed": 0, "errors": []}
    for u in users:
        ig = (u or {}).get("instagram") or {}
        if not (ig.get("connected") and ig.get("access_token")):
            continue
        mine = [r for r in rules if not r.get("created_by") or r.get("created_by") == u.get("id")]
        if not any(r.get("is_active") and r.get("type") == "comment_to_dm" for r in mine):
            continue
        total["workspaces"] += 1
        s = poll_user(u, mine, deliver, state)
        for k in ("polled", "new", "primed"):
            total[k] += s[k]
        total["errors"].extend(s["errors"][:3])
    _save(state)
    return total
