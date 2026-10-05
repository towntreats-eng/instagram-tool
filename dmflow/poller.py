"""
Reading comments ourselves - the fallback for when webhooks do not arrive.

Meta delivers no production webhooks to an unpublished app, and a postback
(the tap on the opening DM's button) can only ever arrive by webhook. So the
poller can start a conversation on its own, but the link after the tap needs
webhooks. Until App Review, test with accounts that have a role on the app.

Safety:
  * The first time a post is watched, its existing comments are marked
    handled and never answered - switching on must not message everyone who
    ever commented.
  * The same `dm_handled` claim the webhook uses, so a comment is answered once.
  * Only comments younger than six days (Meta's private-reply window is seven).
"""

import time
from datetime import datetime
from typing import Any, Dict

from dmflow import accounts, db, engine, instagram

INTERVAL = 45
MAX_AGE = 6 * 86400


def _age(ts: str) -> float:
    try:
        return time.time() - datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z").timestamp()
    except Exception:
        return 0


def poll_account(acct: Dict[str, Any]) -> Dict[str, int]:
    user_id, token = acct["user_id"], acct["token"]
    stats = {"posts": 0, "new": 0, "primed": 0, "errors": 0}
    ids, any_post = engine.watched_media(user_id)
    if any_post:
        ok, recent = instagram.media(token, limit=8)
        if ok:
            ids += [m["id"] for m in recent if m["id"] not in ids]
    for mid in ids[:12]:
        ok, rows = instagram.comments(token, mid)
        stats["posts"] += 1
        if not ok:
            stats["errors"] += 1
            engine.log(user_id, "poll", "error", source="poll", note=f"Could not read comments on {mid}: {rows}")
            continue
        primed = db.one("SELECT primed_at FROM dm_poll WHERE user_id = ? AND media_id = ?", (user_id, mid))
        if not primed:
            for c in rows:
                engine.claim(c.get("id", ""), user_id)
            db.execute("INSERT INTO dm_poll (user_id, media_id, primed_at) VALUES (?, ?, ?) "
                       "ON CONFLICT (user_id, media_id) DO NOTHING", (user_id, mid, db.now()))
            stats["primed"] += len(rows)
            continue
        for c in reversed(rows):  # oldest first
            if _age(c.get("timestamp", "")) > MAX_AGE:
                continue
            frm = c.get("from") or {}
            verdict = engine.handle_comment(acct, {
                "id": c.get("id", ""), "text": c.get("text", ""), "media_id": mid,
                "from_id": str(frm.get("id") or ""),
                "username": frm.get("username") or c.get("username") or ""}, "poll")
            if verdict != "duplicate":
                stats["new"] += 1
    return stats


def poll_all() -> Dict[str, int]:
    total = {"accounts": 0, "posts": 0, "new": 0, "primed": 0, "errors": 0}
    users = db.query("SELECT DISTINCT user_id FROM dm_flows WHERE status = 'live'")
    for u in users:
        acct = accounts.get(u["user_id"])
        if not acct or acct["status"] != "connected":
            continue
        total["accounts"] += 1
        try:
            s = poll_account(acct)
            for k in s:
                total[k] += s[k]
        except Exception as exc:
            engine.log(u["user_id"], "poll", "error", source="poll", note=str(exc))
            total["errors"] += 1
    return total
