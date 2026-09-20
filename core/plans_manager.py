"""
ConverFlow — Plans, Pricing & Offers
====================================
The pricing catalogue is data, not code. Everything the admin edits in
Admin > Plans & Pricing lands in data/plans.json and is read live by the
public website, the signup flow and the limit checks.

Offers (data/offers.json) are coupon codes that discount a plan, extend a
trial or give free months.
"""

import os
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
PLANS_FILE = os.path.join(DATA_DIR, "plans.json")
OFFERS_FILE = os.path.join(DATA_DIR, "offers.json")

ISO = "%Y-%m-%dT%H:%M:%S"
UNLIMITED = -1  # a limit of -1 means "no cap"


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


# Every capability a plan can switch on. Order here is the order shown in the UI.
FEATURE_KEYS = [
    ("comment_to_dm", "Comment-to-DM automations"),
    ("dm_keyword", "DM keyword auto-replies"),
    ("wildcard_trigger", "Wildcard (any comment) trigger"),
    ("story_mention", "Story mention trigger"),
    ("broadcast", "Broadcast / cold DM engine"),
    ("ai_assist", "AI flow & hook generator"),
    ("analytics", "Campaign analytics"),
    ("csv_export", "CSV export"),
    ("remove_branding", "Remove ConverFlow branding"),
    ("priority_support", "Priority WhatsApp support"),
    ("white_label", "White-label for clients"),
]

LIMIT_KEYS = [
    ("automations", "Active automations"),
    ("contacts", "Contacts stored"),
    ("dms_per_month", "DMs per month"),
    ("ig_accounts", "Instagram accounts"),
    ("team_seats", "Team seats"),
]


