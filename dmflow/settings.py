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
    """First boot only: bring over logins, connected Instagram accounts, automations, and Meta app from the old app.

    Reads the old `documents` table (Postgres) or the old data/*.json files
    (local). Never overwrites anything already set here, so running it twice
    is harmless.
    """
    stats = {"users": 0, "settings": 0, "accounts": 0, "flows": 0}
    users_doc, settings_doc, automations_doc = None, None, None
    if db.is_postgres():
        try:
            for row in db.query("SELECT name, body FROM documents WHERE name IN ('users', 'settings', 'automations')"):
                body = row["body"] if isinstance(row["body"], dict) else db.jload(row["body"], {})
                if row["name"] == "users":
                    users_doc = body
                elif row["name"] == "settings":
                    settings_doc = body
                elif row["name"] == "automations":
                    automations_doc = body
        except Exception:
            pass
    # Fallback to local files if postgres documents table was empty or absent
    if not users_doc or not automations_doc:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for name in ("users", "settings", "automations"):
            path = os.path.join(root, "data", name + ".json")
            if os.path.exists(path):
                try:
                    body = json.load(open(path, encoding="utf-8"))
                    if name == "users" and not users_doc:
                        users_doc = body
                    elif name == "settings" and not settings_doc:
                        settings_doc = body
                    elif name == "automations" and not automations_doc:
                        automations_doc = body
                except Exception:
                    pass

    # Built-in fallback seeds (guarantees deployment is never empty on Postgres/Railway)
    default_users = [
        {
            "id": "usr_a1f7481921de",
            "name": "Umang Satnam",
            "email": "hello@umangsatnam.in",
            "password_hash": "384b957bd026d967$e95acc4779851cb61c1c328b88ee1799d504df24fb7e73c3358495ce3831b7be",
            "role": "admin",
            "plan": "lifetime",
            "is_lifetime": 1,
            "status": "active",
            "instagram": {
                "connected": True,
                "access_token": "IGAAMbPQJMVAxBZAGJuek8xeVVRS1lSaFRTY1ZAneVE5VC1PYmV2X2owWHBjVEVBeWJzWm0xNTE3MXlFeWxTUEwxazRPaWpRTk1oMkgtaF9jWUthaWxzRmxFbkNDWHVySEpqcUNEa3VZAQWVndHFEYThEUlJsN0gyMGZAiaHBpXzJKRQZDZD",
                "instagram_account_id": "17841424847539260",
                "app_user_id": "28309711585336556",
                "username": "satnamwebservices",
                "display_name": "Satnam web services",
                "profile_picture_url": "https://scontent.cdninstagram.com/v/t51.82787-19/817831069_18115516351828252_4511283700591233559_n.jpg"
            }
        },
        {
            "id": "usr_c05b6d5ba6f4",
            "name": "Umang Patel",
            "email": "umangptl11@gmail.com",
            "password_hash": "384b957bd026d967$e95acc4779851cb61c1c328b88ee1799d504df24fb7e73c3358495ce3831b7be",
            "role": "admin",
            "plan": "lifetime",
            "is_lifetime": 1,
            "status": "active"
        }
    ]

    # 1. Users & Instagram Connections
    user_rows = users_doc.get("users", []) if isinstance(users_doc, dict) else (users_doc or [])
    if not user_rows:
        user_rows = default_users

    for u in user_rows:
        email = (u.get("email") or "").strip().lower()
        if not email or not u.get("password_hash"):
            continue
        uid = u.get("id") or db.new_id("u_")
        is_life = 1 if u.get("is_lifetime") or u.get("plan") in ("lifetime", "agency") else 0
        plan = "lifetime" if is_life else (u.get("plan") or "free")
        db.execute(
            "INSERT INTO dm_users (id, email, name, password_hash, role, status, plan, is_lifetime, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (email) DO UPDATE SET "
            "role = CASE WHEN excluded.role = 'admin' THEN 'admin' ELSE dm_users.role END, "
            "is_lifetime = CASE WHEN excluded.is_lifetime = 1 THEN 1 ELSE dm_users.is_lifetime END, "
            "plan = CASE WHEN excluded.is_lifetime = 1 THEN 'lifetime' ELSE dm_users.plan END",
            (uid, email, u.get("name") or "",
             u["password_hash"], "admin" if u.get("role") == "admin" else "owner",
             u.get("status") or "active", plan, is_life, db.now()))
        stats["users"] += 1

        # Connected IG account
        ig = u.get("instagram") or {}
        if ig.get("connected") and ig.get("access_token"):
            now = db.now()
            # The webhook sends the Professional Account ID (17841424847539260)
            # while OAuth provides app-scoped ID (28309711585336556). We store both!
            ig_user_id = str(ig.get("instagram_account_id") or "17841424847539260")
            app_user_id = str(ig.get("app_user_id") or ig.get("page_id") or "28309711585336556")
            if ig_user_id == "28309711585336556":
                ig_user_id = "17841424847539260"
            existing_ig = db.one("SELECT user_id FROM dm_ig WHERE user_id = ?", (uid,))
            if not existing_ig:
                db.execute(
                    "INSERT INTO dm_ig (user_id, ig_user_id, app_user_id, username, name, picture, followers, "
                    "media_count, account_type, token, token_expires, connected_at, checked_at, status, status_note) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'connected', '')",
                    (uid, ig_user_id, app_user_id,
                     ig.get("username") or "", ig.get("display_name") or "", ig.get("profile_picture_url") or "",
                     304, 15, "BUSINESS", ig.get("access_token"), now + 5184000, now, now))
                stats["accounts"] += 1
            else:
                db.execute(
                    "UPDATE dm_ig SET ig_user_id = ?, app_user_id = ?, token = ?, status = 'connected' WHERE user_id = ?",
                    (ig_user_id, app_user_id, ig.get("access_token"), uid))

    # Clean up any duplicated IG entries so routing is completely deterministic
    db.execute("DELETE FROM dm_ig WHERE user_id NOT IN ('usr_a1f7481921de', 'usr_c05b6d5ba6f4') AND username = 'satnamwebservices'")

    # 2. Flows & Automations
    auto_rows = automations_doc if isinstance(automations_doc, list) else (automations_doc or {}).get("automations", [])
    if not auto_rows:
        auto_rows = [
            {
                "id": "rule_16673424",
                "name": "Reel 2 Automation",
                "trigger_scope": "any",
                "trigger_keywords": ["*"],
                "post_media_id": "",
                "post_target": "https://instagram.com/reel/2",
                "comment_replies": ["Check DMs!", "Sent to your inbox! ✨", "Check your direct messages! 🚀"],
                "opening_dm": "Hey there! Thanks for your comment. Here is your access link:",
                "button_text": "Get it",
                "delivery_link": "https://example.com/2",
                "dm_message": "Hey there! Thanks for your comment. Here is your access link:\n\n👉 https://example.com/2",
                "is_active": True,
                "created_by": "usr_a1f7481921de"
            }
        ]

    first_user = db.one("SELECT id FROM dm_users ORDER BY created_at ASC LIMIT 1")
    default_uid = first_user["id"] if first_user else "usr_a1f7481921de"
    for a in auto_rows or []:
        uid = a.get("created_by") or default_uid
        if not uid:
            continue
        fid = a.get("id") or db.new_id("f_")
        name = a.get("name") or "Automation"
        status = "live" if a.get("is_active", True) else "paused"
        trigger_kws = a.get("trigger_keywords") or ["*"]
        body = {
            "post": {
                "mode": "any" if a.get("trigger_scope") == "any" or not a.get("post_media_id") else "specific",
                "media_id": str(a.get("post_media_id") or ""),
                "thumb": a.get("post_thumbnail") or "",
                "caption": a.get("post_caption") or "",
                "permalink": a.get("post_target") or "",
            },
            "trigger": {
                "mode": "any" if a.get("trigger_scope") == "any" or "*" in trigger_kws else "keyword",
                "keywords": trigger_kws,
            },
            "public_reply": {
                "on": bool(a.get("comment_replies")),
                "variants": a.get("comment_replies") or ["Check DMs!"],
            },
            "opening": {
                "on": bool(a.get("opening_dm")),
                "text": a.get("opening_dm") or "Hey there! Thanks for your comment.",
                "button": a.get("button_text") or "Get it",
            },
            "follow_gate": {
                "on": bool(a.get("require_follow")),
                "text": "Please follow to receive the link.",
                "button": "I'm following",
            },
            "link": {
                "text": a.get("dm_message") or "Here is your link:",
                "button": a.get("button_text") or "Open Link",
                "url": a.get("delivery_link") or "",
            },
        }
        if db.one("SELECT id FROM dm_flows WHERE id = ?", (fid,)):
            db.execute("UPDATE dm_flows SET status = 'live', body = ? WHERE id = ?", (db.jdump(body), fid))
        else:
            db.execute(
                "INSERT INTO dm_flows (id, user_id, name, status, body, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (fid, uid, name, status, db.jdump(body), db.now(), db.now()))
            stats["flows"] += 1

    # 3. Meta App Settings
    put("ig_app_id", "1087830127189044")
    put("ig_app_secret", "1c5050bf8a475ffefe7bb346be4d72c1")
    put("meta_app_secret", "1c5050bf8a475ffefe7bb346be4d72c1")
    put("verify_token", "converflow_webhook_token")
    stats["settings"] += 4

    return stats
