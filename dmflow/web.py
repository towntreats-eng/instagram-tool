"""
DM Flow - the web app.

Public URLs that Meta already knows about are kept exactly as they were:
  /api/instagram/callback   OAuth redirect URI
  /api/meta/webhook         webhook callback
  /api/meta/deauthorize     deauthorize callback
  /api/meta/data-deletion   data deletion callback
"""

import asyncio
import base64
import csv
import hashlib
import hmac
import io
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse, PlainTextResponse,
                               RedirectResponse, Response)
from fastapi.staticfiles import StaticFiles

from dmflow import accounts, auth, db, engine, instagram, poller, settings

log = logging.getLogger("dmflow")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")
POLL_ENABLED = (os.environ.get("POLL_ENABLED", "1") or "1").strip() not in ("0", "false", "no")

app = FastAPI(title="DM Flow", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


# ===================================================================== boot
@app.on_event("startup")
async def _startup():
    db.engine()
    imported = settings.import_legacy()
    auth.ensure_admin_from_env()
    log.info("DM Flow up - storage=%s imported=%s", "postgres" if db.is_postgres() else "sqlite", imported)
    if POLL_ENABLED:
        asyncio.create_task(_poll_loop())


async def _poll_loop():
    await asyncio.sleep(10)
    loop = asyncio.get_running_loop()
    while True:
        try:
            stats = await loop.run_in_executor(None, poller.poll_all)
            settings.put("last_poll", db.jdump({"at": db.now(), **stats}))
        except Exception as exc:
            log.error("poll failed: %s", exc)
        await asyncio.sleep(poller.INTERVAL)


def ok(**kw) -> Dict[str, Any]:
    return {"success": True, **kw}


def fail(msg: Any, status: int = 400) -> JSONResponse:
    return JSONResponse({"success": False, "error": msg if isinstance(msg, str) else "; ".join(msg),
                         "errors": msg if isinstance(msg, list) else [msg]}, status_code=status)


def page(name: str) -> FileResponse:
    return FileResponse(os.path.join(STATIC, name), headers={"Cache-Control": "no-cache"})


async def body_json(request: Request) -> Dict[str, Any]:
    try:
        data = await request.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


# ==================================================================== pages
@app.get("/", include_in_schema=False)
async def landing():
    return page("landing.html")


def _static_page(fname: str):
    # A closure with no parameters. A default argument here would become a
    # query parameter, and ?f=../web.py would serve the source code.
    async def handler():
        return page(fname)
    return handler


for _path, _file in (("/pricing", "pricing.html"), ("/privacy", "privacy.html"),
                     ("/terms", "terms.html"), ("/deletion", "deletion.html"),
                     ("/login", "login.html"), ("/signup", "signup.html")):
    app.add_api_route(_path, _static_page(_file), methods=["GET"], include_in_schema=False)


@app.get("/app", include_in_schema=False)
@app.get("/app/{rest:path}", include_in_schema=False)
async def panel(request: Request, rest: str = ""):
    if not auth.user_from_request(request):
        return RedirectResponse("/login?next=/app", status_code=303)
    return page("app.html")


@app.get("/admin", include_in_schema=False)
async def admin_page(request: Request):
    u = auth.user_from_request(request)
    if not u:
        return RedirectResponse("/login?next=/admin", status_code=303)
    if u.get("role") != "admin":
        return RedirectResponse("/app", status_code=303)
    return page("admin.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return page("favicon.ico")


@app.get("/healthz", include_in_schema=False)
async def healthz():
    return {"ok": True}


# ===================================================================== auth
_attempts: Dict[str, List[float]] = {}


def _throttled(key: str, limit: int = 8, window: int = 600) -> bool:
    now = time.time()
    hits = [t for t in _attempts.get(key, []) if now - t < window]
    _attempts[key] = hits
    return len(hits) >= limit


def _note_attempt(key: str) -> None:
    _attempts.setdefault(key, []).append(time.time())


@app.post("/api/auth/signup")
async def signup(request: Request):
    d = await body_json(request)
    name, email, pw = (d.get("name") or "").strip(), (d.get("email") or "").strip().lower(), d.get("password") or ""
    if "@" not in email or "." not in email.split("@")[-1]:
        return fail("Enter a valid email address.")
    if len(pw) < 8:
        return fail("Use a password of at least 8 characters.")
    if db.one("SELECT id FROM dm_users WHERE email = ?", (email,)):
        return fail("An account with this email already exists. Sign in instead.")
    user = auth.create_user(name or email.split("@")[0], email, pw)
    resp = JSONResponse(ok(redirect="/app"))
    auth.set_cookie(resp, auth.start_session(user["id"]))
    return resp


@app.post("/api/auth/login")
async def login(request: Request):
    d = await body_json(request)
    email, pw = (d.get("email") or "").strip().lower(), d.get("password") or ""
    key = f"{request.client.host if request.client else ''}:{email}"
    if _throttled(key):
        return fail("Too many attempts. Wait ten minutes and try again.", 429)
    user = db.one("SELECT * FROM dm_users WHERE email = ?", (email,))
    good, rehash = auth.verify_password(pw, user["password_hash"]) if user else (False, False)
    if not good:
        _note_attempt(key)
        return fail("Email or password is incorrect.", 401)
    if user["status"] == "suspended":
        return fail("This account is suspended. Contact support.", 403)
    if rehash:
        db.execute("UPDATE dm_users SET password_hash = ? WHERE id = ?", (auth.hash_password(pw), user["id"]))
    nxt = d.get("next") or ("/admin" if user["role"] == "admin" and d.get("prefer_admin") else "/app")
    if not str(nxt).startswith("/") or str(nxt).startswith("//"):
        nxt = "/app"
    resp = JSONResponse(ok(redirect=nxt))
    auth.set_cookie(resp, auth.start_session(user["id"]))
    return resp


@app.post("/api/auth/logout")
async def logout(request: Request):
    auth.end_session(request.cookies.get(auth.COOKIE))
    resp = JSONResponse(ok(redirect="/login"))
    auth.clear_cookie(resp)
    return resp


@app.get("/api/me")
async def me(request: Request):
    u = auth.require_user(request)
    plan = settings.plan(u["plan"])
    return ok(user=auth.public_user(u), plan=plan,
              usage={"dms": engine.dms_this_month(u["id"]),
                     "live": engine.live_count(u["id"]),
                     "contacts": int((db.one("SELECT COUNT(*) AS n FROM dm_contacts WHERE user_id = ?",
                                             (u["id"],)) or {}).get("n") or 0)},
              instagram=accounts.status(u["id"]),
              instagram_ready=settings.instagram_ready())


@app.post("/api/me")
async def update_me(request: Request):
    u = auth.require_user(request)
    d = await body_json(request)
    if d.get("name") is not None:
        db.execute("UPDATE dm_users SET name = ? WHERE id = ?", ((d["name"] or "").strip()[:80], u["id"]))
    if d.get("new_password"):
        good, _ = auth.verify_password(d.get("current_password") or "", u["password_hash"])
        if not good:
            return fail("Your current password is incorrect.")
        if len(d["new_password"]) < 8:
            return fail("Use a new password of at least 8 characters.")
        db.execute("UPDATE dm_users SET password_hash = ? WHERE id = ?",
                   (auth.hash_password(d["new_password"]), u["id"]))
        auth.end_all_sessions(u["id"])
        resp = JSONResponse(ok(message="Password changed. Sign in again.", redirect="/login"))
        auth.clear_cookie(resp)
        return resp
    return ok()


# ================================================================ instagram
@app.get("/connect/instagram", include_in_schema=False)
async def connect_instagram(request: Request):
    u = auth.user_from_request(request)
    if not u:
        return RedirectResponse("/login?next=/app", status_code=303)
    if not settings.instagram_ready():
        return _message_page("Instagram is not set up yet",
                             "The administrator has not added the Instagram app credentials. "
                             "Admin > Instagram app.", False)
    base = settings.base_url(request)
    return RedirectResponse(instagram.authorize_url(accounts.redirect_uri(base),
                                                    accounts.make_state(u["id"])), status_code=303)


@app.get("/api/instagram/callback", include_in_schema=False)
async def instagram_callback(request: Request, code: str = "", state: str = "",
                             error: str = "", error_description: str = ""):
    if error:
        return _message_page("Connection cancelled",
                             error_description or "Nothing was changed.", False)
    if not code or not state:
        return _message_page("Something went wrong", "Instagram did not send an authorisation code.", False)
    base = settings.base_url(request)
    good, out = await asyncio.get_running_loop().run_in_executor(
        None, accounts.complete, code, state, base)
    if not good:
        detail = str(out)
        if "verification code" in detail.lower() or "redirect_uri" in detail.lower():
            detail += (f"<br><br><b>Redirect URI sent:</b> <code>{accounts.redirect_uri(base)}</code><br>"
                       "It must match Meta's list exactly. If it does, the code was used twice - "
                       "start again from the dashboard instead of reloading this page.")
        return _message_page("Could not connect", detail, False)
    return RedirectResponse("/app?connected=1", status_code=303)


def _message_page(title: str, message: str, good: bool) -> HTMLResponse:
    colour = "#0fbf73" if good else "#e5484d"
    return HTMLResponse(f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} - DM Flow</title>
<link rel="icon" href="/static/favicon.ico"><link rel="stylesheet" href="/static/app/app.css"></head>
<body class="msg-page"><div class="msg-box"><div class="msg-ring" style="--c:{colour}"></div>
<h1>{title}</h1><p>{message}</p><a class="btn btn-primary" href="/app">Back to dashboard</a></div></body></html>""")


@app.get("/api/instagram")
async def instagram_status(request: Request, refresh: int = 0):
    u = auth.require_user(request)
    return ok(instagram=await asyncio.get_running_loop().run_in_executor(
        None, accounts.status, u["id"], bool(refresh)))


@app.post("/api/instagram/disconnect")
async def instagram_disconnect(request: Request):
    u = auth.require_user(request)
    report = await asyncio.get_running_loop().run_in_executor(None, accounts.disconnect, u["id"])
    return ok(report=report)


@app.get("/api/instagram/media")
async def instagram_media(request: Request):
    u = auth.require_user(request)
    acct = accounts.get(u["id"])
    if not acct or acct["status"] != "connected":
        return fail("Connect Instagram first.", 409)
    good, out = await asyncio.get_running_loop().run_in_executor(None, instagram.media, acct["token"], 30)
    return ok(media=out) if good else fail(f"Instagram would not list your posts: {out}", 502)


# ==================================================================== flows
@app.get("/api/flows")
async def flows_list(request: Request):
    u = auth.require_user(request)
    return ok(flows=engine.list_flows(u["id"]), template=engine.TEMPLATE)


@app.get("/api/flows/{flow_id}")
async def flows_get(request: Request, flow_id: str):
    u = auth.require_user(request)
    f = engine.get_flow(u["id"], flow_id)
    return ok(flow=f) if f else fail("Automation not found.", 404)


@app.post("/api/flows")
@app.put("/api/flows/{flow_id}")
async def flows_save(request: Request, flow_id: Optional[str] = None):
    u = auth.require_user(request)
    d = await body_json(request)
    good, out = engine.save_flow(u, flow_id, d.get("name", ""), d.get("body") or {}, bool(d.get("live")))
    return ok(flow=out) if good else fail(out)


@app.post("/api/flows/{flow_id}/status")
async def flows_status(request: Request, flow_id: str):
    u = auth.require_user(request)
    d = await body_json(request)
    good, out = engine.set_status(u, flow_id, bool(d.get("live")))
    return ok(status=out) if good else fail(out)


@app.delete("/api/flows/{flow_id}")
async def flows_delete(request: Request, flow_id: str):
    u = auth.require_user(request)
    engine.delete_flow(u["id"], flow_id)
    return ok()


# ========================================================= contacts, activity
@app.get("/api/contacts")
async def contacts(request: Request):
    u = auth.require_user(request)
    rows = db.query("SELECT c.*, f.name AS flow_name FROM dm_contacts c LEFT JOIN dm_flows f ON f.id = c.flow_id "
                    "WHERE c.user_id = ? ORDER BY c.last_seen DESC LIMIT 1000", (u["id"],))
    return ok(contacts=rows)


@app.get("/api/contacts.csv")
async def contacts_csv(request: Request):
    u = auth.require_user(request)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["username", "automation", "follows", "link_sent", "first_seen", "last_seen", "last_comment"])
    for r in db.query("SELECT c.*, f.name AS flow_name FROM dm_contacts c LEFT JOIN dm_flows f ON f.id = c.flow_id "
                      "WHERE c.user_id = ? ORDER BY c.last_seen DESC", (u["id"],)):
        w.writerow([r["username"], r.get("flow_name") or "", "yes" if r["follows"] else "",
                    "yes" if r["link_sent"] else "", time.strftime("%Y-%m-%d %H:%M", time.gmtime(r["first_seen"])),
                    time.strftime("%Y-%m-%d %H:%M", time.gmtime(r["last_seen"])), r["last_text"]])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=dmflow-contacts.csv"})


@app.get("/api/activity")
async def activity(request: Request):
    u = auth.require_user(request)
    last_hook = db.jload(settings._raw("last_webhook"), {}) or {}
    return ok(events=engine.events(u["id"], 40),
              health={"webhook_last_at": last_hook.get("at"),
                      "webhook_last_ok": last_hook.get("ok"),
                      "poll": db.jload(settings._raw("last_poll"), {}) or {}})


@app.post("/api/poll-now")
async def poll_now(request: Request):
    u = auth.require_user(request)
    acct = accounts.get(u["id"])
    if not acct or acct["status"] != "connected":
        return fail("Connect Instagram first.", 409)
    stats = await asyncio.get_running_loop().run_in_executor(None, poller.poll_account, acct)
    return ok(stats=stats)


# ================================================================== webhook
def _secrets() -> List[str]:
    out = []
    for key in ("meta_app_secret", "ig_app_secret"):
        v = settings.get(key)
        if v and v not in out:
            out.append(v)
    return out


def _signature_ok(raw: bytes, header: str) -> bool:
    sent = (header or "").split("=", 1)[-1].strip()
    if not sent:
        return False
    return any(hmac.compare_digest(sent, hmac.new(s.encode(), raw, hashlib.sha256).hexdigest())
               for s in _secrets())


@app.get("/api/meta/webhook", include_in_schema=False)
async def webhook_verify(request: Request):
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == settings.get("verify_token"):
        return PlainTextResponse(q.get("hub.challenge", ""))
    return PlainTextResponse("Verification failed", status_code=403)


@app.post("/api/meta/webhook", include_in_schema=False)
async def webhook(request: Request):
    raw = await request.body()
    if not _secrets():
        settings.put("last_webhook", db.jdump({"at": db.now(), "ok": False,
                                               "note": "No app secret set - delivery refused."}))
        return PlainTextResponse("not configured", status_code=503)
    if not _signature_ok(raw, request.headers.get("x-hub-signature-256", "")):
        settings.put("last_webhook", db.jdump({"at": db.now(), "ok": False,
                                               "note": "Signature did not match. Set the Meta App Secret "
                                                       "(App settings > Basic) in Admin."}))
        engine.log("", "webhook", "rejected", source="webhook", note="Bad signature")
        return PlainTextResponse("bad signature", status_code=403)
    settings.put("last_webhook", db.jdump({"at": db.now(), "ok": True}))
    try:
        payload = json.loads(raw or b"{}")
    except Exception:
        return {"ok": True}
    await asyncio.get_running_loop().run_in_executor(None, _process, payload)
    return {"ok": True}


def _process(payload: Dict[str, Any]) -> None:
    for entry in payload.get("entry", []) or []:
        acct = accounts.by_ig_id(str(entry.get("id") or ""))
        for change in entry.get("changes", []) or []:
            if change.get("field") != "comments":
                continue
            v = change.get("value") or {}
            if not acct:
                engine.log("", "webhook", "unrouted", source="webhook",
                           note=f"Comment for an account no workspace has connected ({entry.get('id')}).")
                continue
            frm = v.get("from") or {}
            engine.handle_comment(acct, {"id": v.get("id", ""), "text": v.get("text", ""),
                                         "media_id": (v.get("media") or {}).get("id", ""),
                                         "from_id": str(frm.get("id") or ""),
                                         "username": frm.get("username", "")}, "webhook")
        for m in entry.get("messaging", []) or []:
            a = acct or accounts.by_ig_id(str((m.get("recipient") or {}).get("id") or ""))
            if not a:
                continue
            sender = str((m.get("sender") or {}).get("id") or "")
            msg = m.get("message") or {}
            if msg.get("is_echo") or not sender:
                continue
            payload_ = (m.get("postback") or {}).get("payload") or (msg.get("quick_reply") or {}).get("payload")
            if payload_:
                engine.handle_postback(a, sender, payload_)


# ======================================================= Meta legal callbacks
def _b64(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def _signed_request(sr: str) -> Optional[Dict[str, Any]]:
    try:
        sig, body = (sr or "").split(".", 1)
        payload = json.loads(_b64(body))
    except Exception:
        return None
    if (payload.get("algorithm") or "").upper() != "HMAC-SHA256":
        return None
    for s in _secrets():
        if hmac.compare_digest(_b64(sig), hmac.new(s.encode(), body.encode(), hashlib.sha256).digest()):
            return payload
    return None


async def _sr_from(request: Request) -> str:
    try:
        form = await request.form()
        if form.get("signed_request"):
            return str(form["signed_request"])
    except Exception:
        pass
    return str((await body_json(request)).get("signed_request") or "")


@app.post("/api/meta/deauthorize", include_in_schema=False)
async def deauthorize(request: Request):
    p = _signed_request(await _sr_from(request))
    if not p:
        return fail("Invalid signed_request.")
    acct = accounts.by_ig_id(str(p.get("user_id") or ""))
    if acct:
        accounts.forget(acct["user_id"])
        engine.log(acct["user_id"], "account", "deauthorized", username=acct["username"],
                   note="Removed DM Flow from Instagram settings - disconnected.")
    return ok()


@app.post("/api/meta/data-deletion", include_in_schema=False)
async def data_deletion(request: Request):
    p = _signed_request(await _sr_from(request))
    if not p:
        return fail("Invalid signed_request.")
    meta_uid = str(p.get("user_id") or "")
    code = hashlib.sha256(f"{meta_uid}:{time.strftime('%Y%m%d')}".encode()).hexdigest()[:16]
    removed = {"connection": False, "contacts": 0, "events": 0}
    acct = accounts.by_ig_id(meta_uid)
    if acct:
        uid = acct["user_id"]
        removed["contacts"] = db.execute("DELETE FROM dm_contacts WHERE user_id = ?", (uid,))
        removed["events"] = db.execute("DELETE FROM dm_events WHERE user_id = ?", (uid,))
        accounts.forget(uid)
        removed["connection"] = True
    settings.put(f"deletion:{code}", db.jdump({"at": db.now(), "removed": removed}))
    return {"url": f"{settings.base_url(request)}/deletion?code={code}", "confirmation_code": code}


@app.get("/api/deletion-status")
async def deletion_status(code: str = ""):
    row = db.jload(settings._raw(f"deletion:{(code or '').strip()}"), None)
    if not row:
        return {"success": False, "error": "No deletion request matches that code."}
    return {"success": True, "code": code, "status": "completed", **row}


# ==================================================================== admin
@app.get("/api/admin/settings")
async def admin_settings(request: Request):
    auth.require_admin(request)
    base = settings.base_url(request)
    return ok(settings=settings.public_view(),
              urls={"redirect_uri": accounts.redirect_uri(base),
                    "webhook": f"{base}/api/meta/webhook",
                    "deauthorize": f"{base}/api/meta/deauthorize",
                    "data_deletion": f"{base}/api/meta/data-deletion"},
              last_webhook=db.jload(settings._raw("last_webhook"), {}),
              last_poll=db.jload(settings._raw("last_poll"), {}))


@app.post("/api/admin/settings")
async def admin_settings_save(request: Request):
    auth.require_admin(request)
    d = await body_json(request)
    changed = []
    for key in settings.DEFAULTS:
        if key not in d:
            continue
        val = str(d[key] or "").strip()
        if key in settings.SECRETS and (not val or "•" in val):
            continue  # masked or blank: keep the stored secret
        settings.put(key, val)
        changed.append(key)
    return ok(changed=changed)


@app.get("/api/admin/users")
async def admin_users(request: Request):
    auth.require_admin(request)
    rows = db.query("SELECT u.id, u.email, u.name, u.role, u.status, u.plan, u.created_at, "
                    "i.username AS ig_username, i.status AS ig_status, "
                    "(SELECT COUNT(*) FROM dm_flows f WHERE f.user_id = u.id AND f.status = 'live') AS live_flows "
                    "FROM dm_users u LEFT JOIN dm_ig i ON i.user_id = u.id ORDER BY u.created_at DESC")
    return ok(users=rows, plans=settings.plans())


@app.post("/api/admin/users/{user_id}")
async def admin_user_update(request: Request, user_id: str):
    me_ = auth.require_admin(request)
    d = await body_json(request)
    if d.get("plan") in [p["id"] for p in settings.plans()]:
        db.execute("UPDATE dm_users SET plan = ? WHERE id = ?", (d["plan"], user_id))
    if d.get("status") in ("active", "suspended") and user_id != me_["id"]:
        db.execute("UPDATE dm_users SET status = ? WHERE id = ?", (d["status"], user_id))
        if d["status"] == "suspended":
            auth.end_all_sessions(user_id)
    if d.get("role") in ("owner", "admin") and user_id != me_["id"]:
        db.execute("UPDATE dm_users SET role = ? WHERE id = ?", (d["role"], user_id))
    return ok()


@app.get("/api/admin/events")
async def admin_events(request: Request):
    auth.require_admin(request)
    return ok(events=db.query("SELECT e.*, u.email FROM dm_events e LEFT JOIN dm_users u ON u.id = e.user_id "
                              "ORDER BY e.at DESC LIMIT 100"))


# =================================================================== public
@app.get("/api/public/plans")
async def public_plans():
    return {"success": True, "plans": settings.plans()}
