"""
Flows, and what happens when someone comments.

The sequence is the one Meta's rules make possible:

  1. Someone comments on a post a live flow is watching.
  2. Optionally, a short public reply under their comment.
  3. A PRIVATE REPLY: the opening DM, with one button ("Send me the link").
     Meta allows exactly one private reply per comment, within 7 days, and
     the commenter has not messaged the account, so this is the only DM that
     may be sent at this point.
  4. They tap the button. That tap is them messaging the account, which opens
     Instagram's 24-hour window and arrives here as a postback.
  5. If the flow has a follow-gate: are they following? If not, one message
     asking them to, with a button to check again.
  6. The link.

With the opening DM switched off, step 3 sends the link straight away and
there is no step 4 - simpler, but no follow-gate is possible, because whether
someone follows can only be read after they have messaged the account.
"""

import random
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from dmflow import accounts, db, instagram, settings

TEXT_MAX, BUTTON_MAX = 640, 20

TEMPLATE = {
    "post": {"mode": "specific", "media_id": "", "thumb": "", "caption": "", "permalink": ""},
    "trigger": {"mode": "keyword", "keywords": []},
    "public_reply": {"on": True, "variants": ["Thanks! Please see DMs.",
                                              "Sent you a message! Check it out!",
                                              "Nice! Check your DMs!"]},
    "opening": {"on": True,
                "text": "Hey there! I'm so happy you're here, thanks so much for your interest.\n\n"
                        "Click below and I'll send you the link in just a sec.",
                "button": "Send me the link"},
    "follow_gate": {"on": False,
                    "text": "Almost there! This one is for followers only. Follow the account, "
                            "then tap the button below and I'll send it right away.",
                    "button": "I'm following"},
    "link": {"text": "Here is the link you asked for.", "button": "Open link", "url": ""},
}


# ---------------------------------------------------------------------- log
def log(user_id: str, kind: str, verdict: str, *, source: str = "", flow_id: str = "",
        username: str = "", text: str = "", note: str = "") -> None:
    try:
        db.execute("INSERT INTO dm_events (id, user_id, at, source, kind, flow_id, username, text, verdict, note) "
                   "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (db.new_id("e_"), user_id or "", db.now(), source, kind, flow_id or "",
                    username or "", (text or "")[:300], verdict, (note or "")[:500]))
    except Exception:
        pass  # a diagnostic must never break what it diagnoses


def events(user_id: str, limit: int = 30) -> List[Dict[str, Any]]:
    return db.query("SELECT * FROM dm_events WHERE user_id = ? ORDER BY at DESC LIMIT ?", (user_id, limit))


def _month_start() -> int:
    t = time.gmtime()
    return int(time.mktime((t.tm_year, t.tm_mon, 1, 0, 0, 0, 0, 0, -1)))


SENT_VERDICTS = ("sent", "link_sent", "held")


def dms_this_month(user_id: str) -> int:
    row = db.one("SELECT COUNT(*) AS n FROM dm_events WHERE user_id = ? AND at >= ? "
                 "AND verdict IN ('sent', 'link_sent', 'held')", (user_id, _month_start()))
    return int((row or {}).get("n") or 0)


