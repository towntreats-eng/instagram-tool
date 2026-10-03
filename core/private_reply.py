"""
The right way to DM someone who commented.

This is the bug that made the whole product look broken even once the webhook
was delivering. Meta's messaging policy is blunt: a business may only message a
person inside the 24-hour window that *the person* opened by messaging first. A
commenter has not messaged anyone. So addressing them the ordinary way -

    {"recipient": {"id": "<their IGSID>"}, "message": {...}}

- is refused, and the merchant sees a comment arrive and no DM leave.

Comment-to-DM works through a different door, the **private reply**, which is
addressed by the comment rather than the person:

    POST https://graph.instagram.com/v24.0/me/messages
    {"recipient": {"comment_id": "<comment id>"}, "message": {...}}

Meta's limits on it, which the caller has to respect:

  * within **7 days** of the comment
  * **one private reply per comment**, ever - a retry is refused, so a failed
    send must not be blindly repeated
  * the account must be Business or Creator, and the app needs
    instagram_business_manage_messages

`meta_api.py` is a locked module and is left exactly as it is. This sits beside
it and is used only for the comment-triggered path; the DM-keyword path still
goes through the ordinary window, which is correct there because that person
really did message first.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

IG_BASE = os.environ.get("IG_GRAPH_BASE", "https://graph.instagram.com").rstrip("/")
if "graph.instagram.com" in IG_BASE:
    IG_BASE = IG_BASE + "/v24.0"
TIMEOUT = 15

# Meta codes that mean "this person cannot be addressed this way", as opposed
# to a transient failure. Used to decide whether a fallback is worth trying.
_UNREACHABLE = {10, 551, 200, 230}


def _post(url: str, payload: Dict[str, Any]) -> Tuple[bool, Any]:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "ConverFlow"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return True, json.loads(res.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        try:
            err = json.loads(exc.read().decode()).get("error", {})
            return False, {"message": err.get("message") or f"HTTP {exc.code}",
                           "code": err.get("code"),
                           "subcode": err.get("error_subcode")}
        except Exception:
            return False, {"message": f"HTTP {exc.code}", "code": None}
    except Exception as exc:
        return False, {"message": str(exc), "code": None}


def _message_body(text: str, button_text: Optional[str],
                  button_url: Optional[str]) -> Dict[str, Any]:
    if button_text and button_url:
        return {"attachment": {"type": "template", "payload": {
            "template_type": "generic",
            "elements": [{
                "title": (text or "")[:80],
                "subtitle": "Tap below to open it:",
                "buttons": [{"type": "web_url", "url": button_url,
                             "title": button_text[:20]}],
            }],
        }}}
    return {"text": text}


def send(access_token: str, comment_id: str, text: str,
         button_text: Optional[str] = None, button_url: Optional[str] = None,
         fallback_user_id: Optional[str] = None) -> Dict[str, Any]:
    """Private-reply to a comment. Returns the same shape meta_api uses.

    Order matters. The private reply is tried first because it is the only
    route that is allowed for a commenter who has never written to us. The
    plain recipient-id send is kept as a fallback for the case where this
    person *has* messaged the business recently, which makes the ordinary
    window legitimately open.
    """
    if not access_token:
        return {"success": False, "error": "This workspace has no Instagram token."}
    if not comment_id:
        return {"success": False, "error": "No comment to reply to."}

    url = f"{IG_BASE}/me/messages?access_token={urllib.parse.quote(access_token)}"
    rich = bool(button_text and button_url)

    attempts = [({"comment_id": str(comment_id)}, rich)]
    if rich:
        # A template the app is not approved for fails on its own; the text
        # with the link appended still delivers the thing that matters.
        attempts.append(({"comment_id": str(comment_id)}, False))
    if fallback_user_id:
        attempts.append(({"id": str(fallback_user_id)}, False))

    last: Dict[str, Any] = {}
    for recipient, use_rich in attempts:
        body = _message_body(
            text if use_rich else (f"{text}\n\n{button_url}" if button_url else text),
            button_text if use_rich else None,
            button_url if use_rich else None)
        ok, out = _post(url, {"recipient": recipient, "message": body})
        if ok:
            return {"success": True, "data": out,
                    "via": "private_reply" if "comment_id" in recipient else "direct"}
        last = out if isinstance(out, dict) else {"message": str(out)}
        # A hard "you may not message this person" is not worth retrying with
        # the same door; the loop moves on to the next one, which is the point.

    msg = last.get("message", "Instagram refused the message.")
    code = last.get("code")
    hint = ""
    if code in _UNREACHABLE:
        hint = (" Instagram only allows one private reply per comment, within "
                "7 days of it. If this comment was already answered, that is "
                "expected.")
    elif code == 100:
        hint = (" Usually the comment id is stale, or the app does not have "
                "instagram_business_manage_messages.")
    return {"success": False, "error": f"{msg}{hint}", "code": code}