class PlansManager:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.plans = self._load(PLANS_FILE, self._seed_plans, "plans")
        self.offers = self._load(OFFERS_FILE, self._seed_offers, "offers")

    # ------------------------------------------------------------------ io
    def _load(self, path: str, seeder, key: str) -> List[Dict[str, Any]]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and key in data:
                    return data[key]
                if isinstance(data, list):
                    return data
            except Exception:
                pass
        data = seeder()
        self._write(path, key, data)
        return data

    def _write(self, path: str, key: str, data: List[Dict[str, Any]]) -> None:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({key: data, "updated_at": _now()}, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)

    def _save_plans(self):
        self._write(PLANS_FILE, "plans", self.plans)

    def _save_offers(self):
        self._write(OFFERS_FILE, "offers", self.offers)

    # ---------------------------------------------------------------- seed
    def _seed_plans(self) -> List[Dict[str, Any]]:
        """
        Benchmarked Sept 2026: Manychat Essential ~Rs.1,245/mo (250 contacts),
        Manychat Pro ~Rs.3,735/mo (2,500 contacts); Indian rivals sit at
        Rs.99-Rs.799 flat. This ladder undercuts Manychat heavily while leaving
        real headroom above the Rs.399 entry point.
        """
        def plan(pid, name, tagline, monthly, yearly, order, limits, features,
                 highlight=False, badge="", public=True, trial_days=0):
            return {
                "id": pid,
                "name": name,
                "tagline": tagline,
                "price_monthly": monthly,
                "price_yearly": yearly,
                "currency": "INR",
                "order": order,
                "is_public": public,
                "highlight": highlight,
                "badge": badge,
                "trial_days": trial_days,
                "limits": limits,
                "features": features,
                "created_at": _now(),
            }

        def feats(**kw):
            base = {k: False for k, _ in FEATURE_KEYS}
            base.update(kw)
            return base

        return [
            plan("free", "Free", "Try one automation, forever free", 0, 0, 1,
                 {"automations": 1, "contacts": 100, "dms_per_month": 200,
                  "ig_accounts": 1, "team_seats": 1},
                 feats(comment_to_dm=True, dm_keyword=True, csv_export=True),
                 badge="Free forever"),

            plan("starter", "Starter", "For creators posting every week", 399, 3990, 2,
                 {"automations": 3, "contacts": 1000, "dms_per_month": 2000,
                  "ig_accounts": 1, "team_seats": 1},
                 feats(comment_to_dm=True, dm_keyword=True, wildcard_trigger=True,
                       csv_export=True, remove_branding=True)),

            plan("growth", "Growth", "For brands selling every single day", 799, 7990, 3,
                 {"automations": UNLIMITED, "contacts": 5000, "dms_per_month": 15000,
                  "ig_accounts": 1, "team_seats": 2},
                 feats(comment_to_dm=True, dm_keyword=True, wildcard_trigger=True,
                       story_mention=True, broadcast=True, ai_assist=True,
                       analytics=True, csv_export=True, remove_branding=True,
                       priority_support=True),
                 highlight=True, badge="Most popular", trial_days=15),

            plan("agency", "Agency", "Run several brands from one login", 1999, 19990, 4,
                 {"automations": UNLIMITED, "contacts": 25000, "dms_per_month": UNLIMITED,
                  "ig_accounts": 3, "team_seats": 5},
                 feats(**{k: True for k, _ in FEATURE_KEYS}),
                 badge="Best for agencies"),
        ]

    def _seed_offers(self) -> List[Dict[str, Any]]:
        now = datetime.now()
        return [
            {
                "id": f"off_{uuid.uuid4().hex[:8]}",
                "code": "LAUNCH50",
                "title": "Launch offer — 50% off first month",
                "description": "Half price on the first month of any paid plan.",
                "type": "percent",
                "value": 50,
                "applies_to": ["starter", "growth", "agency"],
                "duration": "first_month",
                "starts_at": (now - timedelta(days=6)).strftime(ISO),
                "expires_at": (now + timedelta(days=24)).strftime(ISO),
                "max_redemptions": 100,
                "redeemed": 14,
                "active": True,
                "created_at": (now - timedelta(days=6)).strftime(ISO),
            },
            {
                "id": f"off_{uuid.uuid4().hex[:8]}",
                "code": "DIWALI299",
                "title": "Festive flat ₹299 off",
                "description": "Flat discount on Growth and Agency during the festive season.",
                "type": "flat",
                "value": 299,
                "applies_to": ["growth", "agency"],
                "duration": "first_month",
                "starts_at": now.strftime(ISO),
                "expires_at": (now + timedelta(days=40)).strftime(ISO),
                "max_redemptions": 250,
                "redeemed": 0,
                "active": True,
                "created_at": now.strftime(ISO),
            },
            {
                "id": f"off_{uuid.uuid4().hex[:8]}",
                "code": "EXTEND7",
                "title": "7 extra trial days",
                "description": "Gives a trial user one more week before they have to decide.",
                "type": "trial_extend",
                "value": 7,
                "applies_to": ["growth"],
                "duration": "one_time",
                "starts_at": (now - timedelta(days=30)).strftime(ISO),
                "expires_at": (now + timedelta(days=120)).strftime(ISO),
                "max_redemptions": 0,
                "redeemed": 6,
                "active": True,
                "created_at": (now - timedelta(days=30)).strftime(ISO),
            },
        ]

    # --------------------------------------------------------------- plans
    def all_plans(self, public_only: bool = False) -> List[Dict[str, Any]]:
        rows = [p for p in self.plans if p.get("is_public", True)] if public_only else list(self.plans)
        return sorted(rows, key=lambda p: p.get("order", 99))

    def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        return next((p for p in self.plans if p["id"] == plan_id), None)

    def default_paid_plan(self) -> Dict[str, Any]:
        """The plan a trial runs on, and the one the upgrade button points at."""
        highlighted = next((p for p in self.all_plans() if p.get("highlight")), None)
        if highlighted:
            return highlighted
        paid = [p for p in self.all_plans() if p.get("price_monthly", 0) > 0]
        return paid[0] if paid else self.all_plans()[0]

    def free_plan(self) -> Optional[Dict[str, Any]]:
        return next((p for p in self.all_plans() if p.get("price_monthly", 0) == 0), None)

    def limits_for(self, plan_id: str) -> Dict[str, Any]:
        plan = self.get_plan(plan_id) or self.free_plan() or {}
        return plan.get("limits", {})

    def features_for(self, plan_id: str) -> Dict[str, bool]:
        plan = self.get_plan(plan_id) or self.free_plan() or {}
        return plan.get("features", {})

    def save_plan(self, payload: Dict[str, Any]) -> Tuple[bool, Any]:
        pid = (payload.get("id") or "").strip().lower().replace(" ", "-")
        if not pid:
            pid = (payload.get("name", "plan")).strip().lower().replace(" ", "-")
        existing = self.get_plan(pid)

        if existing:
            for key in ("name", "tagline", "price_monthly", "price_yearly", "order",
                        "is_public", "highlight", "badge", "trial_days", "currency"):
                if key in payload and payload[key] is not None:
                    existing[key] = payload[key]
            if isinstance(payload.get("limits"), dict):
                existing.setdefault("limits", {}).update(payload["limits"])
            if isinstance(payload.get("features"), dict):
                existing.setdefault("features", {}).update(payload["features"])
            plan = existing
        else:
            if not payload.get("name"):
                return False, "A plan needs a name."
            plan = {
                "id": pid,
                "name": payload["name"],
                "tagline": payload.get("tagline", ""),
                "price_monthly": int(payload.get("price_monthly", 0)),
                "price_yearly": int(payload.get("price_yearly", 0)),
                "currency": payload.get("currency", "INR"),
                "order": int(payload.get("order", len(self.plans) + 1)),
                "is_public": bool(payload.get("is_public", True)),
                "highlight": bool(payload.get("highlight", False)),
                "badge": payload.get("badge", ""),
                "trial_days": int(payload.get("trial_days", 0)),
                "limits": payload.get("limits", {k: 0 for k, _ in LIMIT_KEYS}),
                "features": payload.get("features", {k: False for k, _ in FEATURE_KEYS}),
                "created_at": _now(),
            }
            self.plans.append(plan)

        # only one plan can wear the highlight
        if plan.get("highlight"):
            for other in self.plans:
                if other["id"] != plan["id"]:
                    other["highlight"] = False

        self._save_plans()
        return True, plan

    def delete_plan(self, plan_id: str) -> Tuple[bool, str]:
        plan = self.get_plan(plan_id)
        if not plan:
            return False, "Plan not found."
        if len([p for p in self.plans if p.get("price_monthly", 0) == 0]) <= 1 and plan.get("price_monthly", 0) == 0:
            return False, "Keep at least one free plan — new signups land on it."
        self.plans = [p for p in self.plans if p["id"] != plan_id]
        self._save_plans()
        return True, "Plan deleted."

    def reorder(self, ordered_ids: List[str]) -> None:
        for index, pid in enumerate(ordered_ids, start=1):
            plan = self.get_plan(pid)
            if plan:
                plan["order"] = index
        self._save_plans()

    # -------------------------------------------------------------- offers
    def all_offers(self) -> List[Dict[str, Any]]:
        rows = sorted(self.offers, key=lambda o: o.get("created_at", ""), reverse=True)
        for offer in rows:
            offer["status"] = self.offer_status(offer)
        return rows

    def offer_status(self, offer: Dict[str, Any]) -> str:
        if not offer.get("active"):
            return "paused"
        now = datetime.now()
        starts = _parse(offer.get("starts_at"))
        expires = _parse(offer.get("expires_at"))
        if starts and now < starts:
            return "scheduled"
        if expires and now > expires:
            return "expired"
        cap = offer.get("max_redemptions", 0)
        if cap and offer.get("redeemed", 0) >= cap:
            return "used up"
        return "live"

    def get_offer(self, offer_id: str) -> Optional[Dict[str, Any]]:
        return next((o for o in self.offers if o["id"] == offer_id), None)

    def get_offer_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        code = (code or "").strip().upper()
        return next((o for o in self.offers if o.get("code", "").upper() == code), None)

    def save_offer(self, payload: Dict[str, Any]) -> Tuple[bool, Any]:
        code = (payload.get("code") or "").strip().upper()
        if not code:
            return False, "A coupon needs a code."
        offer = self.get_offer(payload.get("id", "")) if payload.get("id") else None
        clash = self.get_offer_by_code(code)
        if clash and (not offer or clash["id"] != offer["id"]):
            return False, f"The code {code} is already in use."

        applies = payload.get("applies_to") or []
        if isinstance(applies, str):
            applies = [a.strip() for a in applies.split(",") if a.strip()]

        data = {
            "code": code,
            "title": payload.get("title", "") or code,
            "description": payload.get("description", ""),
            "type": payload.get("type", "percent"),
            "value": int(payload.get("value", 0) or 0),
            "applies_to": applies,
            "duration": payload.get("duration", "first_month"),
            "starts_at": payload.get("starts_at") or _now(),
            "expires_at": payload.get("expires_at") or (datetime.now() + timedelta(days=30)).strftime(ISO),
            "max_redemptions": int(payload.get("max_redemptions", 0) or 0),
            "active": bool(payload.get("active", True)),
        }

        if offer:
            offer.update(data)
        else:
            offer = {"id": f"off_{uuid.uuid4().hex[:8]}", "redeemed": 0,
                     "created_at": _now(), **data}
            self.offers.append(offer)
        self._save_offers()
        return True, offer

    def delete_offer(self, offer_id: str) -> bool:
        before = len(self.offers)
        self.offers = [o for o in self.offers if o["id"] != offer_id]
        self._save_offers()
        return len(self.offers) < before

    def toggle_offer(self, offer_id: str) -> Optional[Dict[str, Any]]:
        offer = self.get_offer(offer_id)
        if not offer:
            return None
        offer["active"] = not offer.get("active", True)
        self._save_offers()
        return offer

    def apply_offer(self, code: str, plan_id: str) -> Dict[str, Any]:
        """Price a plan with a coupon applied. Does NOT consume a redemption."""
        plan = self.get_plan(plan_id)
        if not plan:
            return {"valid": False, "error": "Unknown plan."}
        price = plan.get("price_monthly", 0)

        offer = self.get_offer_by_code(code)
        if not offer:
            return {"valid": False, "error": "That coupon code does not exist."}
        status = self.offer_status(offer)
        if status != "live":
            return {"valid": False, "error": f"This coupon is {status}."}
        if offer.get("applies_to") and plan_id not in offer["applies_to"]:
            return {"valid": False, "error": f"{offer['code']} does not apply to the {plan['name']} plan."}

        discount = 0
        trial_days = 0
        if offer["type"] == "percent":
            discount = round(price * offer["value"] / 100)
        elif offer["type"] == "flat":
            discount = min(price, offer["value"])
        elif offer["type"] == "free_months":
            discount = price
        elif offer["type"] == "trial_extend":
            trial_days = offer["value"]

        return {
            "valid": True,
            "offer": offer,
            "plan": plan["name"],
            "original_price": price,
            "discount": discount,
            "final_price": max(0, price - discount),
            "trial_days": trial_days,
            "note": offer.get("title", ""),
        }

    def redeem(self, code: str) -> bool:
        offer = self.get_offer_by_code(code)
        if not offer:
            return False
        offer["redeemed"] = offer.get("redeemed", 0) + 1
        self._save_offers()
        return True

    # ----------------------------------------------------------- reference
    def schema(self) -> Dict[str, Any]:
        return {
            "feature_keys": [{"key": k, "label": l} for k, l in FEATURE_KEYS],
            "limit_keys": [{"key": k, "label": l} for k, l in LIMIT_KEYS],
            "offer_types": [
                {"key": "percent", "label": "Percent off"},
                {"key": "flat", "label": "Flat ₹ off"},
                {"key": "free_months", "label": "Free month"},
                {"key": "trial_extend", "label": "Extra trial days"},
            ],
            "unlimited": UNLIMITED,
        }
