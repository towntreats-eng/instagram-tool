import os
import csv
import time
import queue
import logging
import threading
from io import StringIO
from datetime import datetime
from typing import List, Dict, Any, Optional

from core.browser_manager import BrowserManager
from core.dm_engine import DMEngine
from core.spintax import SpintaxEngine
from core.safety import SafetyManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CampaignManager")

class TargetLead:
    def __init__(self, id: int, username: str, name: str = ""):
        self.id = id
        self.username = username.strip().lstrip("@")
        self.name = name.strip() or self.username
        self.status = "pending"  # pending, in_progress, sent, failed, skipped
        self.sent_message: Optional[str] = None
        self.sent_at: Optional[str] = None
        self.error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "name": self.name,
            "status": self.status,
            "sent_message": self.sent_message,
            "sent_at": self.sent_at,
            "error": self.error
        }

class CampaignManager:
    """
    Orchestrates leads queue, campaign execution thread,
    safety delays, and real-time event streaming.
    """

    def __init__(self):
        self.targets: List[TargetLead] = []
        self.status = "IDLE"  # IDLE, RUNNING, PAUSED, STOPPED, COMPLETED
        self.thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set() # Unpaused by default

        self.browser_manager = BrowserManager()
        self.safety_manager = SafetyManager()
        self.dm_engine = DMEngine(self.browser_manager)

        # Settings
        self.message_template = "{Hey|Hello|Hi} {name}! {Hope you are having a wonderful week|Loved your profile}! Check out our latest project."
        self.min_delay = 45
        self.max_delay = 90
        self.daily_limit = 35
        self.headless = False  # Visible by default so user can monitor

        # Logs & Event subscribers
        self.log_history: List[Dict[str, Any]] = []
        self.subscribers: List[queue.Queue] = []
        self._lock = threading.Lock()

        self.add_log("SYSTEM", "Instagram Auto DM Engine initialized and ready.")

    def add_log(self, level: str, message: str, meta: Optional[Dict[str, Any]] = None):
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "level": level.upper(),
            "message": message,
            "meta": meta or {}
        }
        with self._lock:
            self.log_history.append(entry)
            if len(self.log_history) > 500:
                self.log_history.pop(0)

            # Broadcast to SSE subscribers
            dead = []
            for sub in self.subscribers:
                try:
                    sub.put_nowait(entry)
                except Exception:
                    dead.append(sub)
            for d in dead:
                self.subscribers.remove(d)

    def subscribe_logs(self) -> queue.Queue:
        q = queue.Queue(maxsize=100)
        with self._lock:
            self.subscribers.append(q)
        return q

    def unsubscribe_logs(self, q: queue.Queue):
        with self._lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def load_targets_from_text(self, text: str) -> int:
        """
        Accepts raw multiline string formatted as:
        username
        or:
        username, Name
        """
        lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
        new_targets = []
        idx = len(self.targets) + 1
        for line in lines:
            parts = [p.strip() for p in line.split(",") if p.strip()]
            username = parts[0]
            name = parts[1] if len(parts) > 1 else ""
            if username:
                new_targets.append(TargetLead(idx, username, name))
                idx += 1

        self.targets.extend(new_targets)
        self.add_log("INFO", f"Loaded {len(new_targets)} targets into campaign queue.")
        return len(new_targets)

    def load_targets_from_csv(self, csv_content: str) -> int:
        f = StringIO(csv_content)
        reader = csv.reader(f)
        count = 0
        idx = len(self.targets) + 1

        header = next(reader, None)
        user_col = 0
        name_col = 1

        if header:
            lower_h = [col.lower().strip() for col in header]
            if "username" in lower_h:
                user_col = lower_h.index("username")
            if "name" in lower_h:
                name_col = lower_h.index("name")
            elif "full_name" in lower_h:
                name_col = lower_h.index("full_name")

            # Check if header is actually a row
            if "instagram" not in lower_h and "username" not in lower_h and "handle" not in lower_h:
                # Treat first row as data
                if len(header) > 0 and header[0].strip():
                    name = header[1].strip() if len(header) > 1 else ""
                    self.targets.append(TargetLead(idx, header[0].strip(), name))
                    idx += 1
                    count += 1

        for row in reader:
            if not row or not row[0].strip():
                continue
            username = row[user_col].strip() if len(row) > user_col else ""
            name = row[name_col].strip() if len(row) > name_col else ""
            if username:
                self.targets.append(TargetLead(idx, username, name))
                idx += 1
                count += 1

        self.add_log("INFO", f"Imported {count} leads from CSV.")
        return count

    def clear_targets(self):
        if self.status == "RUNNING":
            return False
        self.targets = []
        self.status = "IDLE"
        self.add_log("INFO", "Cleared targets queue.")
        return True

    def start_campaign(self, settings: Optional[Dict[str, Any]] = None) -> bool:
        if self.status == "RUNNING":
            return False

        if settings:
            self.message_template = settings.get("template", self.message_template)
            self.min_delay = int(settings.get("min_delay", self.min_delay))
            self.max_delay = int(settings.get("max_delay", self.max_delay))
            self.daily_limit = int(settings.get("daily_limit", self.daily_limit))
            self.headless = bool(settings.get("headless", self.headless))

        pending_targets = [t for t in self.targets if t.status == "pending"]
        if not pending_targets:
            self.add_log("WARN", "No pending targets in queue to send DMs to.")
            return False

        # Reset controls
        self._stop_event.clear()
        self._pause_event.set()
        self.status = "RUNNING"

        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()
        self.add_log("SUCCESS", f"Started Auto DM campaign with {len(pending_targets)} pending targets.")
        return True

    def pause_campaign(self) -> bool:
        if self.status != "RUNNING":
            return False
        self._pause_event.clear()
        self.status = "PAUSED"
        self.add_log("WARN", "Campaign paused by user.")
        return True

    def resume_campaign(self) -> bool:
        if self.status != "PAUSED":
            return False
        self._pause_event.set()
        self.status = "RUNNING"
        self.add_log("INFO", "Campaign resumed.")
        return True

    def stop_campaign(self) -> bool:
        if self.status not in ["RUNNING", "PAUSED"]:
            return False
        self._stop_event.set()
        self._pause_event.set()
        self.status = "STOPPED"
        self.add_log("WARN", "Campaign stop signal received. Stopping worker...")
        return True

    def _worker_loop(self):
        """
        Executes the campaign sequence with safety checks, humanized delays,
        and action block protections.
        """
        context = None
        page = None

        try:
            self.add_log("INFO", f"Launching browser session (Headless={self.headless})...")
            context, page = self.browser_manager.launch(headless=self.headless)

            # Quick verification of login state
            self.add_log("INFO", "Checking Instagram authentication...")
            page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=25000)
            time.sleep(3)
            self.dm_engine.dismiss_popups(page)

            if "/accounts/login" in page.url:
                self.add_log("ERROR", "Not logged into Instagram! Please use the 'Login to Instagram' button first.")
                self.status = "STOPPED"
                return

            self.add_log("SUCCESS", "Instagram session authenticated. Processing queue...")

            for target in self.targets:
                if self._stop_event.is_set():
                    break

                # Check pause
                while not self._pause_event.is_set():
                    if self._stop_event.is_set():
                        break
                    time.sleep(1)

                if target.status != "pending":
                    continue

                # Enforce daily safety limit
                allowed, limit_msg = self.safety_manager.can_send_today(self.daily_limit)
                if not allowed:
                    self.add_log("ERROR", f"SAFETY LIMIT: {limit_msg}")
                    self.status = "STOPPED"
                    break

                # Mark active
                target.status = "in_progress"
                self.add_log("INFO", f"Preparing DM for @{target.username} (Lead #{target.id})")

                # Generate customized message with spintax & variables
                personalized_message = SpintaxEngine.spin(
                    self.message_template,
                    {"username": target.username, "name": target.name}
                )

                # Send DM via DMEngine
                res = self.dm_engine.send_dm(page, target.username, personalized_message)

                if res.get("success"):
                    target.status = "sent"
                    target.sent_message = personalized_message
                    target.sent_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.safety_manager.record_dm_sent()
                    today_count = self.safety_manager.get_today_sent_count()
                    self.add_log("SUCCESS", f"DM sent to @{target.username}! (Daily sent: {today_count}/{self.daily_limit})")
                else:
                    target.status = "failed"
                    target.error = res.get("error", "Unknown error")
                    self.add_log("ERROR", f"Failed sending to @{target.username}: {target.error}")

                    # If Instagram triggered an Action Block, stop immediately to save the account!
                    if res.get("action_blocked"):
                        self.add_log("ERROR", "EMERGENCY SAFETY STOP: Instagram action block detected! Stopping campaign.")
                        self.status = "STOPPED"
                        break

                # If there are more pending items, execute randomized human delay
                remaining_pending = [t for t in self.targets if t.status == "pending"]
                if remaining_pending and not self._stop_event.is_set():
                    delay = SafetyManager.calculate_delay(self.min_delay, self.max_delay)
                    self.add_log("INFO", f"Anti-ban safety wait: sleeping {delay}s before next recipient...")

                    # Incremental sleep so pause/stop triggers immediately
                    start_sleep = time.time()
                    while time.time() - start_sleep < delay:
                        if self._stop_event.is_set():
                            break
                        while not self._pause_event.is_set():
                            if self._stop_event.is_set():
                                break
                            time.sleep(1)
                        time.sleep(1)

            if not self._stop_event.is_set() and self.status != "STOPPED":
                self.status = "COMPLETED"
                self.add_log("SUCCESS", "Campaign completed! All targets in queue processed.")

        except Exception as e:
            self.add_log("ERROR", f"Campaign execution encountered error: {str(e)}")
            self.status = "STOPPED"
        finally:
            self.browser_manager.close()
            if self.status == "RUNNING":
                self.status = "STOPPED"
            self.add_log("INFO", "Browser closed and campaign session finalized.")

    def export_csv(self) -> str:
        """
        Exports targets and status to CSV string.
        """
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Username", "Name", "Status", "Sent At", "Message", "Error"])
        for t in self.targets:
            writer.writerow([t.id, t.username, t.name, t.status, t.sent_at or "", t.sent_message or "", t.error or ""])
        return output.getvalue()

    def get_stats(self) -> Dict[str, Any]:
        total = len(self.targets)
        sent = sum(1 for t in self.targets if t.status == "sent")
        failed = sum(1 for t in self.targets if t.status == "failed")
        pending = sum(1 for t in self.targets if t.status == "pending")
        in_progress = sum(1 for t in self.targets if t.status == "in_progress")
        sent_today = self.safety_manager.get_today_sent_count()

        return {
            "status": self.status,
            "total_targets": total,
            "sent_count": sent,
            "failed_count": failed,
            "pending_count": pending,
            "in_progress_count": in_progress,
            "sent_today": sent_today,
            "daily_limit": self.daily_limit,
            "min_delay": self.min_delay,
            "max_delay": self.max_delay,
            "headless": self.headless,
            "message_template": self.message_template
        }
