import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BILLING_FILE = os.path.join(BASE_DIR, "data", "billing.json")

class BillingManager:
    """
    Manages 15-Day Free Trial and ₹299/month Pro Plan subscription.
    Free Trial Rule: Exactly 1 active reel/post automation at a time.
    Pro Plan: Unlimited automations, all advanced triggers unlocked.
    """

    TRIAL_DAYS = 15
    PRO_PRICE_INR = 299

    def __init__(self, file_path: str = BILLING_FILE):
        self.file_path = file_path
        self._ensure_dir()
        self._state = self._load()

    def _ensure_dir(self):
        folder = os.path.dirname(self.file_path)
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)

    def _load(self) -> Dict[str, Any]:
        if not os.path.exists(self.file_path):
            initial = {
                "plan": "trial", # trial, pro
                "is_pro": False,
                "trial_start_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "pro_subscribed_date": None,
                "max_active_reels_free": 1
            }
            self._save_raw(initial)
            return initial

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {
                "plan": "trial",
                "is_pro": False,
                "trial_start_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "pro_subscribed_date": None,
                "max_active_reels_free": 1
            }

    def _save_raw(self, data: Dict[str, Any]):
        self._ensure_dir()
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _save(self):
        self._save_raw(self._state)

    def get_status(self, active_count: int = 0) -> Dict[str, Any]:
        start_dt = datetime.strptime(self._state.get("trial_start_date", datetime.now().strftime("%Y-%m-%d %H:%M:%S")), "%Y-%m-%d %H:%M:%S")
        expiry_dt = start_dt + timedelta(days=self.TRIAL_DAYS)
        now = datetime.now()

        days_left = max(0, (expiry_dt - now).days)
        hours_left = max(0, int((expiry_dt - now).total_seconds() // 3600))
        is_trial_expired = now > expiry_dt

        is_pro = self._state.get("is_pro", False)
        plan_name = "Pro Plan (₹299/mo)" if is_pro else ("Free Trial" if not is_trial_expired else "Trial Expired")

        max_reels = 999 if is_pro else self._state.get("max_active_reels_free", 1)

        return {
            "plan": "pro" if is_pro else "trial",
            "plan_name": plan_name,
            "is_pro": is_pro,
            "days_left": days_left,
            "hours_left": hours_left,
            "is_trial_expired": is_trial_expired,
            "trial_start": str(start_dt),
            "trial_expiry": str(expiry_dt),
            "price_monthly": self.PRO_PRICE_INR,
            "active_reels_count": active_count,
            "max_active_reels": max_reels,
            "can_activate_more": is_pro or (active_count < max_reels)
        }

    def can_activate_reel(self, current_active_count: int) -> Tuple[bool, str]:
        """
        Validates if user is allowed to activate an automation reel.
        Free plan is strictly limited to 1 active reel.
        """
        if self._state.get("is_pro"):
            return True, "Pro active"

        max_free = self._state.get("max_active_reels_free", 1)
        if current_active_count >= max_free:
            return False, f"Free Trial allows only {max_free} active Reel automation at a time. Upgrade to Pro for ₹299/month for unlimited Reels!"

        # Check trial expiration
        status = self.get_status(current_active_count)
        if status.get("is_trial_expired"):
            return False, "Your 15-day Free Trial has expired. Upgrade to Pro for ₹299/month to keep automations running!"

        return True, "Allowed"

    def upgrade_to_pro(self) -> Dict[str, Any]:
        self._state["is_pro"] = True
        self._state["plan"] = "pro"
        self._state["pro_subscribed_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save()
        return self.get_status()

    def reset_to_trial(self) -> Dict[str, Any]:
        self._state["is_pro"] = False
        self._state["plan"] = "trial"
        self._state["trial_start_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._state["pro_subscribed_date"] = None
        self._save()
        return self.get_status()

    get_billing_status = get_status
