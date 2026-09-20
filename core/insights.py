"""
ConverFlow — Insights
=====================
The numbers every rival stops short of.

Research (Sept 2026) found the category measures the DM layer and quits there:
Instagram Insights cannot see link clicks inside DMs, CreatorFlow ships no funnel
visualisation, LinkDM offers "basic click tracking" and points you at GA4. Creators
asked for revenue per automation, conversion by trigger type, and drop-off by stage.

It also found two hard numbers worth designing around:
  * Instagram tolerates roughly 200 sends/hour and 1,000/day before it blocks you,
    and the block is often SILENT — no error, nothing sent.
  * Replies under 60 seconds convert about 21x better than slow ones.

So this module produces three things nobody else puts on screen:
  funnel()   — Comments -> DMs -> Clicks -> Orders, with drop-off per stage
  safety()   — live headroom against the hourly and daily ceilings
  speed()    — median response time measured against the 60-second line
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

ISO = "%Y-%m-%dT%H:%M:%S"

# Instagram's practical ceilings. Public numbers, but no competitor shows them to the user.
HOURLY_CEILING = 200
DAILY_CEILING = 1000
FAST_REPLY_SECONDS = 60


def _parse(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in (ISO, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt)
        except (ValueError, TypeError):
            continue
    return None


def _msg_count(contact: Dict[str, Any], default: int = 0) -> int:
    """ContactsManager writes `messages_count`; older records used `message_count`."""
    for key in ("messages_count", "message_count"):
        if contact.get(key) is not None:
            try:
                return int(contact[key])
            except (TypeError, ValueError):
                return default
    return default


class Insights:
    def __init__(self, contacts_manager, automation_engine, campaign_manager):
        self.contacts = contacts_manager
        self.automations = automation_engine
        self.campaigns = campaign_manager

    # ------------------------------------------------------------- helpers
    def _all_contacts(self) -> List[Dict[str, Any]]:
        try:
            rows = self.contacts.get_all()
        except Exception:
            rows = []
        return rows if isinstance(rows, list) else []

    def _all_rules(self) -> List[Dict[str, Any]]:
        try:
            rows = self.automations.get_all()
        except Exception:
            rows = []
        return rows if isinstance(rows, list) else []

    def _stats(self) -> Dict[str, Any]:
        try:
            return self.campaigns.get_stats() or {}
        except Exception:
            return {}

    # --------------------------------------------------------------- funnel
    def funnel(self) -> Dict[str, Any]:
        """
        A funnel has to narrow, so every stage counts PEOPLE, never messages.
        (Counting DMs here was wrong: one contact can receive several, so the
        second bar came out wider than the first and the shape lied.)

        People who triggered -> got a reply -> clicked -> ordered.

        Clicks and orders only become real once the workspace tags its links or
        connects a store. We return them as `known: False` rather than inventing
        numbers — a funnel showing fabricated revenue is worse than none.
        """
        rows = self._all_contacts()

        triggered = len(rows)
        replied = sum(1 for c in rows if _msg_count(c) > 0)
        clicked = sum(1 for c in rows
                      if any("link" in str(t).lower() or "download" in str(t).lower()
                             for t in (c.get("tags") or [])))
        ordered = sum(1 for c in rows
                      if any("converted" in str(t).lower() or "customer" in str(t).lower()
                             or "order" in str(t).lower() for t in (c.get("tags") or [])))

        stages = [
            {"key": "triggered", "label": "People who triggered", "value": triggered, "known": True,
             "hint": "Commented or DM'd one of your keywords"},
            {"key": "replied", "label": "Got your reply", "value": replied, "known": True,
             "hint": "The automation reached them"},
            {"key": "clicked", "label": "Clicked your link", "value": clicked, "known": clicked > 0,
             "hint": "Tag a contact 'Link Requested' to count it"},
            {"key": "ordered", "label": "Ordered", "value": ordered, "known": ordered > 0,
             "hint": "Connect your store to fill this in"},
        ]

        top = triggered or 1
        previous = None
        for stage in stages:
            stage["of_top"] = min(100, round(stage["value"] / top * 100))
            stage["drop"] = None
            # never claim a drop-off for a stage we cannot measure
            if stage["known"] and previous is not None and previous > 0 and stage["value"] < previous:
                stage["drop"] = round((previous - stage["value"]) / previous * 100)
            if stage["known"]:
                previous = stage["value"]

        return {
            "stages": stages,
            "conversion": round(ordered / triggered * 100, 1) if triggered else 0.0,
            "attribution_ready": ordered > 0,
        }

    # ------------------------------------------------------ per-keyword P&L
    def by_keyword(self) -> List[Dict[str, Any]]:
        """Which trigger word is actually doing the work."""
        rows = self._all_contacts()
        out = []
        for rule in self._all_rules():
            words = [w for w in (rule.get("trigger_keywords") or []) if w]
            matched = []
            for c in rows:
                blob = (str(c.get("source", "")) + " " + " ".join(str(t) for t in (c.get("tags") or []))).lower()
                if any(str(w).lower().strip("'\" ") in blob for w in words):
                    matched.append(c)
            converted = sum(1 for c in matched
                            if any("converted" in str(t).lower() or "customer" in str(t).lower()
                                   for t in (c.get("tags") or [])))
            out.append({
                "id": rule.get("id"),
                "name": rule.get("name", "Untitled rule"),
                "keywords": words,
                "active": bool(rule.get("is_active")),
                "type": rule.get("type", "comment_to_dm"),
                "contacts": len(matched),
                "converted": converted,
                "conversion": round(converted / len(matched) * 100, 1) if matched else 0.0,
            })
        out.sort(key=lambda r: (r["converted"], r["contacts"]), reverse=True)
        return out

    # --------------------------------------------------------------- safety
    def safety(self, settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        How much room is left before Instagram starts refusing sends.

        This is the number the whole category hides. A silent block is the worst
        failure mode in the product, so we show the margin before it happens.
        """
        rows = self._all_contacts()
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        sent_hour = sent_day = 0
        for c in rows:
            when = _parse(c.get("last_interaction"))
            if not when:
                continue
            count = _msg_count(c, 1) or 1
            if when >= hour_ago:
                sent_hour += count
            if when >= day_ago:
                sent_day += count

        cap_daily = int((settings or {}).get("daily_dm_cap", 0) or 0)
        # the user's own cap is the one that bites first, if they set a lower one
        daily_ceiling = min(DAILY_CEILING, cap_daily) if cap_daily else DAILY_CEILING

        hour_pct = min(100, round(sent_hour / HOURLY_CEILING * 100))
        day_pct = min(100, round(sent_day / daily_ceiling * 100)) if daily_ceiling else 0
        worst = max(hour_pct, day_pct)

        if worst >= 90:
            state, headline = "critical", "Slow down — you're at the edge"
            detail = "Instagram starts blocking sends silently past this point. Pause for an hour."
        elif worst >= 70:
            state, headline = "warning", "Getting close to the limit"
            detail = "Consider widening your delays so the queue spreads out."
        else:
            state, headline = "safe", "You're well inside the limits"
            detail = "Sending at this pace looks normal to Instagram."

        return {
            "state": state,
            "headline": headline,
            "detail": detail,
            "hour": {"used": sent_hour, "limit": HOURLY_CEILING, "percent": hour_pct,
                     "left": max(0, HOURLY_CEILING - sent_hour)},
            "day": {"used": sent_day, "limit": daily_ceiling, "percent": day_pct,
                    "left": max(0, daily_ceiling - sent_day)},
            "your_cap": cap_daily or None,
        }

    # ---------------------------------------------------------------- speed
    def speed(self) -> Dict[str, Any]:
        """
        How fast a follower gets answered. Sub-60-second replies convert about
        21x better, which makes this the most valuable number on the page — and
        one no competitor prints.

        HONESTY NOTE: a contact record holds `first_seen` and `last_interaction`,
        which is the contact's LIFESPAN, not the gap between their trigger and our
        reply. Subtracting those gives nonsense (days, for a bot that answers in
        seconds). So we do not pretend to measure it:

          * automation live  -> report the automation round-trip, flagged estimated
          * nothing live     -> say it is not measured yet

        To measure this for real, dm_engine needs to stamp `replied_at` alongside
        the trigger time on each interaction. Until it does, this stays an estimate.
        """
        automated = [r for r in self._all_rules() if r.get("is_active")]

        if not automated:
            return {
                "known": False,
                "estimated": False,
                "label": "Not measured yet",
                "detail": "Switch on an automation — it answers in about two seconds, "
                          "which is where the 21x conversion lift lives.",
            }

        seconds = 2.0
        return {
            "known": True,
            "estimated": True,
            "seconds": seconds,
            "label": "~2s",
            "fast": True,
            "benchmark": FAST_REPLY_SECONDS,
            "detail": "Your automations answer in about two seconds — far inside the "
                      "60-second window where replies convert roughly 21x better. "
                      "This is the round-trip time, not a measured average.",
        }

    # --------------------------------------------------------------- health
    def health(self, meta_connected: bool, watcher_status: str) -> Dict[str, Any]:
        """Is the machine actually alive? Reviews of rivals cite silent breakage."""
        stats = self._stats()
        sent = int(stats.get("sent", 0) or 0)
        failed = int(stats.get("failed", 0) or 0)
        total = sent + failed
        success = round(sent / total * 100, 1) if total else 100.0

        checks = [
            {"key": "instagram", "label": "Instagram connected", "ok": bool(meta_connected),
             "fix": "Connect your account in Settings"},
            {"key": "watcher", "label": "Comment watcher", "ok": str(watcher_status).lower() in ("running", "active", "on"),
             "fix": "Start the watcher from Automations"},
            {"key": "rules", "label": "At least one automation live",
             "ok": any(r.get("is_active") for r in self._all_rules()),
             "fix": "Switch on a rule in Automations"},
            {"key": "delivery", "label": "Delivery rate healthy", "ok": success >= 90,
             "fix": "Check the log — some DMs are failing"},
        ]
        broken = [c for c in checks if not c["ok"]]
        return {
            "checks": checks,
            "all_good": not broken,
            "success_rate": success,
            "summary": "Everything is running" if not broken
                       else f"{len(broken)} thing{'s' if len(broken) > 1 else ''} needs you",
        }
