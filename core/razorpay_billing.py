"""
ConverFlow — Razorpay Payment Gateway
======================================
Handles order creation, payment verification, subscription management,
and webhook processing for INR payments via Razorpay.
"""

import os
import json
import hmac
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("RazorpayBilling")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RZP_CONFIG_FILE = os.path.join(DATA_DIR, "razorpay_config.json")
PAYMENTS_FILE = os.path.join(DATA_DIR, "payments.json")

ISO = "%Y-%m-%dT%H:%M:%S"


class RazorpayBilling:
    """
    Razorpay integration for ConverFlow SaaS billing.
    Supports one-time orders and recurring subscriptions.
    """

    def __init__(self, config_file: str = RZP_CONFIG_FILE):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.config_file = config_file
        self.config = self._load_config()
        self.payments = self._load_payments()
        self._client = None

    # ------------------------------------------------------------------ config
    def _load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        default = {
            "key_id": "",
            "key_secret": "",
            "webhook_secret": "",
            "currency": "INR",
            "receipt_prefix": "converflow_",
            "enabled": False,
        }
        self._write_config(default)
        return default

    def _write_config(self, data: Dict[str, Any]):
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def save_config(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        self.config.update(updates)
        self._write_config(self.config)
        self._client = None  # force re-init
        return self.config

    def get_config_safe(self) -> Dict[str, Any]:
        """Return config with secret masked."""
        cfg = dict(self.config)
        secret = cfg.get("key_secret", "")
        if secret:
            cfg["key_secret"] = secret[:6] + "..." + secret[-4:] if len(secret) > 10 else "***"
        ws = cfg.get("webhook_secret", "")
        if ws:
            cfg["webhook_secret"] = ws[:6] + "..." + ws[-4:] if len(ws) > 10 else "***"
        return cfg

    # ------------------------------------------------------------------ client
    @property
    def client(self):
        if self._client is None:
            try:
                import razorpay
                self._client = razorpay.Client(
                    auth=(self.config.get("key_id", ""), self.config.get("key_secret", ""))
                )
            except ImportError:
                logger.error("razorpay package not installed")
                return None
        return self._client

    def is_ready(self) -> bool:
        return bool(self.config.get("key_id") and self.config.get("key_secret") and self.config.get("enabled"))

    # ------------------------------------------------------------------ payments store
    def _load_payments(self) -> list:
        if os.path.exists(PAYMENTS_FILE):
            try:
                with open(PAYMENTS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else data.get("payments", [])
            except Exception:
                pass
        return []

    def _save_payments(self):
        with open(PAYMENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.payments, f, indent=2, ensure_ascii=False)

    def record_payment(self, payment_data: Dict[str, Any]):
        payment_data["recorded_at"] = datetime.now().strftime(ISO)
        self.payments.append(payment_data)
        self._save_payments()

    def get_payments(self, user_id: Optional[str] = None) -> list:
        if user_id:
            return [p for p in self.payments if p.get("user_id") == user_id]
        return self.payments

    # ------------------------------------------------------------------ orders
    def create_order(self, amount_inr: int, user_id: str, plan_id: str,
                     notes: Optional[Dict] = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Create a Razorpay order. Amount is in INR (will be converted to paise).
        Returns (success, order_data_or_error).
        """
        if not self.is_ready():
            return False, {"error": "Razorpay not configured. Add key_id and key_secret in admin settings."}

        try:
            order_data = {
                "amount": amount_inr * 100,  # paise
                "currency": self.config.get("currency", "INR"),
                "receipt": f"{self.config.get('receipt_prefix', 'cf_')}{user_id}_{int(datetime.now().timestamp())}",
                "notes": {
                    "user_id": user_id,
                    "plan_id": plan_id,
                    **(notes or {}),
                },
            }
            order = self.client.order.create(data=order_data)
            logger.info(f"Razorpay order created: {order['id']} for user {user_id}")
            return True, order
        except Exception as e:
            logger.error(f"Razorpay order creation failed: {e}")
            return False, {"error": str(e)}

    # ------------------------------------------------------------------ verify
    def verify_payment(self, razorpay_order_id: str, razorpay_payment_id: str,
                       razorpay_signature: str) -> Tuple[bool, str]:
        """
        Verify payment signature using HMAC SHA256.
        Returns (is_valid, message).
        """
        if not self.is_ready():
            return False, "Razorpay not configured"

        try:
            self.client.utility.verify_payment_signature({
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            })
            return True, "Payment verified successfully"
        except Exception as e:
            logger.error(f"Payment verification failed: {e}")
            return False, f"Signature verification failed: {e}"

    # ------------------------------------------------------------------ webhook
    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        """Verify Razorpay webhook signature."""
        secret = self.config.get("webhook_secret", "")
        if not secret:
            return False
        expected = hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def process_webhook(self, event: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming Razorpay webhook events.
        Returns action dict with what happened.
        """
        result = {"event": event, "processed": False}

        if event == "payment.captured":
            payment = payload.get("payment", {}).get("entity", {})
            notes = payment.get("notes", {})
            result.update({
                "processed": True,
                "action": "upgrade",
                "user_id": notes.get("user_id"),
                "plan_id": notes.get("plan_id"),
                "amount": payment.get("amount", 0) / 100,
                "payment_id": payment.get("id"),
                "method": payment.get("method"),
            })

        elif event == "payment.failed":
            payment = payload.get("payment", {}).get("entity", {})
            notes = payment.get("notes", {})
            result.update({
                "processed": True,
                "action": "payment_failed",
                "user_id": notes.get("user_id"),
                "error": payment.get("error_description", "Payment failed"),
            })

        elif event == "subscription.cancelled":
            sub = payload.get("subscription", {}).get("entity", {})
            notes = sub.get("notes", {})
            result.update({
                "processed": True,
                "action": "downgrade",
                "user_id": notes.get("user_id"),
                "subscription_id": sub.get("id"),
            })

        return result

    # ------------------------------------------------------------------ subscription
    def create_subscription(self, razorpay_plan_id: str, user_id: str,
                            total_count: int = 12) -> Tuple[bool, Dict[str, Any]]:
        """
        Create a Razorpay subscription for recurring billing.
        razorpay_plan_id is the plan ID created in Razorpay dashboard.
        """
        if not self.is_ready():
            return False, {"error": "Razorpay not configured"}

        try:
            sub_data = {
                "plan_id": razorpay_plan_id,
                "total_count": total_count,
                "quantity": 1,
                "notes": {"user_id": user_id},
            }
            sub = self.client.subscription.create(data=sub_data)
            return True, sub
        except Exception as e:
            logger.error(f"Subscription creation failed: {e}")
            return False, {"error": str(e)}

    def cancel_subscription(self, subscription_id: str) -> Tuple[bool, str]:
        """Cancel a Razorpay subscription."""
        if not self.is_ready():
            return False, "Razorpay not configured"
        try:
            self.client.subscription.cancel(subscription_id)
            return True, "Subscription cancelled"
        except Exception as e:
            return False, str(e)

    # ------------------------------------------------------------------ revenue stats
    def revenue_stats(self) -> Dict[str, Any]:
        """Aggregate revenue stats for admin dashboard."""
        total = sum(p.get("amount", 0) for p in self.payments if p.get("status") == "captured")
        this_month = []
        now = datetime.now()
        for p in self.payments:
            try:
                dt = datetime.strptime(p.get("recorded_at", ""), ISO)
                if dt.year == now.year and dt.month == now.month:
                    this_month.append(p)
            except Exception:
                pass
        mrr = sum(p.get("amount", 0) for p in this_month if p.get("status") == "captured")
        return {
            "total_revenue": total,
            "mrr": mrr,
            "total_payments": len(self.payments),
            "this_month_payments": len(this_month),
            "currency": "INR",
        }
