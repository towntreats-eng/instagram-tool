"""
ConverFlow — Razorpay
=====================
Checkout without a server SDK: Razorpay's Orders API is plain REST over basic
auth, and signature verification is one HMAC. That keeps the dependency list
short and the failure modes visible.

Flow:
  1. dashboard  -> POST /api/billing/checkout   (we create an order)
  2. browser    -> Razorpay Checkout opens with that order_id
  3. browser    -> POST /api/billing/verify     (we check the signature)
  4. Razorpay   -> POST /api/razorpay/webhook   (belt and braces, server side)

Nothing is granted on the browser's word alone. The plan only changes after a
signature we computed ourselves matches, or after a signed webhook says so.
"""

import os
import json
import hmac
import base64
import hashlib
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

API = "https://api.razorpay.com/v1"
ISO = "%Y-%m-%dT%H:%M:%S"


def _now() -> str:
    return datetime.now().strftime(ISO)


class RazorpayClient:
    def __init__(self, settings):
        self.settings = settings  # PlatformSettings

    # ------------------------------------------------------------- config
    @property
    def cfg(self) -> Dict[str, Any]:
        return self.settings.section("billing")

    @property
    def key_id(self) -> str:
        return (self.cfg.get("razorpay_key_id") or "").strip()

    @property
    def key_secret(self) -> str:
        return (self.cfg.get("razorpay_key_secret") or "").strip()

    def ready(self) -> bool:
        return bool(self.key_id and self.key_secret and self.key_id.startswith("rzp_"))

    def mode(self) -> str:
        if not self.ready():
            return "not_configured"
        return "live" if self.key_id.startswith("rzp_live") else "test"

    # -------------------------------------------------------------- http
    def _call(self, method: str, path: str, payload: Optional[Dict] = None) -> Tuple[bool, Any]:
        token = base64.b64encode(f"{self.key_id}:{self.key_secret}".encode()).decode()
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(
            API + path, data=data, method=method,
            headers={"Authorization": "Basic " + token,
                     "Content-Type": "application/json",
                     "User-Agent": "ConverFlow/4.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as res:
                return True, json.loads(res.read().decode())
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read().decode())
                return False, body.get("error", {}).get("description", f"HTTP {e.code}")
            except Exception:
                return False, f"Razorpay returned HTTP {e.code}"
        except Exception as e:
            return False, str(e)

    # ------------------------------------------------------------ orders
    def create_order(self, amount_inr: int, receipt: str,
                     notes: Optional[Dict[str, str]] = None) -> Tuple[bool, Any]:
        """Amount is in rupees here; Razorpay wants paise."""
        if not self.ready():
            return False, ("Razorpay is not configured yet. Add the Key ID and Secret "
                           "in Admin → Platform settings → Billing.")
        if amount_inr <= 0:
            return False, "That plan is free — there is nothing to pay."

        ok, order = self._call("POST", "/orders", {
            "amount": int(round(amount_inr * 100)),
            "currency": self.cfg.get("currency", "INR"),
            "receipt": receipt[:40],
            "notes": notes or {},
        })
        if not ok:
            return False, order
        return True, {
            "order_id": order["id"],
            "amount": order["amount"],
            "amount_inr": amount_inr,
            "currency": order["currency"],
            "key_id": self.key_id,          # publishable, safe for the browser
            "mode": self.mode(),
        }

    # ------------------------------------------------------- verification
    def verify_payment(self, order_id: str, payment_id: str, signature: str) -> Tuple[bool, str]:
        """HMAC-SHA256 of "order_id|payment_id" keyed with the secret."""
        if not self.ready():
            return False, "Razorpay is not configured."
        expected = hmac.new(self.key_secret.encode(),
                            f"{order_id}|{payment_id}".encode(),
                            hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, (signature or "").strip()):
            return False, "Payment signature did not match — nothing has been charged to your plan."
        return True, "Signature verified"

    def verify_webhook(self, raw_body: bytes, signature: str) -> bool:
        secret = (self.cfg.get("razorpay_webhook_secret") or self.key_secret or "").encode()
        if not secret:
            return False
        expected = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, (signature or "").strip())

    def fetch_payment(self, payment_id: str) -> Tuple[bool, Any]:
        return self._call("GET", f"/payments/{payment_id}")

    # --------------------------------------------------------------- test
    def test_keys(self) -> Dict[str, Any]:
        """Admin 'Test keys' — creates a ₹1 order and throws it away."""
        if not self.ready():
            return {"success": False,
                    "error": "Add a Key ID starting with rzp_ and its Secret first."}
        ok, result = self._call("POST", "/orders", {
            "amount": 100, "currency": "INR", "receipt": "cf_keycheck",
            "notes": {"purpose": "ConverFlow key check"},
        })
        if ok:
            return {"success": True, "mode": self.mode(),
                    "message": f"Keys work — you're in {self.mode()} mode."}
        return {"success": False, "error": str(result)}
