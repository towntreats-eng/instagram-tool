"""
Platform configuration.

Secrets never live in source. Each value is read from an environment variable
first (Railway > Variables), then from the database (Admin > Instagram), and
the source only ever carries blanks. The repository is public; anything typed
here is published.
"""

import json
import hashlib
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
    # Platform / Brand
    "brand_name": "BRAND_NAME",
    "support_email": "SUPPORT_EMAIL",
    "support_whatsapp": "SUPPORT_WHATSAPP",
    # SMTP
    "smtp_host": "SMTP_HOST",
    "smtp_port": "SMTP_PORT",
    "smtp_user": "SMTP_USER",
    "smtp_password": "SMTP_PASSWORD",
    "smtp_from_email": "SMTP_FROM_EMAIL",
    "smtp_from_name": "SMTP_FROM_NAME",
    "smtp_enabled": "SMTP_ENABLED",
    # Gateways
    "razorpay_key_id": "RAZORPAY_KEY_ID",
    "razorpay_key_secret": "RAZORPAY_KEY_SECRET",
    "razorpay_webhook_secret": "RAZORPAY_WEBHOOK_SECRET",
    "stripe_publishable_key": "STRIPE_PUBLISHABLE_KEY",
    "stripe_secret_key": "STRIPE_SECRET_KEY",
    "stripe_webhook_secret": "STRIPE_WEBHOOK_SECRET",
}

DEFAULTS = {
    "ig_app_id": "",
    "ig_app_secret": "",       # Instagram > API setup with Instagram login (OAuth)
    "meta_app_secret": "",     # App settings > Basic (signs webhooks)
    "verify_token": "converflow_webhook_token",   # kept: Meta already has it
    "base_url": "",
    "graph_version": "v24.0",
    # Platform / Brand
    "brand_name": "DM Flow",
    "support_email": "hello@umangsatnam.in",
    "support_whatsapp": "+91 88498 66193",
    "company_name": "Satnam Web Services",
    "announcement": "",
    "maintenance_mode": "0",
    "signups_open": "1",
    # Email / SMTP
    "smtp_enabled": "0",
    "smtp_host": "",
    "smtp_port": "587",
    "smtp_user": "",
    "smtp_password": "",
    "smtp_from_name": "DM Flow",
    "smtp_from_email": "",
    "smtp_security": "tls",
    "email_welcome_enabled": "1",
    "email_ticket_enabled": "1",
    "email_lifetime_enabled": "1",
    "smtp_provider": "gmail",          # gmail | custom
    "email_payment_enabled": "1",      # receipt after a successful payment
    "email_payment_failed_enabled": "1",
    "email_renewal_enabled": "1",      # reminder a few days before the plan ends
    "email_expired_enabled": "1",      # plan ended, moved to Free
    "email_admin_alerts_enabled": "1", # owner hears about new signups and payments
    "admin_alert_email": "",           # blank = support_email
    "renewal_reminder_days": "3",
    "company_address": "Shalin Complex, Unjha, Gujarat, India",
    "company_gstin": "",
    # Payment Gateway
    "payment_gateway": "razorpay",
    "payment_mode": "manual",  # manual | test | live
    "currency": "INR",
    "tax_percent": "18",
    "invoice_prefix": "DMF",
    "razorpay_enabled": "0",
    "razorpay_key_id": "",
    "razorpay_key_secret": "",
    "razorpay_webhook_secret": "",
    "stripe_enabled": "0",
    "stripe_publishable_key": "",
    "stripe_secret_key": "",
    "stripe_webhook_secret": "",
}

SECRETS = {
    "ig_app_secret", "meta_app_secret", "smtp_password",
    "razorpay_key_secret", "razorpay_webhook_secret",
    "stripe_secret_key", "stripe_webhook_secret"
}

