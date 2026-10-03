"""
DM Flow — Admin Store
========================
Announcements (in-app notices broadcast to users) and the platform event log
that powers the System Health tab of the admin dashboard.
"""

import os
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from core import store

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
ANNOUNCE_FILE = os.path.join(DATA_DIR, "announcements.json")
EVENTS_FILE = os.path.join(DATA_DIR, "events.json")

ISO = "%Y-%m-%dT%H:%M:%S"
MAX_EVENTS = 400


def _now() -> str:
    return datetime.now().strftime(ISO)


class AdminStore:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.announcements = self._load(ANNOUNCE_FILE, self._seed_announcements)
        self.events = self._load(EVENTS_FILE, self._seed_events)

    # ------------------------------------------------------------------ io
    def _load(self, path: str, seeder) -> List[Dict[str, Any]]:
        if store.exists(path):
            try:
                data = store.read(path)
                if isinstance(data, list):
                    return data
            except Exception:
                pass
        data = seeder()
        self._write(path, data)
        return data

    def _write(self, path: str, data: List[Dict[str, Any]]) -> None:
        store.write(path, data)

    # ---------------------------------------------------------------- seed
    def _seed_announcements(self) -> List[Dict[str, Any]]:
        """None. Announcements are written by the operator, not shipped."""
        return []

    def _seed_events(self) -> List[Dict[str, Any]]:
        """Nothing. The activity log shows what actually happened.

        It used to ship fourteen invented events naming customers who did not
        exist — "Renewal recorded for riya@glowcart.in" — so the first thing an
        operator read in their own console was fiction.
        """
        return []

    def list_announcements(self) -> List[Dict[str, Any]]:
        return sorted(self.announcements, key=lambda a: a.get("created_at", ""), reverse=True)

    def add_announcement(self, title: str, body: str, audience: str = "all",
                         level: str = "update", published: bool = True) -> Dict[str, Any]:
        item = {
            "id": f"ann_{uuid.uuid4().hex[:8]}",
            "title": title.strip(),
            "body": body.strip(),
            "audience": audience,
            "level": level,
            "published": published,
            "created_at": _now(),
        }
        self.announcements.append(item)
        self._write(ANNOUNCE_FILE, self.announcements)
        self.log("INFO", "announcement", f"Published announcement: {item['title']}")
        return item

    def delete_announcement(self, ann_id: str) -> bool:
        before = len(self.announcements)
        self.announcements = [a for a in self.announcements if a["id"] != ann_id]
        self._write(ANNOUNCE_FILE, self.announcements)
        return len(self.announcements) < before

    def latest_published(self) -> Optional[Dict[str, Any]]:
        published = [a for a in self.list_announcements() if a.get("published")]
        return published[0] if published else None

    # --------------------------------------------------------------- events
    def log(self, level: str, source: str, message: str) -> Dict[str, Any]:
        item = {
            "id": f"evt_{uuid.uuid4().hex[:8]}",
            "level": level.upper(),
            "source": source,
            "message": message,
            "created_at": _now(),
        }
        self.events.append(item)
        self.events = self.events[-MAX_EVENTS:]
        self._write(EVENTS_FILE, self.events)
        return item

    def list_events(self, level: str = "all", limit: int = 60) -> List[Dict[str, Any]]:
        rows = sorted(self.events, key=lambda e: e.get("created_at", ""), reverse=True)
        if level != "all":
            rows = [e for e in rows if e.get("level", "").upper() == level.upper()]
        return rows[:limit]

    def health_summary(self) -> Dict[str, Any]:
        counts = {"SUCCESS": 0, "INFO": 0, "WARN": 0, "ERROR": 0}
        for e in self.events:
            lvl = e.get("level", "INFO").upper()
            counts[lvl] = counts.get(lvl, 0) + 1
        total = sum(counts.values()) or 1
        error_rate = round((counts.get("ERROR", 0) + counts.get("WARN", 0)) / total * 100, 1)
        if counts.get("ERROR", 0) == 0 and error_rate < 10:
            state, label = "healthy", "All systems operational"
        elif error_rate < 25:
            state, label = "degraded", "Minor issues detected"
        else:
            state, label = "critical", "Needs attention"
        return {
            "state": state,
            "label": label,
            "error_rate": error_rate,
            "counts": counts,
            "events_total": sum(counts.values()),
        }
