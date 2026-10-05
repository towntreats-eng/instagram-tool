"""
Platform configuration.

Secrets never live in source. Each value is read from an environment variable
first (Railway > Variables), then from the database (Admin > Instagram), and
the source only ever carries blanks. The repository is public; anything typed
here is published.
"""

import json
import os
from typing import Any, Dict, List

from dmflow import db

# key -> environment variable that overrides it
ENV = {
    "ig_app_id": "IG_APP_ID",
    "ig_app_secret": "IG_APP_SECRET",
    "meta_app_secret": "META_APP_SECRET",
    "verify_token": "VERIFY_TOKEN",
    "base_url": "BASE_URL",
    "graph_version": "GRAPH_VERSION",
}

DEFAULTS = {
    "ig_app_id": "",
    "ig_app_secret": "",       # Instagram > API setup with Instagram login (OAuth)
    "meta_app_secret": "",     # App settings > Basic (signs webhooks)
    "verify_token": "converflow_webhook_token",   # kept: Meta already has it
    "base_url": "",
    "graph_version": "v24.0",
}

SECRETS = {"ig_app_secret", "meta_app_secret"}

# Only what the product actually does. No feature appears on the pricing page
# that the code does not deliver. -1 means unlimited.
DEFAULT_PLANS: List[Dict[str, Any]] = [
    {"id": "free", "name": "Free", "tagline": "One automation, free forever",
     "price_monthly": 0, "price_yearly": 0, "trial_days": 0, "highlight": False,
     "badge": "Free forever",
     "limits": {"automations": 1, "contacts": 100, "dms_per_month": 200, "ig_accounts": 1},
     "features": {"comment_to_dm": True, "follow_gate": True, "any_post": False}},
    {"id": "starter", "name": "Starter", "tagline": "For creators posting every week",
     "price_monthly": 399, "price_yearly": 3990, "trial_days": 0, "highlight": False,
     "badge": "",
     "limits": {"automations": 5, "contacts": 1000, "dms_per_month": 2000, "ig_accounts": 1},
     "features": {"comment_to_dm": True, "follow_gate": True, "any_post": True}},
    {"id": "growth", "name": "Growth", "tagline": "For brands selling every day",
     "price_monthly": 799, "price_yearly": 7990, "trial_days": 15, "highlight": True,
     "badge": "Most popular",
     "limits": {"automations": -1, "contacts": 5000, "dms_per_month": 15000, "ig_accounts": 1},
     "features": {"comment_to_dm": True, "follow_gate": True, "any_post": True,
                  "priority_support": True}},
]


def _raw(key: str) -> str:
    row = db.one("SELECT value FROM dm_settings WHERE key = ?", (key,))
    return row["value"] if row else ""


def get(key: str) -> str:
    env = ENV.get(key)
    if env and (os.environ.get(env) or "").strip():
        return os.environ[env].strip()
    val = _raw(key)
    return val if val else DEFAULTS.get(key, "")


def source(key: str) -> str:
    """Where a value comes from - shown in Admin so nobody edits a field that
    an environment variable silently overrides."""
    env = ENV.get(key)
    if env and (os.environ.get(env) or "").strip():
        return "env"
    return "db" if _raw(key) else "default"


def put(key: str, value: str) -> None:
    db.execute("INSERT INTO dm_settings (key, value) VALUES (?, ?) "
               "ON CONFLICT (key) DO UPDATE SET value = excluded.value", (key, value or ""))


def public_view() -> Dict[str, Any]:
    out = {}
    for key in DEFAULTS:
        val = get(key)
        if key in SECRETS:
            val = ("•" * 8 + val[-4:]) if val else ""
        out[key] = {"value": val, "source": source(key)}
    return out


def plans() -> List[Dict[str, Any]]:
    stored = db.jload(_raw("plans"), None)
    return stored if isinstance(stored, list) and stored else DEFAULT_PLANS


def plan(plan_id: str) -> Dict[str, Any]:
    for p in plans():
        if p["id"] == plan_id:
            return p
    return plans()[0]


def base_url(request=None) -> str:
    """The public address of this app, https on any real host."""
    fixed = get("base_url").rstrip("/")
    if fixed:
        return fixed
    if request is None:
        return ""
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip()
    proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    local = host.split(":")[0] in ("localhost", "127.0.0.1", "0.0.0.0")
    scheme = proto or ("http" if local else "https")
    if not local:
        scheme = "https"
    return f"{scheme}://{host}" if host else str(request.base_url).rstrip("/")


def instagram_ready() -> bool:
    return bool(get("ig_app_id") and get("ig_app_secret"))


# ------------------------------------------------------------------ migration
def import_legacy() -> Dict[str, int]:
    """First boot only: bring over logins and the Meta app from the old app.

    Reads the old `documents` table (Postgres) or the old data/*.json files
    (local). Never overwrites anything already set here, so running it twice
    is harmless.
    """
    stats = {"users": 0, "settings": 0}
    users_doc, settings_doc = None, None
    if db.is_postgres():
        try:
            for row in db.query("SELECT name, body FROM documents WHERE name IN ('users', 'settings')"):
                body = row["body"] if isinstance(row["body"], dict) else db.jload(row["body"], {})
                if row["name"] == "users":
                    users_doc = body
                else:
                    settings_doc = body
        except Exception:
            pass
    else:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for name in ("users", "settings"):
            path = os.path.join(root, "data", name + ".json")
            if os.path.exists(path):
                try:
                    body = json.load(open(path, encoding="utf-8"))
                    if name == "users":
                        users_doc = body
                    else:
                        settings_doc = body
                except Exception:
                    pass

    if users_doc and not db.one("SELECT id FROM dm_users LIMIT 1"):
        rows = users_doc.get("users", []) if isinstance(users_doc, dict) else users_doc
        for u in rows or []:
            email = (u.get("email") or "").strip().lower()
            if not email or not u.get("password_hash"):
                continue
            db.execute(
                "INSERT INTO dm_users (id, email, name, password_hash, role, status, plan, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (email) DO NOTHING",
                (u.get("id") or db.new_id("u_"), email, u.get("name") or "",
                 u["password_hash"], "admin" if u.get("role") == "admin" else "owner",
                 u.get("status") or "active", u.get("plan") or "free", db.now()))
            stats["users"] += 1

    meta = (settings_doc or {}).get("meta_app", {}) if isinstance(settings_doc, dict) else {}
    for old, new in (("app_id", "ig_app_id"), ("app_secret", "ig_app_secret"),
                     ("webhook_secret", "meta_app_secret"), ("verify_token", "verify_token")):
        val = str(meta.get(old) or "").strip()
        if val and not _raw(new):
            put(new, val)
            stats["settings"] += 1
    return stats