# Only what the product actually does. No feature appears on the pricing page
# that the code does not deliver. -1 means unlimited.
DEFAULT_PLANS: List[Dict[str, Any]] = [
    {"id": "free", "name": "Free", "tagline": "One automation, free forever",
     "price_monthly": 0, "price_yearly": 0, "trial_days": 0, "highlight": False,
     "badge": "Free forever", "is_active": True,
     "limits": {"automations": 1, "contacts": 100, "dms_per_month": 200, "ig_accounts": 1},
     "features": {"comment_to_dm": True, "follow_gate": True, "any_post": False, "priority_support": False}},
    {"id": "starter", "name": "Starter", "tagline": "For creators posting every week",
     "price_monthly": 399, "price_yearly": 3990, "trial_days": 0, "highlight": False,
     "badge": "", "is_active": True,
     "limits": {"automations": 5, "contacts": 1000, "dms_per_month": 2000, "ig_accounts": 1},
     "features": {"comment_to_dm": True, "follow_gate": True, "any_post": True, "priority_support": False}},
    {"id": "growth", "name": "Growth", "tagline": "For brands selling every day",
     "price_monthly": 799, "price_yearly": 7990, "trial_days": 15, "highlight": True,
     "badge": "Most popular", "is_active": True,
     "limits": {"automations": -1, "contacts": 5000, "dms_per_month": 15000, "ig_accounts": 1},
     "features": {"comment_to_dm": True, "follow_gate": True, "any_post": True,
                  "priority_support": True}},
    {"id": "lifetime", "name": "Lifetime VIP", "tagline": "Full platform access forever",
     "price_monthly": 0, "price_yearly": 0, "trial_days": 0, "highlight": False,
     "badge": "Lifetime Free", "is_active": True,
     "limits": {"automations": -1, "contacts": -1, "dms_per_month": -1, "ig_accounts": -1},
     "features": {"comment_to_dm": True, "follow_gate": True, "any_post": True,
                  "priority_support": True, "ai_assist": True, "csv_export": True}},
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


def save_plans(plans_list: List[Dict[str, Any]]) -> None:
    put("plans", db.jdump(plans_list))


def reset_plans() -> List[Dict[str, Any]]:
    put("plans", db.jdump(DEFAULT_PLANS))
    return DEFAULT_PLANS


def plan(plan_id: str) -> Dict[str, Any]:
    for p in plans():
        if p.get("id") == plan_id:
            return p
    return plans()[0]


def user_plan(user: Dict[str, Any]) -> Dict[str, Any]:
    p = dict(plan(user.get("plan") or "free"))
    if user.get("is_lifetime"):
        p["is_lifetime"] = True
        p["badge"] = "Lifetime VIP"
        p["limits"] = {"automations": -1, "contacts": -1, "dms_per_month": -1, "ig_accounts": -1}
        p["features"] = {**p.get("features", {}), "comment_to_dm": True, "follow_gate": True,
                         "any_post": True, "priority_support": True, "ai_assist": True, "csv_export": True}
    return p


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
    _owner_upgrade()
    stats["accounts_cleared"] = _clear_seeded_connections()
    return stats

OWNER_EMAILS = ("umangsatnam11@gmail.com", "umangptl11@gmail.com", "hello@umangsatnam.in")

# sha256 of an Instagram token that an earlier build hardcoded and attached to
# every workspace. Any row still holding it is not a real connection: drop it
# so the owner reconnects through Instagram. (Only the hash lives here.)
_SEEDED_TOKEN_SHA256 = "61c226de9e0bc14fb74b391a5dd5bdf0f4c3ee0632be148005c38f5b17f0bbe9"


def _owner_upgrade() -> None:
    marks = ",".join("?" for _ in OWNER_EMAILS)
    db.execute(f"UPDATE dm_users SET is_lifetime = 1, plan = 'lifetime' WHERE email IN ({marks})", OWNER_EMAILS)


def _clear_seeded_connections() -> int:
    cleared = 0
    for row in db.query("SELECT user_id, token FROM dm_ig"):
        if hashlib.sha256((row.get("token") or "").encode()).hexdigest() == _SEEDED_TOKEN_SHA256:
            db.execute("DELETE FROM dm_ig WHERE user_id = ?", (row["user_id"],))
            db.execute("DELETE FROM dm_poll WHERE user_id = ?", (row["user_id"],))
            cleared += 1
    return cleared


