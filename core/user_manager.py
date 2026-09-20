"""
ConverFlow — Multi-tenant User & Subscription Store
====================================================
Single source of truth for every workspace on the platform.
Backed by data/users.json (swap for Postgres later without touching callers).

A workspace holds: who owns it, which plan it is on, its subscription state,
its connected Instagram account, its usage counters and its payment history.
Plan prices, limits and features are NOT stored here — they are read live from
PlansManager, so an admin price change applies to everyone instantly.
"""

import os
import json
import uuid
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

from core.plans_manager import PlansManager, UNLIMITED

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")

ISO = "%Y-%m-%dT%H:%M:%S"

# Subscription states
TRIALING, ACTIVE, EXPIRED, FREE = "trialing", "active", "expired", "free"

# Old plan values from earlier versions -> new plan ids
LEGACY_PLANS = {"pro": "growth", "trial": "growth", "expired": "growth", "": "free"}

# Kept so older callers that imported this constant still work.
PRO_PRICE_INR = 799


def _now() -> str:
    return datetime.now().strftime(ISO)


def _parse(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in (ISO, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            continue
    return None


def hash_password(raw: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(8)
    digest = hashlib.sha256((salt + raw).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def verify_password(raw: str, stored: str) -> bool:
    if not stored or "$" not in stored:
        return False
    salt, _ = stored.split("$", 1)
    return hash_password(raw, salt) == stored


class UserManager:
    def __init__(self, file_path: str = USERS_FILE, plans: Optional[PlansManager] = None):
        self.file_path = file_path
        self.plans = plans or PlansManager()
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        self._state = self._load()

    # ------------------------------------------------------------------ io
    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                if isinstance(state, dict) and "users" in state:
                    if self._migrate(state["users"]):
                        self._write(state)
                    return state
            except Exception:
                pass
        state = {"users": self._seed(), "updated_at": _now()}
        self._write(state)
        return state

    def _migrate(self, users: List[Dict[str, Any]]) -> bool:
        """Bring records written by earlier versions up to the current shape."""
        changed = False
        for u in users:
            plan = u.get("plan", "")
            if plan in LEGACY_PLANS:
                old = plan
                u["plan"] = LEGACY_PLANS[plan]
                u["subscription_state"] = {
                    "pro": ACTIVE, "trial": TRIALING, "expired": EXPIRED
                }.get(old, FREE)
                changed = True
            if "subscription_state" not in u:
                u["subscription_state"] = ACTIVE if u.get("pro_since") else TRIALING
                changed = True
            if "instagram" not in u:
                u["instagram"] = {"connected": False}
                changed = True
            u.setdefault("stats", {}).setdefault("dms_this_month", u["stats"].get("dms_sent", 0))
        return changed

    def _write(self, state: Dict[str, Any]) -> None:
        state["updated_at"] = _now()
        tmp = self.file_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.file_path)

    def _save(self) -> None:
        self._write(self._state)

    # ---------------------------------------------------------------- seed
    def _seed(self) -> List[Dict[str, Any]]:
        """First-run demo book so the admin dashboard is never an empty shell."""
        now = datetime.now()
        book = [
            ("Umang Satnam", "hello@umangsatnam.in", "satnamwebservices", "Satnam Web Services", "agency", ACTIVE, 120, 3, 1840, 9),
            ("Riya Mehta", "riya@glowcart.in", "glowcart.in", "GlowCart Skincare", "growth", ACTIVE, 640, 5, 2410, 14),
            ("Arjun Nair", "arjun@urbanedge.co", "urbanedge.co", "Urban Edge Apparel", "growth", ACTIVE, 410, 4, 1620, 7),
            ("Sneha Patel", "sneha@kraftly.in", "kraftly.in", "Kraftly Home Decor", "starter", ACTIVE, 190, 2, 310, 3),
            ("Dev Shah", "dev@nutriblend.in", "nutriblend.in", "NutriBlend Foods", "growth", TRIALING, 44, 1, 96, 1),
            ("Kavya Iyer", "kavya@theslowstudio", "theslowstudio", "The Slow Studio", "growth", EXPIRED, 380, 2, 740, 11),
            ("Rohit Verma", "rohit@fitforge.in", "fitforge.in", "FitForge Gym Gear", "growth", ACTIVE, 880, 6, 3120, 18),
            ("Ananya Das", "ananya@petpalsindia", "petpalsindia", "PetPals India", "free", FREE, 22, 1, 44, 0),
        ]
        ages = [96, 74, 61, 42, 4, 130, 88, 2]
        seen = [2, 5, 9, 26, 1, 620, 3, 40]

        users: List[Dict[str, Any]] = []
        for i, (name, email, handle, biz, plan_id, state, contacts, autos, dms, failed) in enumerate(book):
            created = now - timedelta(days=ages[i])
            user = self._blank_user(name=name, email=email, password="converflow123",
                                    ig_handle=handle, business=biz)
            user["created_at"] = created.strftime(ISO)
            user["trial_start"] = created.strftime(ISO)
            user["plan"] = plan_id
            user["subscription_state"] = state
            user["stats"].update({
                "contacts": contacts,
                "automations": autos,
                "active_automations": autos if state == ACTIVE else min(autos, 1),
                "dms_sent": dms,
                "dms_this_month": int(dms * 0.34),
                "dms_failed": failed,
                "last_active": (now - timedelta(hours=seen[i])).strftime(ISO),
            })
            if state == ACTIVE:
                price = (self.plans.get_plan(plan_id) or {}).get("price_monthly", 0)
                started = created + timedelta(days=3)
                months = max(1, int((now - started).days // 30))
                user["pro_since"] = started.strftime(ISO)
                user["renews_on"] = (now + timedelta(days=[12, 21, 6, 17, 0, 0, 27, 0][i] or 15)).strftime(ISO)
                user["payments"] = [{
                    "id": f"pay_{uuid.uuid4().hex[:10]}",
                    "date": (started + timedelta(days=30 * m)).strftime(ISO),
                    "amount": price,
                    "plan": plan_id,
                    "method": "manual",
                    "status": "paid",
                } for m in range(months) if started + timedelta(days=30 * m) <= now]
                last = _parse(user["payments"][-1]["date"]) if user["payments"] else None
                if last is None or (now - last).days > 12:
                    user["payments"].append({
                        "id": f"pay_{uuid.uuid4().hex[:10]}",
                        "date": (now - timedelta(days=[3, 6, 9, 5, 0, 0, 2, 0][i] or 4)).strftime(ISO),
                        "amount": price,
                        "plan": plan_id,
                        "method": "manual",
                        "status": "paid",
                    })
            if i in (0, 1, 6):  # a few demo workspaces already connected Instagram
                user["instagram"] = {
                    "connected": True,
                    "provider": "meta_oauth",
                    "username": handle,
                    "display_name": biz,
                    "followers": [8400, 24100, 15600][[0, 1, 6].index(i)],
                    "connected_at": (created + timedelta(days=1)).strftime(ISO),
                    "instagram_account_id": f"1784{uuid.uuid4().hex[:10]}",
                }
            users.append(user)
        return users

    def _blank_user(self, name: str, email: str, password: str,
                    ig_handle: str = "", business: str = "") -> Dict[str, Any]:
        trial_plan = self.plans.default_paid_plan()
        return {
            "id": f"usr_{uuid.uuid4().hex[:12]}",
            "name": name.strip(),
            "email": email.strip().lower(),
            "password_hash": hash_password(password),
            "ig_handle": ig_handle.lstrip("@").strip(),
            "business": business.strip(),
            "phone": "",
            "role": "owner",
            "plan": trial_plan["id"],
            "subscription_state": TRIALING if trial_plan.get("trial_days") else FREE,
            "status": "active",
            "created_at": _now(),
            "trial_start": _now(),
            "pro_since": None,
            "renews_on": None,
            "coupon": None,
            "notes": "",
            "instagram": {"connected": False},
            "stats": {
                "contacts": 0,
                "automations": 0,
                "active_automations": 0,
                "dms_sent": 0,
                "dms_this_month": 0,
                "dms_failed": 0,
                "last_active": _now(),
            },
            "payments": [],
        }

    # --------------------------------------------------------------- reads
    def all(self) -> List[Dict[str, Any]]:
        return self._state.get("users", [])

    def get(self, user_id: str) -> Optional[Dict[str, Any]]:
        return next((u for u in self.all() if u["id"] == user_id), None)

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        email = (email or "").strip().lower()
        return next((u for u in self.all() if u["email"] == email), None)

    def public(self, user: Dict[str, Any]) -> Dict[str, Any]:
        """User payload enriched with live plan maths, password and token stripped."""
        out = {k: v for k, v in user.items() if k != "password_hash"}
        ig = dict(out.get("instagram", {}))
        ig.pop("access_token", None)
        ig.pop("page_access_token", None)
        out["instagram"] = ig
        out["plan_state"] = self.plan_state(user)
        out["usage"] = self.usage(user)
        out["revenue"] = sum(p["amount"] for p in user.get("payments", []) if p.get("status") == "paid")
        return out

    def list_public(self, search: str = "", plan: str = "all",
                    status: str = "all") -> List[Dict[str, Any]]:
        rows = [self.public(u) for u in self.all()]
        if search:
            q = search.lower().strip()
            rows = [r for r in rows if q in r["name"].lower() or q in r["email"].lower()
                    or q in r.get("business", "").lower() or q in r.get("ig_handle", "").lower()]
        if plan != "all":
            rows = [r for r in rows
                    if r["plan_state"]["plan_id"] == plan or r["plan_state"]["state"] == plan]
        if status != "all":
            rows = [r for r in rows if r["status"] == status]
        rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return rows

    # ----------------------------------------------------------- plan math
    def plan_state(self, user: Dict[str, Any]) -> Dict[str, Any]:
        plan_id = user.get("plan", "free")
        plan = self.plans.get_plan(plan_id) or self.plans.free_plan() or {}
        state = user.get("subscription_state", FREE)
        price = plan.get("price_monthly", 0)

        # a trial that has run out flips to expired on read
        trial_days = plan.get("trial_days", 0)
        start = _parse(user.get("trial_start")) or datetime.now()
        expiry = start + timedelta(days=trial_days) if trial_days else None
        days_left = 0
        if state == TRIALING and expiry:
            days_left = max(0, (expiry - datetime.now()).days)
            if datetime.now() > expiry:
                state = EXPIRED

        labels = {
            ACTIVE: f"{plan.get('name', 'Plan')} — ₹{price}/mo",
            TRIALING: f"{plan.get('name', 'Plan')} trial — {days_left} days left",
            EXPIRED: "Trial expired",
            FREE: plan.get("name", "Free"),
        }
        badges = {ACTIVE: plan.get("name", "PLAN").upper(), TRIALING: "TRIAL",
                  EXPIRED: "EXPIRED", FREE: "FREE"}

        limits = dict(plan.get("limits", {}))
        features = dict(plan.get("features", {}))
        if state == EXPIRED:  # nothing runs on an expired trial
            limits = {k: 0 for k in limits}
            features = {k: False for k in features}

        return {
            "plan_id": plan_id,
            "plan_name": plan.get("name", "Free"),
            "state": state,
            "label": labels.get(state, plan.get("name", "")),
            "badge": badges.get(state, "FREE"),
            "is_paid": state == ACTIVE and price > 0,
            "is_pro": state == ACTIVE and price > 0,   # legacy key
            "price_monthly": price,
            "price_yearly": plan.get("price_yearly", 0),
            "days_left": days_left if state == TRIALING else None,
            "expired": state == EXPIRED,
            "trial_expiry": expiry.strftime(ISO) if expiry else None,
            "renews_on": user.get("renews_on"),
            "limits": limits,
            "features": features,
            "max_active_automations": limits.get("automations", 0),
        }

    def usage(self, user: Dict[str, Any]) -> Dict[str, Any]:
        """Usage against the live plan limits, ready to draw as meters."""
        limits = self.plan_state(user)["limits"]
        stats = user.get("stats", {})
        used = {
            "automations": stats.get("active_automations", 0),
            "contacts": stats.get("contacts", 0),
            "dms_per_month": stats.get("dms_this_month", 0),
            "ig_accounts": 1 if user.get("instagram", {}).get("connected") else 0,
            "team_seats": 1,
        }
        out = {}
        for key, cap in limits.items():
            count = used.get(key, 0)
            unlimited = cap == UNLIMITED
            out[key] = {
                "used": count,
                "limit": cap,
                "unlimited": unlimited,
                "percent": 0 if unlimited or not cap else min(100, round(count / cap * 100)),
                "over": (not unlimited) and cap >= 0 and count > cap,
            }
        return out

    def can_use(self, user: Dict[str, Any], feature: str) -> Tuple[bool, str]:
        state = self.plan_state(user)
        if state["state"] == EXPIRED:
            return False, "Your trial has ended. Upgrade to switch this back on."
        if state["features"].get(feature):
            return True, "Included in your plan"
        upsell = next((p for p in self.plans.all_plans(public_only=True)
                       if p.get("features", {}).get(feature)), None)
        if upsell:
            return False, f"{self._feature_label(feature)} is on the {upsell['name']} plan (₹{upsell['price_monthly']}/mo)."
        return False, "That feature is not available on your plan."

    def _feature_label(self, key: str) -> str:
        from core.plans_manager import FEATURE_KEYS
        return dict(FEATURE_KEYS).get(key, key.replace("_", " ").title())

    def can_activate_automation(self, user: Dict[str, Any], current_active: int) -> Tuple[bool, str]:
        state = self.plan_state(user)
        cap = state["limits"].get("automations", 0)
        if state["state"] == EXPIRED:
            return False, "Your trial has ended — upgrade to keep automations running."
        if cap == UNLIMITED:
            return True, "Unlimited on your plan"
        if current_active >= cap:
            nxt = self._next_plan_up(state["plan_id"])
            extra = f" {nxt['name']} gives you {'unlimited' if nxt['limits']['automations'] == UNLIMITED else nxt['limits']['automations']} for ₹{nxt['price_monthly']}/mo." if nxt else ""
            return False, f"The {state['plan_name']} plan allows {cap} active automation{'s' if cap != 1 else ''}.{extra}"
        return True, "Allowed"

    def _next_plan_up(self, plan_id: str) -> Optional[Dict[str, Any]]:
        ladder = self.plans.all_plans(public_only=True)
        current = self.plans.get_plan(plan_id)
        if not current:
            return ladder[0] if ladder else None
        for plan in ladder:
            if plan.get("order", 0) > current.get("order", 0):
                return plan
        return None

    # --------------------------------------------------------------- write
    def create(self, name: str, email: str, password: str,
               ig_handle: str = "", business: str = "") -> Tuple[bool, Any]:
        if not name or not email or not password:
            return False, "Name, email and password are all required."
        if len(password) < 6:
            return False, "Password must be at least 6 characters."
        if self.get_by_email(email):
            return False, "An account with this email already exists."
        user = self._blank_user(name, email, password, ig_handle, business)
        self._state["users"].append(user)
        self._save()
        return True, user

    def authenticate(self, email: str, password: str) -> Tuple[bool, Any]:
        user = self.get_by_email(email)
        if not user:
            return False, "No account found for this email."
        if user.get("status") == "suspended":
            return False, "This account is suspended. Contact support."
        if not verify_password(password, user.get("password_hash", "")):
            return False, "Incorrect password."
        user["stats"]["last_active"] = _now()
        self._save()
        return True, user

    def update(self, user_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        user = self.get(user_id)
        if not user:
            return None
        for key in ("name", "email", "ig_handle", "business", "phone", "notes", "status"):
            if key in patch and patch[key] is not None:
                user[key] = patch[key]
        if patch.get("password"):
            user["password_hash"] = hash_password(patch["password"])
        self._save()
        return user

    def set_plan(self, user_id: str, plan_id: str, record_payment: bool = True,
                 amount: Optional[int] = None, coupon: Optional[str] = None) -> Optional[Dict[str, Any]]:
        user = self.get(user_id)
        if not user:
            return None
        plan = self.plans.get_plan(plan_id)
        if not plan:
            return None

        user["plan"] = plan_id
        price = plan.get("price_monthly", 0)

        if price == 0:
            user["subscription_state"] = FREE
            user["pro_since"] = None
            user["renews_on"] = None
        else:
            user["subscription_state"] = ACTIVE
            user["pro_since"] = user.get("pro_since") or _now()
            user["renews_on"] = (datetime.now() + timedelta(days=30)).strftime(ISO)
            if record_payment:
                user.setdefault("payments", []).append({
                    "id": f"pay_{uuid.uuid4().hex[:10]}",
                    "date": _now(),
                    "amount": price if amount is None else amount,
                    "plan": plan_id,
                    "method": "manual",
                    "coupon": coupon,
                    "status": "paid",
                })
        if coupon:
            user["coupon"] = coupon
        self._save()
        return user

    def start_trial(self, user_id: str, plan_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        user = self.get(user_id)
        if not user:
            return None
        plan = self.plans.get_plan(plan_id) if plan_id else self.plans.default_paid_plan()
        user["plan"] = plan["id"]
        user["subscription_state"] = TRIALING
        user["trial_start"] = _now()
        user["pro_since"] = None
        user["renews_on"] = None
        self._save()
        return user

    def extend_trial(self, user_id: str, days: int = 7) -> Optional[Dict[str, Any]]:
        user = self.get(user_id)
        if not user:
            return None
        plan = self.plans.get_plan(user.get("plan", "")) or self.plans.default_paid_plan()
        trial_days = plan.get("trial_days", 15) or 15
        start = _parse(user.get("trial_start")) or datetime.now()
        expiry = start + timedelta(days=trial_days)
        base = max(expiry, datetime.now())
        user["trial_start"] = (base + timedelta(days=days) - timedelta(days=trial_days)).strftime(ISO)
        user["subscription_state"] = TRIALING
        self._save()
        return user

    def toggle_status(self, user_id: str) -> Optional[Dict[str, Any]]:
        user = self.get(user_id)
        if not user:
            return None
        user["status"] = "suspended" if user["status"] == "active" else "active"
        self._save()
        return user

    def delete(self, user_id: str) -> bool:
        before = len(self.all())
        self._state["users"] = [u for u in self.all() if u["id"] != user_id]
        self._save()
        return len(self.all()) < before

    # ----------------------------------------------------------- instagram
    def set_instagram(self, user_id: str, connection: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        user = self.get(user_id)
        if not user:
            return None
        user["instagram"] = connection
        if connection.get("username"):
            user["ig_handle"] = connection["username"]
        self._save()
        return user

    def disconnect_instagram(self, user_id: str) -> Optional[Dict[str, Any]]:
        user = self.get(user_id)
        if not user:
            return None
        user["instagram"] = {"connected": False, "disconnected_at": _now()}
        self._save()
        return user

    # --------------------------------------------------------- aggregation
    def metrics(self) -> Dict[str, Any]:
        users = self.all()
        states = [(u, self.plan_state(u)) for u in users]
        paying = [(u, s) for u, s in states if s["is_paid"]]
        trialing = [u for u, s in states if s["state"] == TRIALING]
        expired = [u for u, s in states if s["state"] == EXPIRED]
        free = [u for u, s in states if s["state"] == FREE]
        suspended = [u for u in users if u.get("status") == "suspended"]

        total_revenue = sum(p["amount"] for u in users for p in u.get("payments", [])
                            if p.get("status") == "paid")
        mrr = sum(s["price_monthly"] for _, s in paying)
        convertible = len(paying) + len(trialing) + len(expired)
        conversion = round(len(paying) / convertible * 100, 1) if convertible else 0.0

        now = datetime.now()
        active_7d = sum(1 for u in users
                        if (lambda d: d and (now - d).days <= 7)(_parse(u.get("stats", {}).get("last_active"))))
        connected = sum(1 for u in users if u.get("instagram", {}).get("connected"))

        by_plan = {}
        for plan in self.plans.all_plans():
            count = sum(1 for _, s in states if s["plan_id"] == plan["id"])
            by_plan[plan["id"]] = {"name": plan["name"], "count": count,
                                   "price": plan["price_monthly"]}

        return {
            "total_users": len(users),
            "paying_users": len(paying),
            "pro_users": len(paying),          # legacy key
            "trial_users": len(trialing),
            "expired_users": len(expired),
            "free_users": len(free),
            "suspended_users": len(suspended),
            "ig_connected": connected,
            "active_7d": active_7d,
            "mrr": mrr,
            "arr": mrr * 12,
            "total_revenue": total_revenue,
            "arpu": round(total_revenue / len(users), 0) if users else 0,
            "conversion_rate": conversion,
            "total_contacts": sum(u.get("stats", {}).get("contacts", 0) for u in users),
            "total_dms": sum(u.get("stats", {}).get("dms_sent", 0) for u in users),
            "total_dms_failed": sum(u.get("stats", {}).get("dms_failed", 0) for u in users),
            "total_automations": sum(u.get("stats", {}).get("automations", 0) for u in users),
            "by_plan": by_plan,
            "price_monthly": self.plans.default_paid_plan().get("price_monthly", 0),
        }

    def revenue_series(self, months: int = 6) -> List[Dict[str, Any]]:
        """Monthly paid revenue + signup counts, oldest first."""
        now = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        buckets: List[Dict[str, Any]] = []
        for offset in range(months - 1, -1, -1):
            year, month = now.year, now.month - offset
            while month <= 0:
                month += 12
                year -= 1
            start = datetime(year, month, 1)
            end = datetime(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
            revenue = sum(p.get("amount", 0)
                          for u in self.all() for p in u.get("payments", [])
                          if p.get("status") == "paid"
                          and (lambda d: d and start <= d < end)(_parse(p.get("date"))))
            signups = sum(1 for u in self.all()
                          if (lambda d: d and start <= d < end)(_parse(u.get("created_at"))))
            buckets.append({"label": start.strftime("%b"), "month": start.strftime("%Y-%m"),
                            "revenue": revenue, "signups": signups})
        return buckets

    def recent_payments(self, limit: int = 12) -> List[Dict[str, Any]]:
        rows = []
        for u in self.all():
            for p in u.get("payments", []):
                rows.append({**p, "user_id": u["id"], "user_name": u["name"], "email": u["email"]})
        rows.sort(key=lambda r: r.get("date", ""), reverse=True)
        return rows[:limit]
