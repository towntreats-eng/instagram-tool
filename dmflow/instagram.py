"""
Everything this app says to Instagram, in one place.

Instagram API with Instagram Login (graph.instagram.com). No Facebook Page,
no Facebook Login. Every function returns (ok, data_or_error_message) and
never raises, so a bad answer from Meta becomes a sentence a merchant can
read instead of a 500.

Base URLs are overridable (IG_GRAPH_BASE, IG_API_BASE) only so the whole
module can be exercised against a local stand-in for Meta in tests.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from dmflow import settings

TIMEOUT = 20
SCOPES = ["instagram_business_basic",
          "instagram_business_manage_comments",
          "instagram_business_manage_messages"]
WEBHOOK_FIELDS = ["comments", "messages", "messaging_postbacks"]

Result = Tuple[bool, Any]


def _graph() -> str:
    base = os.environ.get("IG_GRAPH_BASE", "https://graph.instagram.com").rstrip("/")
    return f"{base}/{settings.get('graph_version')}"


def _graph_root() -> str:
    return os.environ.get("IG_GRAPH_BASE", "https://graph.instagram.com").rstrip("/")


def _api() -> str:
    return os.environ.get("IG_API_BASE", "https://api.instagram.com").rstrip("/")


def _authorize_base() -> str:
    return os.environ.get("IG_AUTHORIZE_URL", "https://www.instagram.com/oauth/authorize")


def _call(method: str, url: str, params: Optional[Dict[str, Any]] = None,
          body: Optional[Dict[str, Any]] = None, form: Optional[Dict[str, Any]] = None) -> Result:
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    data, headers = None, {"User-Agent": "DMFlow/2"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    elif form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    try:
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            raw = res.read().decode() or "{}"
            return True, json.loads(raw)
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode() or "{}")
        except Exception:
            payload = {}
        err = payload.get("error") if isinstance(payload.get("error"), dict) else {}
        msg = (err.get("error_user_msg") or err.get("message")
               or payload.get("error_message") or f"HTTP {exc.code}")
        code = err.get("code")
        return False, {"message": msg, "code": code, "subcode": err.get("error_subcode"),
                       "status": exc.code}
    except Exception as exc:
        return False, {"message": str(exc), "code": None}


def err_text(out: Any) -> str:
    return out.get("message", str(out)) if isinstance(out, dict) else str(out)


# ------------------------------------------------------------------- connect
def authorize_url(redirect_uri: str, state: str) -> str:
    q = {"client_id": settings.get("ig_app_id"), "redirect_uri": redirect_uri,
         "response_type": "code", "scope": ",".join(SCOPES), "state": state,
         "force_reauth": "true"}
    return _authorize_base() + "?" + urllib.parse.urlencode(q)


def exchange_code(code: str, redirect_uri: str) -> Result:
    """code -> short-lived token. Meta has answered this in two shapes over
    time ({access_token,...} and {data:[{...}]}); accept both."""
    code = (code or "").split("#")[0].strip()
    ok, out = _call("POST", f"{_api()}/oauth/access_token", form={
        "client_id": settings.get("ig_app_id"),
        "client_secret": settings.get("ig_app_secret"),
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
        "code": code})
    if not ok:
        return False, err_text(out)
    if isinstance(out.get("data"), list) and out["data"]:
        out = out["data"][0]
    if not out.get("access_token"):
        return False, "Instagram did not return an access token."
    return True, {"token": out["access_token"], "app_user_id": str(out.get("user_id", ""))}


def long_lived(short_token: str) -> Result:
    ok, out = _call("GET", f"{_graph_root()}/access_token", params={
        "grant_type": "ig_exchange_token",
        "client_secret": settings.get("ig_app_secret"),
        "access_token": short_token})
    if not ok or not out.get("access_token"):
        return False, err_text(out) if not ok else "No long-lived token returned."
    return True, {"token": out["access_token"], "expires_in": int(out.get("expires_in") or 5184000)}


def refresh(token: str) -> Result:
    ok, out = _call("GET", f"{_graph_root()}/refresh_access_token", params={
        "grant_type": "ig_refresh_token", "access_token": token})
    if not ok or not out.get("access_token"):
        return False, err_text(out) if not ok else "No token returned."
    return True, {"token": out["access_token"], "expires_in": int(out.get("expires_in") or 5184000)}


def profile(token: str) -> Result:
    """The truth about the connected account. `user_id` is the professional
    account id that webhooks carry; `id` is the app-scoped id."""
    ok, out = _call("GET", f"{_graph()}/me", params={
        "fields": "id,user_id,username,name,profile_picture_url,followers_count,media_count,account_type",
        "access_token": token})
    if not ok:
        return False, err_text(out)
    return True, out


def subscribe(token: str) -> Result:
    ok, out = _call("POST", f"{_graph()}/me/subscribed_apps", params={
        "subscribed_fields": ",".join(WEBHOOK_FIELDS), "access_token": token})
    return (True, out) if ok else (False, err_text(out))


def unsubscribe(token: str) -> Result:
    ok, out = _call("DELETE", f"{_graph()}/me/subscribed_apps", params={"access_token": token})
    return (True, out) if ok else (False, err_text(out))


def revoke(token: str) -> Result:
    """Ask Instagram to drop this app's permissions for the account. Instagram
    Login does not document a revoke endpoint the way Facebook Login does, so
    this is attempted and its answer reported - never assumed."""
    ok, out = _call("DELETE", f"{_graph()}/me/permissions", params={"access_token": token})
    return (True, out) if ok else (False, err_text(out))


def subscribed_fields(token: str) -> Result:
    ok, out = _call("GET", f"{_graph()}/me/subscribed_apps", params={"access_token": token})
    if not ok:
        return False, err_text(out)
    fields: List[str] = []
    for row in out.get("data", []):
        for f in row.get("subscribed_fields", []):
            fields.append(f if isinstance(f, str) else f.get("name", ""))
    return True, [f for f in fields if f]


# --------------------------------------------------------------------- media
def media(token: str, limit: int = 24) -> Result:
    ok, out = _call("GET", f"{_graph()}/me/media", params={
        "fields": "id,caption,media_type,media_product_type,media_url,thumbnail_url,permalink,timestamp,comments_count,like_count",
        "limit": limit, "access_token": token})
    return (True, out.get("data", [])) if ok else (False, err_text(out))


def comments(token: str, media_id: str, limit: int = 30) -> Result:
    ok, out = _call("GET", f"{_graph()}/{urllib.parse.quote(str(media_id))}/comments", params={
        "fields": "id,text,timestamp,username,from", "limit": limit, "access_token": token})
    if not ok:  # `from` is not always readable; the comment id is enough to reply
        ok, out = _call("GET", f"{_graph()}/{urllib.parse.quote(str(media_id))}/comments", params={
            "fields": "id,text,timestamp,username", "limit": limit, "access_token": token})
    return (True, out.get("data", [])) if ok else (False, err_text(out))


# ------------------------------------------------------------------ messaging
def public_reply(token: str, comment_id: str, text: str) -> Result:
    ok, out = _call("POST", f"{_graph()}/{urllib.parse.quote(str(comment_id))}/replies",
                    params={"message": text, "access_token": token})
    return (True, out) if ok else (False, err_text(out))


def _btn(b: Dict[str, str]) -> Dict[str, Any]:
    if b.get("url"):
        return {"type": "web_url", "url": b["url"], "title": b["title"][:20]}
    return {"type": "postback", "payload": b["payload"], "title": b["title"][:20]}


def _button_template(text: str, buttons: List[Dict[str, str]]) -> Dict[str, Any]:
    """Meta's limits: text <= 640, label <= 20, <= 3 buttons."""
    return {"attachment": {"type": "template", "payload": {
        "template_type": "button", "text": (text or "")[:640],
        "buttons": [_btn(b) for b in buttons[:3]]}}}


