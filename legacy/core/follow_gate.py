"""
Follow-gate: hold the link back until the commenter follows the account.

Why this is its own module and not a change to meta_api.py: meta_api is the
locked Instagram integration. `check_user_follows()` there returns a plain
bool, and a bool cannot tell "they do not follow" apart from "Instagram would
not tell us". Those two need different behaviour, so the tri-state lives here
and the locked module is left exactly as it is.

The distinction matters more than it sounds. Meta's own docs say user-profile
access needs consent, and that consent "occurs only when a person messages the
business". At the moment a *comment* webhook fires the commenter has not
messaged us yet, so the profile call can come back empty — not false, empty.
A gate that reads empty as "not following" blocks the account's real followers
and every merchant using it thinks the product is broken.

So:
  FOLLOWS      -> send the real message
  NOT_FOLLOWING-> send the follow prompt, withhold the link
  UNKNOWN      -> send the follow prompt too, but say so honestly and let their
                  reply open the conversation; the second pass can see the truth
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

FOLLOWS = "follows"
NOT_FOLLOWING = "not_following"
UNKNOWN = "unknown"

TIMEOUT = 6
FIELD = "is_user_follow_business"


def _get(url: str) -> Tuple[bool, Any]:
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
            return True, json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            return False, json.loads(exc.read().decode())
        except Exception:
            return False, {"error": {"message": f"HTTP {exc.code}"}}
    except Exception as exc:
        return False, {"error": {"message": str(exc)}}


def status(commenter_id: str, access_token: str) -> Tuple[str, str]:
    """Returns (FOLLOWS | NOT_FOLLOWING | UNKNOWN, reason-for-the-log)."""
    if not (commenter_id and access_token):
        return UNKNOWN, "No token or no commenter id."

    bases = ["https://graph.instagram.com/v21.0", "https://graph.facebook.com/v21.0"]
    last = ""
    for base in bases:
        url = (f"{base}/{urllib.parse.quote(str(commenter_id))}"
               f"?fields={FIELD}&access_token={urllib.parse.quote(access_token)}")
        ok, data = _get(url)
        if ok and FIELD in data:
            return (FOLLOWS if data[FIELD] else NOT_FOLLOWING), "Instagram answered."
        err = (data or {}).get("error", {}) if isinstance(data, dict) else {}
        last = err.get("message", "no answer")
        # A permissions/consent error is not "they don't follow" — keep it unknown.
        if err.get("code") in (10, 200, 230, 100):
            return UNKNOWN, f"Instagram would not say: {last}"
    return UNKNOWN, f"Could not read follow status: {last}"


def owner_handle(rule: Dict[str, Any], user: Optional[Dict[str, Any]]) -> str:
    """The handle the gate should tell people to follow — the RULE OWNER'S.

    This used to fall back to a hard-coded handle, which meant another
    merchant's follow prompt pointed their audience at somebody else's account.
    """
    ig = (user or {}).get("instagram") or {}
    return (rule.get("connected_account_username")
            or ig.get("username")
            or (user or {}).get("ig_handle")
            or "").lstrip("@")


def prompt_text(rule: Dict[str, Any], handle: str, username: str, known: bool) -> str:
    custom = (rule.get("follow_prompt_msg") or "").strip()
    if custom:
        base = custom
    elif known:
        base = ("Hey {name}! One step — follow @{handle} and I'll send the link straight away. "
                "Already followed? Just reply DONE.")
    else:
        # We could not verify, so we do not assert that they are not following.
        base = ("Hey {name}! Reply DONE and I'll send the link. "
                "If you're not following @{handle} yet, follow first so it reaches you.")
    return (base.replace("{name}", username or "there")
                .replace("{first_name}", username or "there")
                .replace("{username}", username or "there")
                .replace("{handle}", handle or "us"))
