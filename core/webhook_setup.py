"""
Webhook subscription and a live diagnostic for the comment → DM chain.

Why this exists: `meta_oauth.subscribe_webhook()` only runs when a connection
has a Facebook `page_id`. An account connected through **Instagram Login**
(graph.instagram.com) has no page id, so that call was skipped — the account
connected, the dashboard showed the real profile and the real posts, and a
comment on a reel reached nothing at all. Everything looked right and nothing
fired.

Instagram Login subscribes through its own endpoint:

    POST https://graph.instagram.com/v24.0/me/subscribed_apps
         ?subscribed_fields=comments,messages,...&access_token=<IG user token>

`meta_oauth.py` and `meta_api.py` are left untouched; this is additive.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Tuple

# Overridable so the subscription chain can be exercised against a local
# double. Unset in production, where it is Instagram itself.
IG_BASE = os.environ.get("IG_GRAPH_BASE", "https://graph.instagram.com") .rstrip("/")
if "graph.instagram.com" in IG_BASE:
    IG_BASE = IG_BASE + "/v24.0"
TIMEOUT = 20

# What the product actually needs. `comments` is the one that makes
# comment → DM work at all; without it nothing else matters.
FIELDS = ["comments", "messages", "messaging_postbacks", "message_reactions", "live_comments"]


def _call(url: str, method: str = "GET") -> Tuple[bool, Any]:
    try:
        req = urllib.request.Request(url, data=b"" if method == "POST" else None,
                                     method=method, headers={"User-Agent": "ConverFlow"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return True, json.loads(res.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode())
            return False, body.get("error", {}).get("message") or f"HTTP {exc.code}"
        except Exception:
            return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)


def subscribe(access_token: str, fields: List[str] = None) -> Tuple[bool, Any]:
    """Tell Instagram to send this account's comment and message events to us."""
    if not access_token:
        return False, "No Instagram token on this workspace."
    want = ",".join(fields or FIELDS)
    url = (f"{IG_BASE}/me/subscribed_apps"
           f"?subscribed_fields={urllib.parse.quote(want)}"
           f"&access_token={urllib.parse.quote(access_token)}")
    return _call(url, "POST")


def subscriptions(access_token: str) -> Tuple[bool, Any]:
    """What this account is currently subscribed to — the truth, from Meta."""
    if not access_token:
        return False, "No Instagram token on this workspace."
    url = f"{IG_BASE}/me/subscribed_apps?access_token={urllib.parse.quote(access_token)}"
    return _call(url, "GET")


def subscribed_fields(access_token: str) -> Tuple[bool, List[str]]:
    ok, data = subscriptions(access_token)
    if not ok:
        return False, []
    out: List[str] = []
    for row in (data or {}).get("data", []):
        for f in row.get("subscribed_fields", []):
            out.append(f if isinstance(f, str) else f.get("name", ""))
    return True, [f for f in out if f]


def diagnose(user: Dict[str, Any], rules: List[Dict[str, Any]],
             webhook_url: str = "") -> Dict[str, Any]:
    """Walk the whole chain and say, step by step, where it stops.

    Every check reports what IS, not what should be. A step we cannot verify
    says so rather than passing itself.
    """
    ig = (user or {}).get("instagram") or {}
    token = ig.get("access_token", "")
    checks: List[Dict[str, Any]] = []

    def add(key, label, state, detail, fix=""):
        checks.append({"key": key, "label": label, "state": state,
                       "detail": detail, "fix": fix})

    # 1 — is an account connected at all
    if not token:
        add("connected", "Instagram account connected", "fail",
            "No account is linked to this workspace.",
            "Connect Instagram from the Home screen.")
        return {"ok": False, "checks": checks, "verdict": "Not connected yet."}
    add("connected", "Instagram account connected", "pass",
        f"@{ig.get('username') or 'connected'}")

    # 2 — is the token still good
    ok, prof = _call(f"{IG_BASE}/me?fields=id,username,account_type"
                     f"&access_token={urllib.parse.quote(token)}")
    if not ok:
        add("token", "Access token still valid", "fail", str(prof),
            "Reconnect the account from Settings.")
        return {"ok": False, "checks": checks, "verdict": "The connection expired."}
    add("token", "Access token still valid", "pass",
        f"Instagram answered as @{prof.get('username', '')}")

    # 3 — account type. Personal accounts cannot receive automated DMs.
    kind = (prof.get("account_type") or "").upper()
    if kind in ("BUSINESS", "MEDIA_CREATOR", "CREATOR"):
        add("account_type", "Business or Creator account", "pass", kind.title())
    elif kind:
        add("account_type", "Business or Creator account", "fail",
            f"This is a {kind.title()} account.",
            "Switch to a Business or Creator account in the Instagram app. "
            "Meta blocks automated DMs on personal accounts.")
    else:
        add("account_type", "Business or Creator account", "unknown",
            "Instagram did not report the account type.")

    # 4 — THE one that was silently missing
    ok, fields = subscribed_fields(token)
    if not ok:
        add("webhook_sub", "Subscribed to comment events", "unknown",
            "Could not read the subscription from Instagram.",
            "Press Repair below to subscribe again.")
    elif "comments" in fields:
        add("webhook_sub", "Subscribed to comment events", "pass",
            "Subscribed to: " + ", ".join(sorted(fields)))
    else:
        add("webhook_sub", "Subscribed to comment events", "fail",
            ("Not subscribed to anything." if not fields
             else "Subscribed to " + ", ".join(sorted(fields)) + " — but not comments."),
            "Press Repair below. Without this, a comment reaches nothing.")

    # 5 — is there anything to fire
    live = [r for r in rules if r.get("is_active") and r.get("type") == "comment_to_dm"]
    if live:
        add("automation", "At least one flow is live", "pass",
            f"{len(live)} live flow{'s' if len(live) != 1 else ''}")
    else:
        add("automation", "At least one flow is live", "fail",
            "Every flow is paused, or there are none.",
            "Open a post on Home and turn a flow on.")

    # 6 — where Meta is told to deliver
    if webhook_url:
        add("webhook_url", "Webhook address", "info", webhook_url,
            "This must match the Callback URL in your Meta app under "
            "Webhooks → Instagram, and the app must subscribe to the "
            "'comments' field there too.")

    failed = [c for c in checks if c["state"] == "fail"]
    unknown = [c for c in checks if c["state"] == "unknown"]
    if failed:
        verdict = failed[0]["detail"]
    elif unknown:
        verdict = "Mostly set up, but one step could not be verified."
    else:
        verdict = "The chain is complete. A comment on a live post will send a DM."
    return {"ok": not failed, "checks": checks, "verdict": verdict}
