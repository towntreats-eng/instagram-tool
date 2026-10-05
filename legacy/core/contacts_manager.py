import os
import json
import csv
from io import StringIO
from datetime import datetime
from typing import List, Dict, Any, Optional

from core import store

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTACTS_FILE = os.path.join(BASE_DIR, "data", "contacts.json")

class ContactsManager:
    """
    Contact and lead CRM:
    Records users who interacted via comments or DMs, their tags,
    sources, and conversation history.
    """

    def __init__(self, file_path: str = CONTACTS_FILE):
        self.file_path = file_path
        self._ensure_dir()
        self._contacts: List[Dict[str, Any]] = self._load()

    def _ensure_dir(self):
        folder = os.path.dirname(self.file_path)
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)

    def _load(self) -> List[Dict[str, Any]]:
        if not store.exists(self.file_path):
            self._save_raw([])
            return []
        try:
            return store.read(self.file_path)
        except Exception:
            return []

    def _save_raw(self, data: List[Dict[str, Any]]):
        self._ensure_dir()
        store.write(self.file_path, data)

    def _save(self):
        self._save_raw(self._contacts)

    def get_all(self, search: Optional[str] = None, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        contacts = list(self._contacts)
        if search:
            s = search.lower()
            contacts = [c for c in contacts if s in c.get("username", "").lower() or s in c.get("name", "").lower()]
        if tag:
            t = tag.lower()
            contacts = [c for c in contacts if any(t == existing_tag.lower() for existing_tag in c.get("tags", []))]
        return contacts

    def record_interaction(self, username: str, name: str = "", source: str = "Auto-Automation", new_tags: List[str] = None, tags: List[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Creates or updates a contact when an automated event happens.
        """
        effective_tags = new_tags or tags or []
        clean_user = username.strip().lstrip("@")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        existing = None
        for c in self._contacts:
            if c.get("username", "").lower() == clean_user.lower():
                existing = c
                break

        if existing:
            existing["last_interaction"] = now_str
            existing["messages_count"] = existing.get("messages_count", 0) + 1
            if name and not existing.get("name"):
                existing["name"] = name
            if effective_tags:
                current_tags = set(existing.get("tags", []))
                current_tags.update(effective_tags)
                existing["tags"] = list(current_tags)
            self._save()
            return existing
        else:
            new_id = max([c.get("id", 0) for c in self._contacts], default=0) + 1
            record = {
                "id": new_id,
                "username": clean_user,
                "name": name or clean_user,
                "tags": effective_tags or ["New Lead"],
                "source": source,
                "first_seen": now_str,
                "last_interaction": now_str,
                "messages_count": 1
            }
            self._contacts.insert(0, record)
            self._save()
            return record

    def remove_where(self, match) -> int:
        """Delete every contact `match(contact)` says yes to. Returns the count.

        Added for Meta's data-deletion callback, which has to actually remove
        the records captured from a merchant's comments rather than claim to.
        """
        before = len(self._contacts)
        self._contacts = [c for c in self._contacts if not match(c)]
        removed = before - len(self._contacts)
        if removed:
            self._save()
        return removed

    def export_csv(self) -> str:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Username", "Name", "Tags", "Source", "First Seen", "Last Interaction", "Messages Count"])
        for c in self._contacts:
            writer.writerow([
                c.get("id"),
                c.get("username"),
                c.get("name"),
                ", ".join(c.get("tags", [])),
                c.get("source"),
                c.get("first_seen"),
                c.get("last_interaction"),
                c.get("messages_count")
            ])
        return output.getvalue()

    upsert_contact = record_interaction
