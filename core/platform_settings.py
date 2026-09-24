"""
ConverFlow — Platform Settings
==============================
Everything the owner configures once and every workspace inherits:
brand details, billing setup, safety defaults, the Meta app used for
"Connect Instagram", feature flags and the notification templates.

Secrets (app secret, Razorpay key secret) are stored here but never sent
to the browser in full — public() masks them.
"""

import os
import json
import copy
from datetime import datetime
from typing import Dict, Any, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
TEMPLATES_FILE = os.path.join(DATA_DIR, "templates.json")

ISO = "%Y-%m-%dT%H:%M:%S"
SECRET_FIELDS = {("meta_app", "app_secret"), ("billing", "razorpay_key_secret")}

# Permissions the Connect-Instagram flow asks Instagram for.
# These scopes work with the Instagram API via Instagram Login
# (api.instagram.com/oauth/authorize) — NOT the Facebook Login flow.
DEFAULT_SCOPES = [
    "instagram_business_basic",
    "instagram_business_manage_messages",
    "instagram_business_manage_comments",
    "instagram_business_content_publish",
]



def _now() -> str:
    return datetime.now().strftime(ISO)


def mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "•" * len(value)
    return value[:4] + "•" * 8 + value[-4:]


class PlatformSettings:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.settings = self._load_settings()
        self.templates = self._load_templates()

    # ------------------------------------------------------------------ io
    def _defaults(self) -> Dict[str, Any]:
        return {
            "brand": {
                "name": "ConverFlow",
                "tagline": "Turn every Instagram comment into a paying customer",
                "support_email": "hello@umangsatnam.in",
                "whatsapp": "+91 88498 66193",
                "website": "https://satnamwebservices.com",
                "company": "Satnam Web Services",
                "address": "Shalin Complex, above Design Womens, Unjha, Gujarat",
                "gstin": "",
            },
            "billing": {
                "currency": "INR",
                "gst_percent": 18,
                "payment_mode": "manual",          # manual | razorpay
                "razorpay_key_id": "",
                "razorpay_key_secret": "",
                "invoice_prefix": "CF",
            },
            "safety": {
                "min_delay_seconds": 45,
                "max_delay_seconds": 90,
                "daily_dm_cap": 35,
                "watcher_interval_seconds": 60,
                "pause_on_error": True,
            },
            "meta_app": {
                "enabled": True,
                "app_id": "874373775643660",
                "app_secret": "bcab0149ec7f0ff2b389cdfe2b712798",
                "redirect_uri": "https://instagram-tool-production-c3f0.up.railway.app/api/instagram/callback",
                "verify_token": "converflow_webhook_token",
                "webhook_url": "https://instagram-tool-production-c3f0.up.railway.app/api/meta/webhook",
                "api_version": "v21.0",
                "scopes": list(DEFAULT_SCOPES),
                "configured_at": None,
                "last_test": None,
                "last_test_ok": None,
            },
            "flags": {
                "signups_open": True,
                "maintenance_mode": False,
                "show_trial_banner": True,
                "allow_browser_login": True,
                "require_email_verification": False,
            },
            "updated_at": _now(),
        }

    def _load_settings(self) -> Dict[str, Any]:
        base = self._defaults()
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                for section, values in saved.items():
                    if isinstance(values, dict) and section in base:
                        base[section].update(values)
                    else:
                        base[section] = values
                return base
            except Exception:
                pass
        self._write(SETTINGS_FILE, base)
        return base

    def _load_templates(self) -> List[Dict[str, Any]]:
        if os.path.exists(TEMPLATES_FILE):
            try:
                with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and "templates" in data:
                    return data["templates"]
                if isinstance(data, list):
                    return data
            except Exception:
                pass
        seeded = self._seed_templates()
        self._write(TEMPLATES_FILE, {"templates": seeded})
        return seeded

    def _write(self, path: str, data: Any) -> None:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)

    def save(self) -> None:
        self.settings["updated_at"] = _now()
        self._write(SETTINGS_FILE, self.settings)

    def save_templates(self) -> None:
        self._write(TEMPLATES_FILE, {"templates": self.templates, "updated_at": _now()})

    # ---------------------------------------------------------- templates
    def _seed_templates(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "welcome",
                "name": "Welcome",
                "when": "Sent right after someone creates a workspace",
                "subject": "Your ConverFlow workspace is ready, {{first_name}}",
                "body": ("Hi {{first_name}},\n\n"
                         "Your ConverFlow workspace for {{business}} is live. You're on the "
                         "{{plan_name}} plan with {{trial_days}} days free.\n\n"
                         "Three things worth doing first:\n"
                         "1. Connect your Instagram account\n"
                         "2. Pick a reel and set your trigger keyword\n"
                         "3. Test it on the Flow Tester before going live\n\n"
                         "Reply to this email if you get stuck — a real person answers.\n\n"
                         "{{brand_name}}"),
                "enabled": True,
            },
            {
                "id": "ig_connected",
                "name": "Instagram connected",
                "when": "Sent when a workspace links its Instagram account",
                "subject": "@{{ig_handle}} is connected",
                "body": ("Hi {{first_name}},\n\n"
                         "@{{ig_handle}} is now connected to ConverFlow. Comment and DM triggers "
                         "will start firing as soon as you switch an automation on.\n\n"
                         "{{brand_name}}"),
                "enabled": True,
            },
            {
                "id": "trial_ending",
                "name": "Trial ending",
                "when": "Sent 3 days before a trial expires",
                "subject": "{{days_left}} days left on your ConverFlow trial",
                "body": ("Hi {{first_name}},\n\n"
                         "Your trial ends on {{expiry_date}}. Your automations captured "
                         "{{contacts}} contacts and sent {{dms_sent}} DMs so far — all of that "
                         "stays put if you upgrade.\n\n"
                         "{{plan_name}} is {{price}}/month. Upgrade here: {{upgrade_url}}\n\n"
                         "{{brand_name}}"),
                "enabled": True,
            },
            {
                "id": "trial_expired",
                "name": "Trial expired",
                "when": "Sent the day a trial runs out",
                "subject": "Your automations are paused",
                "body": ("Hi {{first_name}},\n\n"
                         "Your trial has ended, so your automations are paused. Nothing is "
                         "deleted — your contacts, flows and tags are exactly where you left them.\n\n"
                         "Switch everything back on: {{upgrade_url}}\n\n"
                         "{{brand_name}}"),
                "enabled": True,
            },
            {
                "id": "payment_received",
                "name": "Payment received",
                "when": "Sent after a successful payment",
                "subject": "Payment received — invoice {{invoice_no}}",
                "body": ("Hi {{first_name}},\n\n"
                         "We've received {{amount}} for the {{plan_name}} plan. Your next renewal "
                         "is {{renews_on}}.\n\n"
                         "Invoice {{invoice_no}} is attached, GST included.\n\n"
                         "{{brand_name}}"),
                "enabled": True,
            },
            {
                "id": "suspended",
                "name": "Workspace suspended",
                "when": "Sent when an account is suspended",
                "subject": "Your ConverFlow workspace is on hold",
                "body": ("Hi {{first_name}},\n\n"
                         "We've put your workspace on hold. Your data is safe and nothing has "
                         "been deleted.\n\n"
                         "Write to {{support_email}} and we'll sort it out.\n\n"
                         "{{brand_name}}"),
                "enabled": True,
            },
        ]

    def list_templates(self) -> List[Dict[str, Any]]:
        return self.templates

    def get_template(self, tid: str) -> Optional[Dict[str, Any]]:
        return next((t for t in self.templates if t["id"] == tid), None)

    def save_template(self, tid: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        tpl = self.get_template(tid)
        if not tpl:
            return None
        for key in ("name", "subject", "body", "enabled", "when"):
            if key in patch and patch[key] is not None:
                tpl[key] = patch[key]
        self.save_templates()
        return tpl

    def render_template(self, tid: str, context: Dict[str, Any]) -> Optional[Dict[str, str]]:
        tpl = self.get_template(tid)
        if not tpl:
            return None
        ctx = {
            "brand_name": self.settings["brand"]["name"],
            "support_email": self.settings["brand"]["support_email"],
            **{k: str(v) for k, v in context.items()},
        }
        def fill(text: str) -> str:
            for key, value in ctx.items():
                text = text.replace("{{" + key + "}}", value)
            return text
        return {"subject": fill(tpl["subject"]), "body": fill(tpl["body"])}

    # ----------------------------------------------------------- settings
    def section(self, name: str) -> Dict[str, Any]:
        return self.settings.get(name, {})

    def update_section(self, name: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        target = self.settings.setdefault(name, {})
        for key, value in patch.items():
            if value is None:
                continue
            # an unchanged masked secret must not overwrite the real one
            if (name, key) in SECRET_FIELDS and set(str(value)) <= {"•"} | set(str(target.get(key, ""))[:4] + str(target.get(key, ""))[-4:]):
                if "•" in str(value):
                    continue
            target[key] = value
        if name == "meta_app":
            target["configured_at"] = _now()
            target["enabled"] = bool(target.get("app_id") and target.get("app_secret"))
        self.save()
        return target

    def meta_app(self) -> Dict[str, Any]:
        return self.settings["meta_app"]

    def meta_ready(self) -> bool:
        app = self.meta_app()
        return bool(app.get("app_id") and app.get("app_secret") and app.get("redirect_uri"))

    def record_meta_test(self, ok: bool) -> None:
        self.settings["meta_app"]["last_test"] = _now()
        self.settings["meta_app"]["last_test_ok"] = ok
        self.save()

    def public(self) -> Dict[str, Any]:
        """Settings safe to hand to the admin browser — secrets masked."""
        data = copy.deepcopy(self.settings)
        for sect, key in SECRET_FIELDS:
            if data.get(sect, {}).get(key):
                data[sect][key] = mask(data[sect][key])
        data["meta_app"]["ready"] = self.meta_ready()
        return data

    def brand_public(self) -> Dict[str, Any]:
        """What the marketing site and dashboard may read."""
        return {
            "brand": self.settings["brand"],
            "flags": self.settings["flags"],
            "instagram_ready": self.meta_ready(),
            "currency": self.settings["billing"]["currency"],
        }