def _generic_template(text: str, buttons: List[Dict[str, str]]) -> Dict[str, Any]:
    """Card form: title and subtitle are 80 characters each."""
    t = (text or "").strip()
    first, _, rest = t.partition("\n")
    title = first.strip()[:80] or "Hi!"
    sub = (rest.strip() or t[len(title):].strip())[:80]
    el: Dict[str, Any] = {"title": title, "buttons": [_btn(b) for b in buttons[:3]]}
    if sub:
        el["subtitle"] = sub
    return {"attachment": {"type": "template", "payload": {"template_type": "generic", "elements": [el]}}}


def _quick_replies(text: str, buttons: List[Dict[str, str]]) -> Dict[str, Any]:
    """Postbacks as quick-reply chips; links go into the text."""
    links = [b["url"] for b in buttons if b.get("url")]
    body = (text or "") + ("\n\n" + "\n".join(links) if links else "")
    return {"text": body[:1000], "quick_replies": [
        {"content_type": "text", "title": b["title"][:20], "payload": b["payload"]}
        for b in buttons if b.get("payload")][:13]}


def _plain(text: str, buttons: List[Dict[str, str]]) -> Dict[str, Any]:
    links = [b["url"] for b in (buttons or []) if b.get("url")]
    body = text or ""
    if links and not any(l in body for l in links):
        body = body.rstrip() + "\n\n" + "\n".join(links)
    return {"text": body[:1000]}


def send(token: str, recipient: Dict[str, str], text: str,
         buttons: Optional[List[Dict[str, str]]] = None) -> Result:
    """recipient is {"comment_id": ...} for a private reply (once per comment,
    within 7 days) or {"id": IGSID} inside an open 24-hour window.

    Tries the richest form first and steps down. A refused call does not use
    up the one private reply a comment allows, so stepping down is safe. A
    message with a tap-to-continue button never degrades to plain text: that
    would ask for a tap the person cannot make (the caller decides instead)."""
    url = f"{_graph()}/me/messages"
    buttons = [b for b in (buttons or []) if b.get("url") or b.get("payload")]
    has_postback = any(b.get("payload") for b in buttons)
    shapes = []
    if buttons:
        shapes += [_button_template, _generic_template]
    if has_postback:
        shapes.append(_quick_replies)
    else:
        shapes.append(_plain)
    first_err = None
    for shape in shapes:
        ok, out = _call("POST", url, params={"access_token": token},
                        body={"recipient": recipient, "message": shape(text, buttons)})
        if ok:
            return True, out
        first_err = first_err or err_text(out)
    return False, first_err or "refused"


def follows(token: str, igsid: str) -> Tuple[Optional[bool], str]:
    """True / False, or None when Instagram will not say. Readable only after
    the person has messaged the account - which tapping the opening DM's
    button counts as."""
    ok, out = _call("GET", f"{_graph()}/{urllib.parse.quote(str(igsid))}",
                    params={"fields": "is_user_follow_business,username", "access_token": token})
    if not ok:
        return None, err_text(out)
    val = out.get("is_user_follow_business")
    return (bool(val) if val is not None else None), ""
