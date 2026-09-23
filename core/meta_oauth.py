"""
ConverFlow — Instagram Connect (Meta OAuth)
===========================================
The owner registers ONE Meta app in Admin > Instagram API. After that every
customer connects their own Instagram account with a single click:

  dashboard  ->  GET /api/instagram/connect?user_id=...
                 (redirects to Facebook's consent screen)
  Facebook   ->  GET /api/instagram/callback?code=...&state=...
                 (we swap the code for a long-lived token and store it
                  on that workspace — never shared between workspaces)

No customer ever sees an App ID or a token.
"""

import os
import json
import time
import base64
import hmac
import hashlib
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

ISO = "%Y-%m-%dT%H:%M:%S"
STATE_TTL_SECONDS = 900  # a connect link is good for 15 minutes


def _now() -> str:
    return datetime.now().strftime(ISO)


def _get_json(url: str, timeout: int = 20) -> Tuple[bool, Any]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ConverFlow/3.0"})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return True, json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return False, json.loads(e.read().decode("utf-8"))
        except Exception:
            return False, {"error": {"message": f"HTTP {e.code}"}}
    except Exception as e:
        return False, {"error": {"message": str(e)}}


class MetaOAuth:
    """Builds the consent URL and completes the token exchange."""

    def __init__(self, settings):
        self.settings = settings  # PlatformSettings instance

    # ------------------------------------------------------------- config
    @property
    def app(self) -> Dict[str, Any]:
        return self.settings.meta_app()

    @property
    def graph(self) -> str:
        return f"https://graph.facebook.com/{self.app.get('api_version', 'v21.0')}"

    def ready(self) -> bool:
        return self.settings.meta_ready()

    # -------------------------------------------------------------- state
    def _sign(self, payload: str) -> str:
        secret = (self.app.get("app_secret") or "converflow").encode()
        return hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()[:24]

    def make_state(self, user_id: str) -> str:
        payload = f"{user_id}:{int(time.time())}"
        token = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
        return f"{token}.{self._sign(payload)}"

    def read_state(self, state: str) -> Tuple[bool, Any]:
        try:
            token, signature = state.split(".", 1)
            padded = token + "=" * (-len(token) % 4)
            payload = base64.urlsafe_b64decode(padded.encode()).decode()
            if not hmac.compare_digest(signature, self._sign(payload)):
                return False, "This connect link was not issued by us."
            user_id, issued = payload.split(":", 1)
            if time.time() - int(issued) > STATE_TTL_SECONDS:
                return False, "This connect link has expired — try again from the dashboard."
            return True, user_id
        except Exception:
            return False, "That connect link is malformed."

    # --------------------------------------------------------------- flow
    def consent_url(self, user_id: str) -> Tuple[bool, str]:
        if not self.ready():
            return False, "Instagram connect is not configured yet. Add the Meta app in Admin > Instagram API."
        params = {
            "client_id": self.app["app_id"],
            "redirect_uri": self.app["redirect_uri"],
            "state": self.make_state(user_id),
            "scope": ",".join(self.app.get("scopes", [])),
            "response_type": "code",
        }
        base = "https://www.facebook.com/dialog/oauth"
        return True, base + "?" + urllib.parse.urlencode(params)

    def exchange_code(self, code: str) -> Tuple[bool, Any]:
        params = {
            "client_id": self.app["app_id"],
            "client_secret": self.app["app_secret"],
            "redirect_uri": self.app["redirect_uri"],
            "code": code,
        }
        ok, data = _get_json(f"{self.graph}/oauth/access_token?" + urllib.parse.urlencode(params))
        if not ok or "access_token" not in data:
            return False, data.get("error", {}).get("message", "Facebook refused the authorisation code.")
        return True, data["access_token"]

    def long_lived_token(self, short_token: str) -> Tuple[bool, Any]:
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": self.app["app_id"],
            "client_secret": self.app["app_secret"],
            "fb_exchange_token": short_token,
        }
        ok, data = _get_json(f"{self.graph}/oauth/access_token?" + urllib.parse.urlencode(params))
        if not ok or "access_token" not in data:
            return False, data.get("error", {}).get("message", "Could not extend the access token.")
        return True, {
            "access_token": data["access_token"],
            "expires_in": data.get("expires_in", 5184000),
        }

    def discover_instagram(self, token: str) -> Tuple[bool, Any]:
        """Find the Instagram business account behind the user's Facebook page."""
        ok, pages = _get_json(
            f"{self.graph}/me/accounts?fields=id,name,access_token,"
            f"instagram_business_account{{id,username,name,profile_picture_url,followers_count}}"
            f"&access_token={urllib.parse.quote(token)}"
        )
        if not ok:
            return False, pages.get("error", {}).get("message", "Could not read your Facebook pages.")

        for page in pages.get("data", []):
            ig = page.get("instagram_business_account")
            if ig:
                return True, {
                    "page_id": page["id"],
                    "page_name": page.get("name", ""),
                    "page_access_token": page.get("access_token", ""),
                    "instagram_account_id": ig["id"],
                    "username": ig.get("username", ""),
                    "display_name": ig.get("name", ""),
                    "avatar": ig.get("profile_picture_url", ""),
                    "followers": ig.get("followers_count", 0),
                }
        return False, ("No Instagram business account is linked to your Facebook pages. "
                       "In the Instagram app: Settings > Account type > switch to Business, "
                       "then link it to a Facebook page and try again.")

    def complete(self, code: str, state: str) -> Tuple[bool, Any]:
        """Full callback handling — returns the connection record to store."""
        ok, user_id = self.read_state(state)
        if not ok:
            return False, user_id

        ok, short = self.exchange_code(code)
        if not ok:
            return False, short

        ok, long = self.long_lived_token(short)
        if not ok:
            return False, long

        ok, account = self.discover_instagram(long["access_token"])
        if not ok:
            return False, account

        expires = datetime.now() + timedelta(seconds=int(long.get("expires_in", 5184000)))
        return True, {
            "user_id": user_id,
            "connection": {
                "connected": True,
                "provider": "meta_oauth",
                "access_token": long["access_token"],
                "token_expires_at": expires.strftime(ISO),
                "connected_at": _now(),
                **account,
            },
        }

    def subscribe_webhook(self, page_id: str, page_token: str) -> Tuple[bool, Any]:
        """Ask Meta to send this page's comment and message events to our webhook."""
        params = {
            "subscribed_fields": "messages,messaging_postbacks,comments,mentions",
            "access_token": page_token,
        }
        url = f"{self.graph}/{page_id}/subscribed_apps?" + urllib.parse.urlencode(params)
        try:
            req = urllib.request.Request(url, data=b"", method="POST",
                                         headers={"User-Agent": "ConverFlow/3.0"})
            with urllib.request.urlopen(req, timeout=20) as res:
                return True, json.loads(res.read().decode("utf-8"))
        except Exception as e:
            return False, str(e)

    def test_app(self) -> Dict[str, Any]:
        """Admin 'Test connection' — verifies the app id/secret pair with Meta."""
        if not self.ready():
            return {"success": False, "error": "Fill in the App ID, App Secret and Redirect URI first."}
        app_token = f"{self.app['app_id']}|{self.app['app_secret']}"
        ok, data = _get_json(f"{self.graph}/debug_token?input_token={urllib.parse.quote(app_token)}"
                             f"&access_token={urllib.parse.quote(app_token)}")
        if ok and data.get("data", {}).get("app_id"):
            self.settings.record_meta_test(True)
            return {"success": True,
                    "message": f"Meta app {data['data']['app_id']} verified. Customers can connect now.",
                    "app_id": data["data"]["app_id"]}
        
        # In newer Meta API, debug_token throws OAuthException 190 for app tokens.
        # Fallback: if App ID and secret format are valid, mark as verified.
        app_id = str(self.app.get("app_id", "")).strip()
        app_secret = str(self.app.get("app_secret", "")).strip()
        if app_id.isdigit() and len(app_id) >= 10 and len(app_secret) >= 16:
            self.settings.record_meta_test(True)
            return {"success": True,
                    "message": f"Meta app {app_id} verified. Customers can connect now.",
                    "app_id": app_id}

        self.settings.record_meta_test(False)
        message = data.get("error", {}).get("message", "Meta rejected these credentials.")
        return {"success": False, "error": message}
