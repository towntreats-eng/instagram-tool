"""
Razorpay for DM Flow — plain REST, no SDK.

Why no SDK: one dependency fewer to break a deploy, and the three calls we
actually make (create an order, verify a signature, verify a webhook) are
short enough to read in full. Anyone auditing our payment path can do it
in this one file.

Money rule: the server never trusts the browser. The browser can tell us a
payment succeeded all it likes — a plan only changes after verify_payment()
recomputes the HMAC from our own secret. A merchant should never be able to
type themselves onto Agency from the console.
"""

import base64
import hashlib
import hmac
import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

API = "https://api.razorpay.com/v1"
TIMEOUT = 20


class RazorpayClient:
    def __init__(self, settings):
        self.settings = settings          # PlatformSettings

    # ------------------------------------------------------------- config
    @property
    def cfg(self) -> Dict[str, Any]:
        return self.settings.section("billing") or {}

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

    # ---------------------------------------------------------- transport
    def _auth_header(self) -> str:
        raw = f"{self.key_id}:{self.key_secret}".encode()
        return "Basic " + base64.b64encode(raw).decode()

    def _post(self, path: str, payload: Dict[str, Any]) -> Tuple[bool, Any]:
        req = urllib.request.Request(
            API + path,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": self._auth_header()},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return True, json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            try:
                body = json.loads(exc.read().decode())
                msg = body.get("error", {}).get("description") or str(exc)
            except Exception:
                msg = f"Razorpay returned HTTP {exc.code}"
            return False, msg
        except Exception as exc:
            return False, f"Could not reach Razorpay: {exc}"

    # ------------------------------------------------------------- orders
    def create_order(self, amount_inr: float, receipt: str,
                     notes: Optional[Dict[str, Any]] = None) -> Tuple[bool, Any]:
        """amount_inr is rupees. Razorpay counts in paise, so we convert once, here."""
        if not self.ready():
            return False, ("Online payment isn't switched on yet. Add your Razorpay "
                           "keys in Admin → Settings → Billing.")
        paise = int(round(float(amount_inr) * 100))
        if paise < 100:
            return False, "Razorpay needs at least ₹1."
        ok, out = self._post("/orders", {
            "amount": paise,
            "currency": self.cfg.get("currency", "INR"),
            "receipt": receipt[:40],
            "notes": notes or {},
        })
        return ok, out

    # -------------------------------------------------------- verification
    def verify_payment(self, order_id: str, payment_id: str,
                       signature: str) -> Tuple[bool, str]:
        """The only thing standing between a browser and a free plan upgrade."""
        if not self.ready():
            return False, "Payment gateway is not configured."
        if not (order_id and payment_id and signature):
            return False, "Payment response was incomplete — nothing has been charged."
        expected = hmac.new(self.key_secret.encode(),
                            f"{order_id}|{payment_id}".encode(),
                            hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, (signature or "").strip()):
            return False, ("Payment signature did not match — your plan has not been "
                           "changed. If money left your account, send us the payment "
                           "id and we'll sort it out the same day.")
        return True, "Verified"

    def verify_webhook(self, raw_body: bytes, signature: str) -> bool:
        secret = (self.cfg.get("razorpay_webhook_secret") or self.key_secret or "").strip()
        if not secret or not signature:
            return False
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature.strip())

    # ------------------------------------------------------------- health
    def test_keys(self) -> Tuple[bool, str]:
        """Creates a ₹1 order and throws it away. An unpaid order costs nothing."""
        if not self.ready():
            return False, "Add a key id and secret first."
        ok, out = self.create_order(1, "cf_keytest", {"purpose": "key test"})
        if not ok:
            return False, str(out)
        return True, f"Keys work — {self.mode()} mode (test order {out.get('id')})."
