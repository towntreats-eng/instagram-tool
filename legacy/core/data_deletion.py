"""
Meta's data deletion callback, implemented rather than advertised.

The deletion page already told Meta there was a callback here. There was not.
A reviewer who tests it - and they do test it - would have found a URL that
answers nothing, which is a rejection on a promise the product made itself.

How Meta's callback works:

  Meta POSTs form field `signed_request`, which is two base64url parts joined
  by a dot: `<signature>.<payload>`. The signature is HMAC-SHA256 of the
  *payload string as sent* (not the decoded JSON) keyed with the app secret.
  The payload names the app-scoped `user_id` whose data must go.

  The reply must be JSON with a `url` the person can open to check on the
  deletion, and a `confirmation_code` that page can be looked up by.

What "delete" means here is deliberately narrow and literal: everything this
app learned from Meta about that person goes - the access token, the cached
profile and media, and the contacts captured from their comments. The
DM Flow account itself is left alone, because it is not Meta's data and
deleting a merchant's billing history because Instagram asked would be its own
kind of wrong. The status page says exactly that, so nobody is misled.
"""

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, List, Optional, Tuple

from core import store

REQUESTS_FILE = "data/deletion_requests.json"
KEEP = 500


def _b64(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def parse_signed_request(signed_request: str, app_secret: str) -> Tuple[bool, Any]:
    """Verify and unpack. A bad signature is a refusal, never a shrug."""
    if not signed_request or "." not in signed_request:
        return False, "Malformed signed_request."
    if not app_secret:
        return False, "No app secret configured, so this cannot be verified."
    sig_part, payload_part = signed_request.split(".", 1)
    try:
        given = _b64(sig_part)
        payload = json.loads(_b64(payload_part).decode())
    except Exception as exc:
        return False, f"Could not decode signed_request: {exc}"

    if (payload.get("algorithm") or "").upper() != "HMAC-SHA256":
        return False, f"Unexpected algorithm {payload.get('algorithm')!r}."
    # The signature covers the encoded payload exactly as it arrived.
    want = hmac.new(app_secret.encode(), payload_part.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(given, want):
        return False, "Signature did not match the app secret."
    return True, payload


def _load() -> List[Dict[str, Any]]:
    try:
        rows = store.read(REQUESTS_FILE, []) if store.exists(REQUESTS_FILE) else []
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def record(code: str, meta_user_id: str, workspace_email: str,
           removed: Dict[str, Any]) -> None:
    rows = _load()
    rows.insert(0, {"code": code, "meta_user_id": meta_user_id,
                    "workspace": workspace_email, "at": time.time(),
                    "removed": removed, "status": "completed"})
    try:
        store.write(REQUESTS_FILE, rows[:KEEP])
    except Exception:
        pass


def lookup(code: str) -> Optional[Dict[str, Any]]:
    return next((r for r in _load() if r.get("code") == code), None)


def code_for(meta_user_id: str) -> str:
    """Stable per person and per day, so a repeated request reads the same."""
    seed = f"{meta_user_id}:{time.strftime('%Y%m%d')}"
    return hashlib.sha256(seed.encode()).hexdigest()[:16]
