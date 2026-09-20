import os
import json
import re
from typing import List, Dict, Any, Optional, Tuple
from core.spintax import SpintaxEngine

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTOMATIONS_FILE = os.path.join(BASE_DIR, "data", "automations.json")

class AutomationEngine:
    """
    ManyChat Automation Rules Manager & Evaluator:
    Handles Comment-to-DM triggers, DM Keyword triggers,
    and Story Mention auto-responders.
    """

    def __init__(self, file_path: str = AUTOMATIONS_FILE):
        self.file_path = file_path
        self._ensure_dir()
        self._rules: List[Dict[str, Any]] = self._load()

    def _ensure_dir(self):
        folder = os.path.dirname(self.file_path)
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)

    def _load(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.file_path):
            seed = [
                {
                    "id": "rule_1",
                    "name": "Reel Comment 'LINK' -> Instant DM with Link",
                    "type": "comment_to_dm",
                    "post_target": "https://www.instagram.com/reel/C7xyz123/",
                    "post_thumbnail": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=400&q=80",
                    "post_caption": "Simple website = 20% conversion. DM for custom client website development 🚀 #webdesign #freelance",
                    "trigger_keywords": ["link", "send", "url", "info"],
                    "public_comment_reply": "{Thanks! Please see DMs.|Sent you a message! Check it out!|Nice! Check your DMs!}",
                    "comment_replies": [
                        "Thanks! Please see DMs.",
                        "Sent you a message! Check it out!",
                        "Nice! Check your DMs!"
                    ],
                    "opening_dm": "Hey there! I'm so happy you're here, thanks so much for your interest 😊\nClick below and I'll send you the link in just a sec ✨",
                    "button_text": "Send me the link",
                    "dm_message": "Hey {name}! Here is your direct link: https://satnamwebservices.com/offer Let me know if you need anything!",
                    "delivery_link": "https://satnamwebservices.com/offer",
                    "require_follow": False,
                    "ask_email": False,
                    "tags": ["Reel Lead", "Link Requested"],
                    "is_active": True
                },
                {
                    "id": "rule_2",
                    "name": "Reel Comment 'GUIDE' -> Free Ebook PDF Delivery",
                    "type": "comment_to_dm",
                    "post_target": "all_posts",
                    "post_thumbnail": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=400&q=80",
                    "post_caption": "Free 2026 Growth Blueprint guide! Comment 'GUIDE' to receive it in DMs 📚",
                    "trigger_keywords": ["guide", "ebook", "free", "pdf"],
                    "public_comment_reply": "{Guide sent to your DMs! 📚|Check your direct messages for the free guide! 🎁}",
                    "comment_replies": [
                        "Guide sent to your DMs! 📚",
                        "Check your direct messages for the free guide! 🎁"
                    ],
                    "opening_dm": "Hey {name}! Click below to get your Free Growth Guide delivered right now ✨",
                    "button_text": "Get the Free Guide",
                    "dm_message": "Hi {first_name}! Here is your Free 2026 Growth Blueprint guide: https://mywebsite.com/growth-guide.pdf Enjoy reading! 🚀",
                    "delivery_link": "https://mywebsite.com/growth-guide.pdf",
                    "require_follow": False,
                    "ask_email": False,
                    "tags": ["Ebook Download", "Warm Lead"],
                    "is_active": False
                }
            ]
            self._save_raw(seed)
            return seed

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_raw(self, data: List[Dict[str, Any]]):
        self._ensure_dir()
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _save(self):
        self._save_raw(self._rules)

    def get_all(self) -> List[Dict[str, Any]]:
        return list(self._rules)

    def get_by_id(self, rule_id: str) -> Optional[Dict[str, Any]]:
        for r in self._rules:
            if r.get("id") == rule_id:
                return r
        return None

    def create(self, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        new_id = f"rule_{int(os.urandom(3).hex(), 16)}"
        rule_data["id"] = new_id
        if "is_active" not in rule_data:
            rule_data["is_active"] = True
        self._rules.append(rule_data)
        self._save()
        return rule_data

    def update(self, rule_id: str, rule_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for idx, r in enumerate(self._rules):
            if r.get("id") == rule_id:
                rule_data["id"] = rule_id
                self._rules[idx] = rule_data
                self._save()
                return rule_data
        return None

    def delete(self, rule_id: str) -> bool:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.get("id") != rule_id]
        if len(self._rules) < before:
            self._save()
            return True
        return False

    def toggle_active(self, rule_id: str) -> Optional[bool]:
        for r in self._rules:
            if r.get("id") == rule_id:
                r["is_active"] = not r.get("is_active", False)
                self._save()
                return r["is_active"]
        return None

    def match_comment(self, comment_text: str, username: str = "User", post_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Evaluates a comment against active comment_to_dm rules.
        Returns the resolved responses or None.
        """
        clean_text = comment_text.lower().strip()

        for rule in self._rules:
            if not rule.get("is_active"):
                continue
            if rule.get("type") != "comment_to_dm":
                continue

            # Check post target if specified
            if rule.get("post_target") and rule.get("post_target") != "all_posts":
                if post_url and rule.get("post_target") not in post_url:
                    continue

            # Check keywords
            keywords = rule.get("trigger_keywords", [])
            matched = False
            if "*" in keywords:
                matched = True
            else:
                for kw in keywords:
                    kw_clean = kw.lower().strip()
                    if kw_clean and (kw_clean in clean_text or re.search(rf"\b{re.escape(kw_clean)}\b", clean_text)):
                        matched = True
                        break

            if matched:
                context = {"username": username, "name": username}
                public_reply = SpintaxEngine.spin(rule.get("public_comment_reply", ""), context)
                dm_reply = SpintaxEngine.spin(rule.get("dm_message", ""), context)

                return {
                    "matched": True,
                    "rule_id": rule.get("id"),
                    "rule_name": rule.get("name"),
                    "trigger_type": "comment_to_dm",
                    "public_reply": public_reply,
                    "dm_reply": dm_reply,
                    "tags": rule.get("tags", [])
                }

        return None

    def match_dm(self, message_text: str, username: str = "User") -> Optional[Dict[str, Any]]:
        """
        Evaluates an incoming DM message against active dm_keyword rules.
        """
        clean_text = message_text.lower().strip()

        for rule in self._rules:
            if not rule.get("is_active"):
                continue
            if rule.get("type") != "dm_keyword":
                continue

            keywords = rule.get("trigger_keywords", [])
            matched = False
            if "*" in keywords:
                matched = True
            else:
                for kw in keywords:
                    kw_clean = kw.lower().strip()
                    if kw_clean and (kw_clean in clean_text or re.search(rf"\b{re.escape(kw_clean)}\b", clean_text)):
                        matched = True
                        break

            if matched:
                context = {"username": username, "name": username}
                dm_reply = SpintaxEngine.spin(rule.get("dm_message", ""), context)

                return {
                    "matched": True,
                    "rule_id": rule.get("id"),
                    "rule_name": rule.get("name"),
                    "trigger_type": "dm_keyword",
                    "public_reply": "",
                    "dm_reply": dm_reply,
                    "tags": rule.get("tags", [])
                }

        return None
