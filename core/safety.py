import os
import json
import time
import random
from datetime import datetime, date
from typing import Tuple, Dict, Any

STATS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "stats.json")

class SafetyManager:
    """
    Guards against Instagram action blocks and account flags:
    - Tracks and enforces daily sending limits
    - Calculates randomized human delays
    - Detects action block patterns
    """

    DEFAULT_MIN_DELAY = 45  # seconds
    DEFAULT_MAX_DELAY = 90  # seconds
    DEFAULT_DAILY_LIMIT = 35 # max DMs per day

    def __init__(self, stats_file: str = STATS_FILE):
        self.stats_file = stats_file
        self._ensure_dir()

    def _ensure_dir(self):
        folder = os.path.dirname(self.stats_file)
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)

    def _load_stats(self) -> Dict[str, Any]:
        if not os.path.exists(self.stats_file):
            return {"date": str(date.today()), "sent_today": 0, "total_sent": 0}
        try:
            with open(self.stats_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                today = str(date.today())
                if data.get("date") != today:
                    data["date"] = today
                    data["sent_today"] = 0
                return data
        except Exception:
            return {"date": str(date.today()), "sent_today": 0, "total_sent": 0}

    def _save_stats(self, data: Dict[str, Any]):
        self._ensure_dir()
        with open(self.stats_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_today_sent_count(self) -> int:
        stats = self._load_stats()
        return stats.get("sent_today", 0)

    def record_dm_sent(self):
        stats = self._load_stats()
        stats["sent_today"] = stats.get("sent_today", 0) + 1
        stats["total_sent"] = stats.get("total_sent", 0) + 1
        self._save_stats(stats)

    def can_send_today(self, daily_limit: int = DEFAULT_DAILY_LIMIT) -> Tuple[bool, str]:
        sent = self.get_today_sent_count()
        if sent >= daily_limit:
            return False, f"Daily limit of {daily_limit} DMs reached for today ({sent} sent). Paused for safety."
        return True, ""

    @staticmethod
    def calculate_delay(min_sec: int = DEFAULT_MIN_DELAY, max_sec: int = DEFAULT_MAX_DELAY) -> float:
        """
        Returns a randomized delay with micro-jitter to appear natural.
        """
        if min_sec > max_sec:
            min_sec, max_sec = max_sec, min_sec
        base = random.uniform(min_sec, max_sec)
        jitter = random.uniform(-1.5, 2.5)
        return max(5.0, round(base + jitter, 1))

    @staticmethod
    def get_keystroke_delay() -> float:
        """
        Generates realistic human keystroke delay in seconds (0.04s to 0.12s)
        """
        return random.uniform(0.045, 0.125)

    @staticmethod
    def is_action_blocked(page_content: str) -> Tuple[bool, str]:
        """
        Scans DOM text for Instagram spam blocks.
        """
        lower = page_content.lower()
        triggers = [
            "try again later",
            "action blocked",
            "we restrict certain activity",
            "your account has been temporarily",
            "tell us if you think we made a mistake",
            "we limit how often you can do certain things",
            "help us confirm you own this account"
        ]
        for trigger in triggers:
            if trigger in lower:
                return True, f"Instagram Safety Trigger detected: '{trigger}'"
        return False, ""