# -------------------------------------------------------------------- flows
def _merge(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in base.items():
        p = (patch or {}).get(k)
        out[k] = _merge(v, p) if isinstance(v, dict) else (p if p is not None else v)
    return out


def normalise(body: Dict[str, Any]) -> Dict[str, Any]:
    b = _merge(TEMPLATE, body or {})
    kws = b["trigger"]["keywords"]
    if isinstance(kws, str):
        kws = kws.split(",")
    b["trigger"]["keywords"] = [k.strip() for k in kws if k and k.strip()][:20]
    b["public_reply"]["variants"] = [v.strip() for v in b["public_reply"]["variants"] if v and v.strip()][:3]
    if b["follow_gate"]["on"]:
        b["opening"]["on"] = True  # following can only be read after they message
    return b


def validate(b: Dict[str, Any], plan: Dict[str, Any]) -> List[str]:
    errs = []
    if b["post"]["mode"] == "specific" and not b["post"]["media_id"]:
        errs.append("Pick the post this automation should watch.")
    if b["post"]["mode"] == "any" and not plan.get("features", {}).get("any_post"):
        errs.append(f"'Any post' is not included in the {plan['name']} plan.")
    if b["trigger"]["mode"] == "keyword" and not b["trigger"]["keywords"]:
        errs.append("Add at least one keyword, or choose 'any comment'.")
    if b["public_reply"]["on"] and not b["public_reply"]["variants"]:
        errs.append("Write at least one public reply, or switch public replies off.")
    for part in ("opening", "follow_gate"):
        if b[part]["on"]:
            if not b[part]["text"].strip():
                errs.append(f"The {part.replace('_', ' ')} message is empty.")
            if not (0 < len(b[part]["button"].strip()) <= BUTTON_MAX):
                errs.append(f"The {part.replace('_', ' ')} button needs a label of 1-{BUTTON_MAX} characters.")
    url = b["link"]["url"].strip()
    if not re.match(r"^https?://[^\s.]+\.[^\s]+$", url):
        errs.append("The link must be a full address starting with https://")
    if not (0 < len(b["link"]["button"].strip()) <= BUTTON_MAX):
        errs.append(f"The link button needs a label of 1-{BUTTON_MAX} characters.")
    for part in ("opening", "follow_gate", "link"):
        if len(b[part]["text"]) > TEXT_MAX:
            errs.append(f"The {part.replace('_', ' ')} message is over {TEXT_MAX} characters.")
    return errs


def flow_row(r: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": r["id"], "name": r["name"], "status": r["status"],
            "body": normalise(db.jload(r["body"], {})),
            "created_at": r["created_at"], "updated_at": r["updated_at"]}


def list_flows(user_id: str) -> List[Dict[str, Any]]:
    rows = db.query("SELECT * FROM dm_flows WHERE user_id = ? ORDER BY updated_at DESC", (user_id,))
    out = []
    for r in rows:
        f = flow_row(r)
        stats = db.one("SELECT "
                       "SUM(CASE WHEN kind = 'comment' AND verdict IN ('sent','limit','failed') THEN 1 ELSE 0 END) AS triggered, "
                       "SUM(CASE WHEN verdict = 'link_sent' OR (kind = 'comment' AND verdict = 'sent' AND note LIKE 'Link sent%') THEN 1 ELSE 0 END) AS links "
                       "FROM dm_events WHERE flow_id = ?", (f["id"],)) or {}
        f["stats"] = {"triggered": int(stats.get("triggered") or 0), "links": int(stats.get("links") or 0)}
        out.append(f)
    return out


def get_flow(user_id: str, flow_id: str) -> Optional[Dict[str, Any]]:
    r = db.one("SELECT * FROM dm_flows WHERE id = ? AND user_id = ?", (flow_id, user_id))
    return flow_row(r) if r else None


def live_count(user_id: str, exclude: str = "") -> int:
    row = db.one("SELECT COUNT(*) AS n FROM dm_flows WHERE user_id = ? AND status = 'live' AND id <> ?",
                 (user_id, exclude))
    return int((row or {}).get("n") or 0)


def save_flow(user: Dict[str, Any], flow_id: Optional[str], name: str, body: Dict[str, Any],
              go_live: bool) -> Tuple[bool, Any]:
    plan = settings.user_plan(user)
    b = normalise(body)
    errs = validate(b, plan)
    if errs:
        return False, errs
    limit = plan["limits"].get("automations", 1)
    if go_live and limit != -1 and live_count(user["id"], flow_id or "") >= limit:
        return False, [f"Your {plan['name']} plan allows {limit} live automation"
                       f"{'s' if limit != 1 else ''}. Pause another one or upgrade."]
    if go_live and not accounts.get(user["id"]):
        return False, ["Connect Instagram before going live."]
    name = (name or "").strip() or (f"Keyword: {', '.join(b['trigger']['keywords'][:2])}"
                                   if b["trigger"]["mode"] == "keyword" else "Any comment")
    now = db.now()
    status = "live" if go_live else "draft"
    if flow_id and get_flow(user["id"], flow_id):
        db.execute("UPDATE dm_flows SET name = ?, status = ?, body = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                   (name, status, db.jdump(b), now, flow_id, user["id"]))
    else:
        flow_id = db.new_id("f_")
        db.execute("INSERT INTO dm_flows (id, user_id, name, status, body, created_at, updated_at) "
                   "VALUES (?, ?, ?, ?, ?, ?, ?)", (flow_id, user["id"], name, status, db.jdump(b), now, now))
    return True, get_flow(user["id"], flow_id)


def set_status(user: Dict[str, Any], flow_id: str, live: bool) -> Tuple[bool, str]:
    f = get_flow(user["id"], flow_id)
    if not f:
        return False, "Automation not found."
    if live:
        plan = settings.user_plan(user)
        limit = plan["limits"].get("automations", 1)
        if limit != -1 and live_count(user["id"], flow_id) >= limit:
            return False, f"Your {plan['name']} plan allows {limit} live automation{'s' if limit != 1 else ''}."
        if not accounts.get(user["id"]):
            return False, "Connect Instagram first."
        errs = validate(f["body"], plan)
        if errs:
            return False, errs[0]
    db.execute("UPDATE dm_flows SET status = ?, updated_at = ? WHERE id = ? AND user_id = ?",
               ("live" if live else "paused", db.now(), flow_id, user["id"]))
    return True, "live" if live else "paused"


def delete_flow(user_id: str, flow_id: str) -> None:
    db.execute("DELETE FROM dm_flows WHERE id = ? AND user_id = ?", (flow_id, user_id))


# ----------------------------------------------------------------- matching
def keyword_hit(text: str, keywords: List[str]) -> bool:
    t = (text or "").lower()
    for kw in keywords:
        k = kw.lower().strip()
        if not k:
            continue
        if k in ("*", "any", "all"):
            return True
        if re.search(r"(?<!\w)" + re.escape(k) + r"(?!\w)", t) or (not re.match(r"\w", k) and k in t):
            return True
    return False


def pick_flow(user_id: str, media_id: str, text: str) -> Optional[Dict[str, Any]]:
    best, rank = None, 99
    for r in db.query("SELECT * FROM dm_flows WHERE user_id = ? AND status = 'live'", (user_id,)):
        f = flow_row(r)
        b = f["body"]
        specific = b["post"]["mode"] == "specific"
        if specific and b["post"]["media_id"] and media_id and str(b["post"]["media_id"]) != str(media_id):
            continue
        keyed = b["trigger"]["mode"] == "keyword"
        keywords = b["trigger"]["keywords"] or []
        if keyed and "*" not in keywords and not keyword_hit(text, keywords):
            continue
        r_ = (0 if specific else 2) + (0 if keyed else 1)
        if r_ < rank:
            best, rank = f, r_
    return best


def watched_media(user_id: str) -> Tuple[List[str], bool]:
    ids, any_post = [], False
    for r in db.query("SELECT body FROM dm_flows WHERE user_id = ? AND status = 'live'", (user_id,)):
        b = normalise(db.jload(r["body"], {}))
        if b["post"]["mode"] == "any":
            any_post = True
        elif b["post"]["media_id"] and b["post"]["media_id"] not in ids:
            ids.append(str(b["post"]["media_id"]))
    return ids, any_post


# ----------------------------------------------------------------- contacts
def touch_contact(user_id: str, ig_id: str, username: str, flow_id: str, text: str = "",
                  follows: Optional[bool] = None, link_sent: bool = False) -> None:
    key = ig_id or f"u:{(username or '').lower()}"
    if key in ("", "u:"):
        return
    now = db.now()
    db.execute("INSERT INTO dm_contacts (user_id, ig_id, username, flow_id, follows, link_sent, first_seen, last_seen, last_text) "
               "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (user_id, ig_id) DO UPDATE SET "
               "username = CASE WHEN excluded.username <> '' THEN excluded.username ELSE dm_contacts.username END, "
               "flow_id = excluded.flow_id, last_seen = excluded.last_seen, "
               "last_text = CASE WHEN excluded.last_text <> '' THEN excluded.last_text ELSE dm_contacts.last_text END",
               (user_id, key, username or "", flow_id or "", 1 if follows else 0,
                1 if link_sent else 0, now, now, (text or "")[:200]))
    if follows is not None:
        db.execute("UPDATE dm_contacts SET follows = ? WHERE user_id = ? AND ig_id = ?",
                   (1 if follows else 0, user_id, key))
    if link_sent:
        db.execute("UPDATE dm_contacts SET link_sent = 1 WHERE user_id = ? AND ig_id = ?", (user_id, key))


# ------------------------------------------------------------------ comments
def claim(comment_id: str, user_id: str) -> bool:
    """True for exactly one caller per comment, whichever path got here first."""
    if not comment_id:
        return True
    return db.execute("INSERT INTO dm_handled (comment_id, user_id, at) VALUES (?, ?, ?) "
                      "ON CONFLICT (comment_id) DO NOTHING", (str(comment_id), user_id, db.now())) == 1


def handle_comment(acct: Dict[str, Any], c: Dict[str, Any], source: str) -> str:
    """c: id, text, media_id, from_id, username. Returns the verdict."""
    user_id = acct["user_id"]
    if not claim(c.get("id", ""), user_id):
        return "duplicate"
    username, text = c.get("username") or "", c.get("text") or ""

    own = (c.get("from_id") and str(c["from_id"]) in (acct["ig_user_id"], acct["app_user_id"])) or \
          (username and username.lower() == (acct["username"] or "").lower())
    if own:
        log(user_id, "comment", "ignored", source=source, username=username, text=text,
            note="Your own comment. Instagram does not let an account message itself - "
                 "test from a different account.")
        return "ignored"

    flow = pick_flow(user_id, c.get("media_id", ""), text)
    if not flow:
        log(user_id, "comment", "no_flow", source=source, username=username, text=text,
            note="No live automation is watching this post for this comment.")
        return "no_flow"
    b, fid = flow["body"], flow["id"]

    user = db.one("SELECT plan, is_lifetime FROM dm_users WHERE id = ?", (user_id,)) or {}
    plan_obj = settings.user_plan(user)
    limit = plan_obj["limits"].get("dms_per_month", 200)
    if limit != -1 and dms_this_month(user_id) >= limit:
        log(user_id, "comment", "limit", source=source, flow_id=fid, username=username, text=text,
            note=f"Monthly DM limit of {limit} reached. Upgrade to keep replying.")
        return "limit"

    token = acct["token"]
    if b["public_reply"]["on"] and b["public_reply"]["variants"]:
        ok, out = instagram.public_reply(token, c["id"], random.choice(b["public_reply"]["variants"]))
        if not ok:
            log(user_id, "comment", "reply_failed", source=source, flow_id=fid, username=username,
                text=text, note=f"Public reply refused: {out}")

    if b["opening"]["on"]:
        ok, out = instagram.send(token, {"comment_id": c["id"]}, b["opening"]["text"],
                                 [{"title": b["opening"]["button"], "payload": f"LINK:{fid}"}])
        note = "Opening DM sent - waiting for them to tap the button." if ok else f"Opening DM refused: {out}"
    else:
        ok, out = instagram.send(token, {"comment_id": c["id"]}, b["link"]["text"],
                                 [{"title": b["link"]["button"], "url": b["link"]["url"]}])
        note = "Link sent." if ok else f"Link refused: {out}"

    touch_contact(user_id, str(c.get("from_id") or ""), username, fid, text,
                  link_sent=bool(ok and not b["opening"]["on"]))
    verdict = "sent" if ok else "failed"
    log(user_id, "comment", verdict, source=source, flow_id=fid, username=username, text=text, note=note)
    return verdict


# ------------------------------------------------------------------ postbacks
def handle_postback(acct: Dict[str, Any], sender_id: str, payload: str, source: str = "webhook") -> str:
    user_id = acct["user_id"]
    kind, _, fid = (payload or "").partition(":")
    if kind not in ("LINK", "CHECK") or not fid:
        return "ignored"
    flow = get_flow(user_id, fid)
    if not flow:
        log(user_id, "postback", "failed", source=source, note=f"Tap on a deleted automation ({fid}).")
        return "failed"
    b, token = flow["body"], acct["token"]
    contact = db.one("SELECT username FROM dm_contacts WHERE user_id = ? AND ig_id = ?", (user_id, sender_id)) or {}
    who = contact.get("username", "")

    if b["follow_gate"]["on"]:
        following, why = instagram.follows(token, sender_id)
        if following is False:
            text = b["follow_gate"]["text"]
            if kind == "CHECK":
                text = "I can't see the follow yet - it can take a few seconds. " + text
            ok, out = instagram.send(token, {"id": sender_id}, text, [
                {"title": "Open profile", "url": f"https://instagram.com/{acct['username']}"},
                {"title": b["follow_gate"]["button"], "payload": f"CHECK:{fid}"}])
            touch_contact(user_id, sender_id, who, fid, follows=False)
            log(user_id, "postback", "held" if ok else "failed", source=source, flow_id=fid, username=who,
                note="Not following yet - asked them to follow." if ok else f"Follow request refused: {out}")
            return "held" if ok else "failed"
        if following is None:
            note_extra = f" (follow status unreadable: {why} - sent anyway)"
        else:
            note_extra = ""
    else:
        following, note_extra = None, ""

    ok, out = instagram.send(token, {"id": sender_id}, b["link"]["text"],
                             [{"title": b["link"]["button"], "url": b["link"]["url"]}])
    touch_contact(user_id, sender_id, who, fid, follows=following, link_sent=ok)
    log(user_id, "postback", "link_sent" if ok else "failed", source=source, flow_id=fid, username=who,
        note=("Link sent." + note_extra) if ok else f"Link refused: {out}")
    return "link_sent" if ok else "failed"
