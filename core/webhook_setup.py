"""
Webhook subscription and a live diagnostic for the comment -> DM chain.

Why this exists: `meta_oauth.subscribe_webhook()` only runs when a connection
has a Facebook `page_id`. An account connected through **Instagram Login**
(graph.instagram.com) has no page id, so that call was skipped - the account
connected, the dashboard showed the real profile and the real posts, and a
comment on a reel reached nothing at all. Everything looked right and nothing
fired.

There are TWO subscriptions, at two different levels, and both must exist.
Having one and not the other is the state that looks connected and is dead:

  1. APP level   - the Meta app says "send me `comments` for the `instagram`
                   object, at this callback URL". One per app, set once.
                   POST https://graph.facebook.com/v24.0/{app-id}/subscriptions

  2. ACCOUNT level - this merchant's Instagram account says "this app may have
                   my events". One per connected account.
                   POST https://graph.instagram.com/v24.0/me/subscribed_apps

Level 2 without level 1 is the silent failure the merchant cannot see: their
own account looks subscribed, and Meta never delivers, because the app itself
never asked for comment events. So `diagnose()` checks both and `repair()`
fixes both.

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
IG_BASE = os.environ.get("IG_GRAPH_BASE", "https://graph.instagram.com").rstrip("/")
if "graph.instagram.com" in IG_BASE:
    IG_BASE = IG_BASE + "/v24.0"

# App-level subscriptions live on the Facebook graph even for Instagram Login.
FB_BASE = os.environ.get("FB_GRAPH_BASE", "https://graph.facebook.com/v24.0").rstrip("/")

TIMEOUT = 20

# What the product actually needs. `comments` is the one that makes
# comment -> DM work at all; without it nothing else matters.
FIELDS = ["comments", "messages", "messaging_postbacks", "message_reactions", "live_comments"]

# The object name Meta uses for accounts connected with Instagram Login.
WEBHOOK_OBJECT = "instagram"


def _call(url: str, method: str = "GET", body: Dict[str, Any] = None) -> Tuple[bool, Any]:
    data = None
    headers = {"User-Agent": "ConverFlow"}
    if method == "POST":
        data = urllib.parse.urlencode(body or {}).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    try:
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return True, json.loads(res.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode())
            err = payload.get("error", {})
            msg = err.get("message") or f"HTTP {exc.code}"
            sub = err.get("error_user_msg")
            return False, (sub or msg)
        except Exception:
            return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------------- level 2
# The merchant's own account.

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
    """What this account is currently subscribed to - the truth, from Meta."""
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


# ---------------------------------------------------------------- level 1
# The Meta app itself. This is the one nobody can see from inside the product,
# and the one that is usually missing.

def _app_token(app_id: str, app_secret: str) -> str:
    return f"{app_id}|{app_secret}"


def app_subscriptions(app_id: str, app_secret: str) -> Tuple[bool, Any]:
    """Every webhook object this Meta app has registered."""
    if not (app_id and app_secret):
        return False, "The Meta app id and secret are not set in Admin -> Instagram API."
    url = (f"{FB_BASE}/{urllib.parse.quote(str(app_id))}/subscriptions"
           f"?access_token={urllib.parse.quote(_app_token(app_id, app_secret))}")
    return _call(url, "GET")


def app_instagram_state(app_id: str, app_secret: str) -> Tuple[bool, Dict[str, Any]]:
    """Just the `instagram` object: its fields, callback URL and active flag."""
    ok, data = app_subscriptions(app_id, app_secret)
    if not ok:
        return False, {"error": str(data)}
    for row in (data or {}).get("data", []):
        if (row.get("object") or "").lower() != WEBHOOK_OBJECT:
            continue
        names = []
        for f in row.get("fields", []) or []:
            names.append(f if isinstance(f, str) else f.get("name", ""))
        return True, {
            "present": True,
            "fields": [n for n in names if n],
            "callback_url": row.get("callback_url", ""),
            "active": bool(row.get("active", True)),
        }
    return True, {"present": False, "fields": [], "callback_url": "", "active": False}


def subscribe_app(app_id: str, app_secret: str, callback_url: str,
                  verify_token: str, fields: List[str] = None) -> Tuple[bool, Any]:
    """Register the app's own webhook for the `instagram` object.

    Meta verifies this synchronously: it calls `callback_url` with
    hub.mode=subscribe and our verify token before answering. So this only
    succeeds against a deployed, publicly reachable instance - which is
    exactly the state in which it matters.
    """
    if not (app_id and app_secret):
        return False, "The Meta app id and secret are not set in Admin -> Instagram API."
    if not callback_url:
        return False, "No webhook address to register."
    if not callback_url.startswith("https://"):
        return False, ("Meta only accepts an https callback. This instance is "
                       f"reachable at {callback_url}, which it will refuse.")
    url = f"{FB_BASE}/{urllib.parse.quote(str(app_id))}/subscriptions"
    return _call(url, "POST", {
        "object": WEBHOOK_OBJECT,
        "callback_url": callback_url,
        "fields": ",".join(fields or FIELDS),
        "verify_token": verify_token or "",
        "include_values": "true",
        "access_token": _app_token(app_id, app_secret),
    })


# ---------------------------------------------------------------- diagnose

def diagnose(user: Dict[str, Any], rules: List[Dict[str, Any]],
             webhook_url: str = "", meta_app: Dict[str, Any] = None) -> Dict[str, Any]:
    """Walk the whole chain and say, step by step, where it stops.

    Every check reports what IS, not what should be. A step we cannot verify
    says so rather than passing itself.
    """
    ig = (user or {}).get("instagram") or {}
    token = ig.get("access_token", "")
    meta_app = meta_app or {}
    checks: List[Dict[str, Any]] = []

    def add(key, label, state, detail, fix=""):
        checks.append({"key": key, "label": label, "state": state,
                       "detail": detail, "fix": fix})

    # 1 - is an account connected at all
    if not token:
        add("connected", "Instagram account connected", "fail",
            "No account is linked to this workspace.",
            "Connect Instagram from the Home screen.")
        return {"ok": False, "checks": checks, "verdict": "Not connected yet."}
    add("connected", "Instagram account connected", "pass",
        f"@{ig.get('username') or 'connected'}")

    # 2 - is the token still good
    ok, prof = _call(f"{IG_BASE}/me?fields=id,username,account_type"
                     f"&access_token={urllib.parse.quote(token)}")
    if not ok:
        add("token", "Access token still valid", "fail", str(prof),
            "Reconnect the account from Settings.")
        return {"ok": False, "checks": checks, "verdict": "The connection expired."}
    add("token", "Access token still valid", "pass",
        f"Instagram answered as @{prof.get('username', '')}")

    # 3 - account type. Personal accounts cannot receive automated DMs.
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

    # 4 - LEVEL 1. The app's own webhook. Invisible from inside the product,
    #     and the usual reason level 2 refuses to take `comments`.
    app_id = (meta_app.get("app_id") or "").strip()
    app_secret = (meta_app.get("app_secret") or "").strip()
    if not (app_id and app_secret):
        add("app_webhook", "Your Meta app forwards comments", "unknown",
            "The app id and secret are not saved, so this cannot be checked.",
            "An administrator sets these in Admin -> Instagram API.")
    else:
        got, state = app_instagram_state(app_id, app_secret)
        if not got:
            add("app_webhook", "Your Meta app forwards comments", "unknown",
                str(state.get("error", "Meta would not answer.")),
                "Check the app id and secret in Admin -> Instagram API.")
        elif not state["present"]:
            add("app_webhook", "Your Meta app forwards comments", "fail",
                "Your Meta app has no Instagram webhook at all.",
                "Press Repair below. Until this exists, Meta sends nothing - "
                "no matter what any single account is subscribed to.")
        elif "comments" not in state["fields"]:
            add("app_webhook", "Your Meta app forwards comments", "fail",
                ("The app is registered for "
                 + (", ".join(sorted(state["fields"])) or "nothing")
                 + " - but not comments."),
                "Press Repair below. This is almost always why an account "
                "refuses to subscribe to comments.")
        elif webhook_url and state["callback_url"] and \
                state["callback_url"].rstrip("/") != webhook_url.rstrip("/"):
            add("app_webhook", "Your Meta app forwards comments", "fail",
                f"Comments are sent to {state['callback_url']}, not to this app.",
                "Press Repair below to point them here instead.")
        elif not state["active"]:
            add("app_webhook", "Your Meta app forwards comments", "fail",
                "The webhook exists but Meta has switched it off, usually after "
                "repeated delivery failures.",
                "Press Repair below to re-register it.")
        else:
            add("app_webhook", "Your Meta app forwards comments", "pass",
                "Registered for " + ", ".join(sorted(state["fields"])))

    # 5 - LEVEL 2. This merchant's account.
    ok, fields = subscribed_fields(token)
    if not ok:
        add("webhook_sub", "This account allows comment events", "unknown",
            "Could not read the subscription from Instagram.",
            "Press Repair below to subscribe again.")
    elif "comments" in fields:
        add("webhook_sub", "This account allows comment events", "pass",
            "Subscribed to: " + ", ".join(sorted(fields)))
    else:
        add("webhook_sub", "This account allows comment events", "fail",
            ("Not subscribed to anything." if not fields
             else "Subscribed to " + ", ".join(sorted(fields)) + " - but not comments."),
            "Press Repair below. Without this, a comment reaches nothing.")

    # 6 - is there anything to fire
    live = [r for r in rules if r.get("is_active") and r.get("type") == "comment_to_dm"]
    if live:
        add("automation", "At least one flow is live", "pass",
            f"{len(live)} live flow{'s' if len(live) != 1 else ''}")
    else:
        add("automation", "At least one flow is live", "fail",
            "Every flow is paused, or there are none.",
            "Open a post on Home and turn a flow on.")

    # 7 - where Meta is told to deliver
    if webhook_url:
        add("webhook_url", "Webhook address", "info", webhook_url,
            "Repair registers this address with Meta for you. It must stay "
            "reachable - if this app moves, run Repair again.")

    failed = [c for c in checks if c["state"] == "fail"]
    unknown = [c for c in checks if c["state"] == "unknown"]
    if failed:
        verdict = failed[0]["detail"]
    elif unknown:
        verdict = "Mostly set up, but one step could not be verified."
    else:
        verdict = "The chain is complete. A comment on a live post will send a DM."
    return {"ok": not failed, "checks": checks, "verdict": verdict}


# ---------------------------------------------------------------- repair

def repair(access_token: str, meta_app: Dict[str, Any] = None,
           webhook_url: str = "") -> Dict[str, Any]:
    """Fix both levels, in the order that works, and report each honestly.

    App level first: subscribing an account to `comments` is refused while the
    app itself is not registered for them, so doing it the other way round
    fails for a reason the merchant would never guess.
    """
    meta_app = meta_app or {}
    app_id = (meta_app.get("app_id") or "").strip()
    app_secret = (meta_app.get("app_secret") or "").strip()
    verify_token = (meta_app.get("verify_token") or "").strip()
    steps: List[Dict[str, Any]] = []

    # Level 1
    if app_id and app_secret and webhook_url:
        ok, out = subscribe_app(app_id, app_secret, webhook_url, verify_token)
        steps.append({
            "level": "app",
            "label": "Register this app for Instagram comments",
            "ok": bool(ok),
            "detail": ("Meta accepted the callback and verified it."
                       if ok else str(out)),
        })
    else:
        missing = ("the app id and secret are" if not (app_id and app_secret)
                   else "the webhook address is")
        steps.append({
            "level": "app", "label": "Register this app for Instagram comments",
            "ok": False,
            "detail": f"Skipped - {missing} not set.",
        })

    # Level 2
    ok, out = subscribe(access_token)
    steps.append({
        "level": "account", "label": "Subscribe this account to comment events",
        "ok": bool(ok),
        "detail": "Instagram accepted it." if ok else str(out),
    })

    got_ok, fields = subscribed_fields(access_token)
    has_comments = got_ok and "comments" in fields

    if has_comments:
        message = "Fixed. A comment on a live post will now send a DM."
    elif not steps[0]["ok"]:
        message = ("The account was asked, but your Meta app is still not "
                   "registered for comments - that has to succeed first. "
                   + steps[0]["detail"])
    else:
        message = ("Instagram accepted the request but still does not list "
                   "comments. This usually means the connection was made "
                   "without the comments permission - reconnect the account "
                   "from Settings and approve every permission.")

    return {
        "success": has_comments,
        "steps": steps,
        "subscribed": fields,
        "comments": has_comments,
        "message": message,
    }
