import time
import logging
import threading
from datetime import datetime
from typing import Optional, Dict, Any, Set

from core.browser_manager import BrowserManager
from core.dm_engine import DMEngine
from core.automation_engine import AutomationEngine
from core.contacts_manager import ContactsManager
from core.safety import SafetyManager

logger = logging.getLogger("CommentWatcher")

class CommentWatcher:
    """
    Background worker that monitors Instagram Posts/Reels for new comments,
    matches keywords against ManyChat automation rules, posts public replies,
    sends private DMs, and captures contacts into CRM.
    """

    def __init__(self, browser_manager: BrowserManager, automation_engine: AutomationEngine, contacts_manager: ContactsManager, campaign_manager=None):
        self.browser_manager = browser_manager
        self.automation_engine = automation_engine
        self.contacts_manager = contacts_manager
        self.campaign_manager = campaign_manager
        self.dm_engine = DMEngine(self.browser_manager)
        self.safety_manager = SafetyManager()

        self.status = "STOPPED" # STOPPED, RUNNING, PAUSED
        self.thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.target_post_url: Optional[str] = None
        self.poll_interval = 60 # seconds
        self.processed_comments: Set[str] = set()

    def log(self, level: str, message: str):
        logger.info(f"[{level}] {message}")
        if self.campaign_manager:
            self.campaign_manager.add_log(level, f"[ManyChat Watcher] {message}")

    def start(self, post_url: Optional[str] = None, interval: int = 60) -> bool:
        if self.status == "RUNNING":
            return False

        self.target_post_url = post_url
        self.poll_interval = max(30, interval)
        self._stop_event.clear()
        self.status = "RUNNING"

        self.thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.thread.start()
        self.log("SUCCESS", f"Started Comment-to-DM monitor (Interval: {self.poll_interval}s, Target: {self.target_post_url or 'All Active Rules'})")
        return True

    def stop(self) -> bool:
        if self.status != "RUNNING":
            return False
        self._stop_event.set()
        self.status = "STOPPED"
        self.log("WARN", "Stopped Comment-to-DM monitor.")
        return True

    def _watch_loop(self):
        context = None
        page = None

        try:
            context, page = self.browser_manager.launch(headless=True)
            self.log("INFO", "Browser context initialized for Comment Watcher.")

            while not self._stop_event.is_set():
                try:
                    # If target post URL specified, check that post
                    if self.target_post_url:
                        self._check_post_comments(page, self.target_post_url)
                    else:
                        # Check active rules for specific post URLs
                        rules = self.automation_engine.get_all()
                        for r in rules:
                            if self._stop_event.is_set():
                                break
                            target = r.get("post_target")
                            if target and target.startswith("http"):
                                self._check_post_comments(page, target)

                    # Sleep between check cycles
                    start_sleep = time.time()
                    while time.time() - start_sleep < self.poll_interval:
                        if self._stop_event.is_set():
                            break
                        time.sleep(1)

                except Exception as loop_err:
                    self.log("ERROR", f"Watcher loop cycle error: {str(loop_err)}")
                    time.sleep(10)

        except Exception as e:
            self.log("ERROR", f"Watcher thread encountered fatal error: {str(e)}")
            self.status = "STOPPED"
        finally:
            self.browser_manager.close()
            self.status = "STOPPED"
            self.log("INFO", "Comment Watcher browser closed.")

    def _check_post_comments(self, page, post_url: str):
        """
        Navigates to post, extracts comments, matches rules and triggers DMs.
        """
        self.log("INFO", f"Checking recent comments on: {post_url}")
        page.goto(post_url, wait_until="domcontentloaded", timeout=25000)
        time.sleep(3)
        self.dm_engine.dismiss_popups(page)

        # Look for comment rows
        # In modern IG web, comments are inside ul / li elements or role="listitem"
        comment_items = page.locator('ul > li div[role="button"]:has(span), div[role="listitem"]').all()

        found_count = 0
        for item in comment_items[:15]: # Process up to 15 recent comments per cycle
            if self._stop_event.is_set():
                break

            try:
                text = item.inner_text()
                if not text or "\n" not in text:
                    continue

                lines = text.split("\n")
                username = lines[0].strip().lstrip("@")
                comment_body = " ".join(lines[1:]).strip()

                comment_id = f"{username}_{hash(comment_body)}"
                if comment_id in self.processed_comments:
                    continue

                # Match against automation rules
                matched = self.automation_engine.match_comment(comment_body, username=username, post_url=post_url)
                if matched and matched.get("matched"):
                    found_count += 1
                    self.processed_comments.add(comment_id)
                    self.log("SUCCESS", f"Keyword matched from @{username}: '{comment_body}' -> Rule: '{matched['rule_name']}'")

                    # 1. Send Direct Message with Link
                    dm_text = matched.get("dm_reply")
                    if dm_text:
                        self.log("INFO", f"Sending automated DM to @{username}...")
                        res = self.dm_engine.send_dm(page, username, dm_text)
                        if res.get("success"):
                            self.safety_manager.record_dm_sent()
                            self.log("SUCCESS", f"Sent automated DM to @{username}")
                        else:
                            self.log("ERROR", f"Failed sending DM to @{username}: {res.get('error')}")

                    # 2. Record lead into ManyChat Contacts CRM
                    self.contacts_manager.record_interaction(
                        username=username,
                        name=username,
                        source=f"Comment on {post_url}",
                        new_tags=matched.get("tags", ["Commented Lead"])
                    )

                    # Human cooldown
                    time.sleep(15)

            except Exception as item_err:
                continue

        if found_count > 0:
            self.log("INFO", f"Processed {found_count} new trigger comments on post.")
