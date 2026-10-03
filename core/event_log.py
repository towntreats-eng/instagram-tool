"""
A record of what actually arrived.

The hardest part of this product to debug is not a bug - it is silence. A
merchant comments on their own reel, nothing happens, and there is no way to
tell apart the three very different reasons:

  * Meta never sent anything          (subscription, access level, or privacy)
  * Meta sent it and we rejected it   (bad signature, unknown object)
  * We took it and chose not to act   (no rule matched, follow-gate held it)

Logs on the server say which, but a merchant cannot read those, and neither
can the person helping them over chat. So every inbound delivery - real
webhook or poll - lands here with a verdict, and the dashboard can show the
one fact that settles the argument: when something last arrived.

Deliberately small: a ring of the most recent deliveries, nothing more. This
is a diagnostic, not an audit trail; `audit_log` is the audit trail.
"""

import time
from typing import Any, Dict, List, Optional

from core import store

FILE = "data/webhook_events.json"
KEEP = 60

# Verdicts, so the dashboard and the tests agree on the vocabulary.
REJECTED = "rejected"      # we refused it (signature)
NO_RULE = "no_rule"        # arrived, nothing was listening
HELD = "held"              # a rule matched, the follow-gate held the link
SENT = "sent"              # a DM went out
FAILED = "failed"          # a rule matched, sending failed
IGNORED = "ignored"        # not something we act on (own comment, echo)


def _load() -> List[Dict[str, Any]]:
    try:
        rows = store.read(FILE, []) if store.exists(FILE) else []
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def record(source: str, verdict: str, *, field: str = "", username: str = "",
           text: str = "", media_id: str = "", note: str = "",
           workspace: str = "") -> None:
    """Never raise. A diagnostic that can break the thing it diagnoses is worse
    than no diagnostic."""
    try:
        rows = _load()
        rows.insert(0, {
            "at": time.time(),
            "source": source,            # "webhook" | "poll"
            "verdict": verdict,
            "field": field,
            "username": username,
            "text": (text or "")[:180],
            "media_id": media_id,
            "workspace": workspace,
            "note": (note or "")[:300],
        })
        store.write(FILE, rows[:KEEP])
    except Exception:
        pass


def recent(limit: int = 20) -> List[Dict[str, Any]]:
    return _load()[:limit]


def last() -> Optional[Dict[str, Any]]:
    rows = _load()
    return rows[0] if rows else None


def ever_received() -> bool:
    """Has anything at all ever reached us? The single most useful fact."""
    return any(r.get("verdict") != REJECTED for r in _load())


def ago(ts: float) -> str:
    secs = max(0, int(time.time() - float(ts or 0)))
    if secs < 60:   return f"{secs}s ago"
    if secs < 3600: return f"{secs // 60}m ago"
    if secs < 86400: return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"
