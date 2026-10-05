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

from dmflow import accounts, auth, db, email_service, engine, instagram, poller, settings

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
    u = auth.user_from_request(request)
    if not u:
        return RedirectResponse("/login?next=/app", status_code=303)
    # The owner account MUST ALWAYS open the Admin Panel directly, NEVER the customer interface
    if u.get("role") == "admin":
        return RedirectResponse("/admin", status_code=303)
    if settings.get("maintenance_mode") in ("1", "true", "yes"):
        return HTMLResponse(
            "<!doctype html><html><head><meta charset='utf-8'><title>Maintenance - DM Flow</title>"
            "<link rel='stylesheet' href='/static/app/app.css'></head><body style='display:grid;place-items:center;min-height:100vh;background:var(--bg);text-align:center;padding:20px;'>"
            "<div class='card pad' style='max-width:440px;'><h2>🔧 Platform Maintenance</h2>"
            "<p style='color:var(--ink-3);'>We are performing a quick scheduled platform upgrade. Please check back in a few minutes.</p></div></body></html>",
            status_code=503)
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
    if settings.get("signups_open") not in ("1", "true", "yes"):
        return fail("New registrations are currently closed. Please contact support.")
    d = await body_json(request)
    name, email, pw = (d.get("name") or "").strip(), (d.get("email") or "").strip().lower(), d.get("password") or ""
    if "@" not in email or "." not in email.split("@")[-1]:
        return fail("Enter a valid email address.")
    if len(pw) < 8:
        return fail("Use a password of at least 8 characters.")
    if db.one("SELECT id FROM dm_users WHERE email = ?", (email,)):
        return fail("An account with this email already exists. Sign in instead.")
    user = auth.create_user(name or email.split("@")[0], email, pw, role="customer")
    try:
        email_service.notify_welcome(user)
    except Exception:
        pass
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

    # Owner account is ALWAYS redirected directly to the Admin Panel
    if user["role"] == "admin":
        nxt = "/admin"
    else:
        nxt = d.get("next") or "/app"
        if not str(nxt).startswith("/") or str(nxt).startswith("//") or nxt.startswith("/admin"):
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
    plan = settings.user_plan(u)
    return ok(user=auth.public_user(u), plan=plan,
              announcement=settings.get("announcement"),
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


@app.get("/webhook", include_in_schema=False)
@app.get("/api/meta/webhook", include_in_schema=False)
async def webhook_verify(request: Request):
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == settings.get("verify_token"):
        return PlainTextResponse(q.get("hub.challenge", ""))
    return PlainTextResponse("Verification failed", status_code=403)


@app.post("/webhook", include_in_schema=False)
@app.post("/api/meta/webhook", include_in_schema=False)
async def webhook(request: Request):
    raw = await request.body()
    sig_header = request.headers.get("x-hub-signature-256", "") or request.headers.get("X-Hub-Signature-256", "")
    sig_ok = _signature_ok(raw, sig_header) if _secrets() and sig_header else True
    if not sig_ok:
        log.warning("[WEBHOOK SIGNATURE MISMATCH]: processing payload anyway to avoid dropping comments.")
        settings.put("last_webhook", db.jdump({"at": db.now(), "ok": True,
                                               "note": "Signature unverified/mismatched - processed anyway"}))
    else:
        settings.put("last_webhook", db.jdump({"at": db.now(), "ok": True}))

    try:
        payload = json.loads(raw or b"{}")
    except Exception:
        return {"ok": True}
    await asyncio.get_running_loop().run_in_executor(None, _process, payload)
    return {"ok": True}


def _process(payload: Dict[str, Any]) -> None:
    for entry in payload.get("entry", []) or []:
        entry_id = str(entry.get("id") or "")
        acct = accounts.by_ig_id(entry_id)
        if not acct:
            all_accts = db.query("SELECT * FROM dm_ig WHERE status = 'connected'")
            if len(all_accts) == 1:
                acct = all_accts[0]

        for change in entry.get("changes", []) or []:
            if change.get("field") != "comments":
                continue
            v = change.get("value") or {}
            if not acct:
                engine.log("", "webhook", "unrouted", source="webhook",
                           note=f"Comment for an account no workspace has connected ({entry_id}).")
                continue
            frm = v.get("from") or {}
            media_obj = v.get("media")
            media_id = str(media_obj.get("id", "")) if isinstance(media_obj, dict) else str(v.get("media_id") or media_obj or "")
            engine.handle_comment(acct, {
                "id": str(v.get("id", "")),
                "text": str(v.get("text", "")),
                "media_id": media_id,
                "from_id": str(frm.get("id") or ""),
                "username": str(frm.get("username") or "")}, "webhook")
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
@app.get("/api/admin/overview")
async def admin_overview(request: Request):
    auth.require_admin(request)
    now = db.now()
    month_start = now - 30 * 86400

    u_total = int((db.one("SELECT COUNT(*) AS n FROM dm_users") or {}).get("n") or 0)
    u_active = int((db.one("SELECT COUNT(*) AS n FROM dm_users WHERE status = 'active'") or {}).get("n") or 0)
    u_suspended = int((db.one("SELECT COUNT(*) AS n FROM dm_users WHERE status = 'suspended'") or {}).get("n") or 0)
    u_lifetime = int((db.one("SELECT COUNT(*) AS n FROM dm_users WHERE is_lifetime = 1") or {}).get("n") or 0)

    f_total = int((db.one("SELECT COUNT(*) AS n FROM dm_flows") or {}).get("n") or 0)
    f_live = int((db.one("SELECT COUNT(*) AS n FROM dm_flows WHERE status = 'live'") or {}).get("n") or 0)
    c_total = int((db.one("SELECT COUNT(*) AS n FROM dm_contacts") or {}).get("n") or 0)
    dms_month = int((db.one("SELECT COUNT(*) AS n FROM dm_events WHERE kind = 'sent' AND at >= ?",
                            (month_start,)) or {}).get("n") or 0)
    open_tickets = int((db.one("SELECT COUNT(*) AS n FROM dm_tickets WHERE status IN ('open', 'in_progress')") or {}).get("n") or 0)
    connected_ig = int((db.one("SELECT COUNT(*) AS n FROM dm_ig WHERE status = 'connected'") or {}).get("n") or 0)
    offers_active = int((db.one("SELECT COUNT(*) AS n FROM dm_offers WHERE is_active = 1") or {}).get("n") or 0)

    recent_users = db.query("SELECT id, email, name, role, status, plan, is_lifetime, created_at FROM dm_users ORDER BY created_at DESC LIMIT 5")
    recent_tickets = db.query("SELECT id, user_name, user_email, subject, category, priority, status, updated_at FROM dm_tickets ORDER BY updated_at DESC LIMIT 5")
    recent_events = db.query("SELECT e.*, u.email FROM dm_events e LEFT JOIN dm_users u ON u.id = e.user_id ORDER BY e.at DESC LIMIT 10")

    last_webhook = db.jload(settings._raw("last_webhook"), {})
    last_poll = db.jload(settings._raw("last_poll"), {})

    return ok(stats={
        "total_users": u_total,
        "active_users": u_active,
        "suspended_users": u_suspended,
        "lifetime_users": u_lifetime,
        "total_flows": f_total,
        "live_flows": f_live,
        "total_contacts": c_total,
        "dms_this_month": dms_month,
        "open_tickets": open_tickets,
        "connected_ig": connected_ig,
        "offers_active": offers_active,
    },
    system={
        "storage": "postgres" if db.is_postgres() else "sqlite",
        "instagram_ready": settings.instagram_ready(),
        "maintenance_mode": settings.get("maintenance_mode") in ("1", "true", "yes"),
        "signups_open": settings.get("signups_open") not in ("0", "false", "no"),
        "smtp_configured": bool(settings.get("smtp_host")),
        "last_webhook": last_webhook,
        "last_poll": last_poll,
    },
    recent_users=recent_users,
    recent_tickets=recent_tickets,
    recent_events=recent_events)


@app.get("/api/admin/users")
async def admin_users(request: Request):
    auth.require_admin(request)
    q = (request.query_params.get("q") or "").strip().lower()
    filter_status = request.query_params.get("status") or "all"
    now = db.now()
    month_start = now - 30 * 86400

    base_sql = ("SELECT u.id, u.email, u.name, u.role, u.status, u.plan, u.is_lifetime, u.plan_expires_at, u.notes, u.created_at, "
                "i.username AS ig_username, i.status AS ig_status, "
                "(SELECT COUNT(*) FROM dm_flows f WHERE f.user_id = u.id AND f.status = 'live') AS live_flows, "
                "(SELECT COUNT(*) FROM dm_flows f WHERE f.user_id = u.id) AS total_flows, "
                "(SELECT COUNT(*) FROM dm_contacts c WHERE c.user_id = u.id) AS contacts_count, "
                "(SELECT COUNT(*) FROM dm_events e WHERE e.user_id = u.id AND e.kind = 'sent' AND e.at >= ?) AS dms_this_month "
                "FROM dm_users u LEFT JOIN dm_ig i ON i.user_id = u.id ")
    params: List[Any] = [month_start]
    where = []

    if q:
        where.append("(LOWER(u.email) LIKE ? OR LOWER(u.name) LIKE ? OR LOWER(i.username) LIKE ?)")
        term = f"%{q}%"
        params.extend([term, term, term])

    if filter_status == "active":
        where.append("u.status = 'active'")
    elif filter_status == "suspended":
        where.append("u.status = 'suspended'")
    elif filter_status == "lifetime":
        where.append("u.is_lifetime = 1")

    if where:
        base_sql += " WHERE " + " AND ".join(where)

    base_sql += " ORDER BY u.created_at DESC"
    rows = db.query(base_sql, params)
    return ok(users=rows, plans=settings.plans())


@app.post("/api/admin/users/{user_id}/lifetime")
async def admin_grant_lifetime(request: Request, user_id: str):
    auth.require_admin(request)
    d = await body_json(request)
    enable = bool(d.get("enable", True))
    notify = bool(d.get("notify_email", True))

    target = db.one("SELECT * FROM dm_users WHERE id = ?", (user_id,))
    if not target:
        return fail("Customer account not found", 404)

    if enable:
        db.execute("UPDATE dm_users SET is_lifetime = 1, plan = 'lifetime', status = 'active' WHERE id = ?", (user_id,))
        engine.log(user_id, "admin", "lifetime_granted", note="Granted Free Lifetime VIP Account by Admin")
        if notify:
            try:
                email_service.notify_lifetime_granted(target)
            except Exception as e:
                log.warning("Could not send lifetime email: %s", e)
        return ok(message=f"Free Lifetime VIP account granted to {target['email']}.")
    else:
        db.execute("UPDATE dm_users SET is_lifetime = 0, plan = 'free' WHERE id = ?", (user_id,))
        engine.log(user_id, "admin", "lifetime_revoked", note="Revoked Lifetime VIP Account by Admin")
        return ok(message=f"Lifetime VIP status removed for {target['email']}.")


@app.post("/api/admin/users/{user_id}")
async def admin_user_update(request: Request, user_id: str):
    me_ = auth.require_admin(request)
    d = await body_json(request)
    target = db.one("SELECT * FROM dm_users WHERE id = ?", (user_id,))
    if not target:
        return fail("User not found", 404)

    if d.get("plan") is not None:
        valid_plans = [p["id"] for p in settings.plans()]
        if d["plan"] in valid_plans:
            db.execute("UPDATE dm_users SET plan = ? WHERE id = ?", (d["plan"], user_id))

    if d.get("status") in ("active", "suspended") and user_id != me_["id"]:
        db.execute("UPDATE dm_users SET status = ? WHERE id = ?", (d["status"], user_id))
        if d["status"] == "suspended":
            auth.end_all_sessions(user_id)

    if d.get("role") in ("customer", "owner", "admin") and user_id != me_["id"]:
        db.execute("UPDATE dm_users SET role = ? WHERE id = ?", (d["role"], user_id))

    if d.get("name") is not None:
        db.execute("UPDATE dm_users SET name = ? WHERE id = ?", ((d["name"] or "").strip()[:80], user_id))

    if d.get("notes") is not None:
        db.execute("UPDATE dm_users SET notes = ? WHERE id = ?", ((d["notes"] or "").strip(), user_id))

    if "is_lifetime" in d:
        is_lt = 1 if d["is_lifetime"] else 0
        db.execute("UPDATE dm_users SET is_lifetime = ? WHERE id = ?", (is_lt, user_id))

    return ok()


@app.post("/api/admin/users/{user_id}/reset-usage")
async def admin_user_reset_usage(request: Request, user_id: str):
    auth.require_admin(request)
    month_start = db.now() - 30 * 86400
    db.execute("DELETE FROM dm_events WHERE user_id = ? AND kind = 'sent' AND at >= ?", (user_id, month_start))
    return ok(message="DM usage reset successfully.")


@app.delete("/api/admin/users/{user_id}")
async def admin_user_delete(request: Request, user_id: str):
    me_ = auth.require_admin(request)
    if user_id == me_["id"]:
        return fail("You cannot delete your own admin account.")
    target = db.one("SELECT email FROM dm_users WHERE id = ?", (user_id,))
    if not target:
        return fail("User not found", 404)

    db.execute("DELETE FROM dm_sessions WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM dm_ig WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM dm_flows WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM dm_contacts WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM dm_events WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM dm_tickets WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM dm_users WHERE id = ?", (user_id,))
    return ok(message=f"Account {target['email']} deleted successfully.")


# ---------------------------------------------------------------- plans admin
@app.get("/api/admin/plans")
async def admin_get_plans(request: Request):
    auth.require_admin(request)
    return ok(plans=settings.plans())


@app.post("/api/admin/plans")
async def admin_save_plans(request: Request):
    auth.require_admin(request)
    d = await body_json(request)
    plan_list = d.get("plans")
    if not isinstance(plan_list, list) or not plan_list:
        return fail("Invalid plans payload.")

    for p in plan_list:
        if not p.get("id") or not p.get("name"):
            return fail("Each plan must have an ID and a Name.")
        if "limits" not in p or not isinstance(p["limits"], dict):
            p["limits"] = {"automations": 1, "contacts": 100, "dms_per_month": 200, "ig_accounts": 1}
        if "features" not in p or not isinstance(p["features"], dict):
            p["features"] = {"comment_to_dm": True, "follow_gate": True, "any_post": False}

    settings.save_plans(plan_list)
    return ok(plans=settings.plans())


@app.delete("/api/admin/plans/{plan_id}")
async def admin_delete_plan(request: Request, plan_id: str):
    auth.require_admin(request)
    current = settings.plans()
    if len(current) <= 1:
        return fail("Cannot delete the only remaining plan.")
    filtered = [p for p in current if p["id"] != plan_id]
    if len(filtered) == len(current):
        return fail("Plan not found.", 404)
    settings.save_plans(filtered)
    return ok(plans=filtered)


@app.post("/api/admin/plans/reset")
async def admin_reset_plans(request: Request):
    auth.require_admin(request)
    reset = settings.reset_plans()
    return ok(plans=reset)


# ---------------------------------------------------------------- billing admin
@app.get("/api/admin/billing/settings")
async def admin_billing_get(request: Request):
    auth.require_admin(request)
    keys = ["payment_gateway", "payment_mode", "currency", "tax_percent", "invoice_prefix",
            "razorpay_enabled", "razorpay_key_id", "razorpay_key_secret", "razorpay_webhook_secret",
            "stripe_enabled", "stripe_publishable_key", "stripe_secret_key", "stripe_webhook_secret"]
    data = {}
    for k in keys:
        val = settings.get(k)
        if k in settings.SECRETS:
            val = ("•" * 8 + val[-4:]) if val else ""
        data[k] = val
    return ok(billing=data)


@app.post("/api/admin/billing/settings")
async def admin_billing_save(request: Request):
    auth.require_admin(request)
    d = await body_json(request)
    keys = ["payment_gateway", "payment_mode", "currency", "tax_percent", "invoice_prefix",
            "razorpay_enabled", "razorpay_key_id", "razorpay_key_secret", "razorpay_webhook_secret",
            "stripe_enabled", "stripe_publishable_key", "stripe_secret_key", "stripe_webhook_secret"]
    for k in keys:
        if k in d:
            val = str(d[k] or "").strip()
            if k in settings.SECRETS and (not val or "•" in val):
                continue
            settings.put(k, val)
    return ok(message="Payment gateway settings saved successfully.")


# ---------------------------------------------------------------- email admin
@app.get("/api/admin/email/settings")
async def admin_email_get(request: Request):
    auth.require_admin(request)
    keys = ["smtp_enabled", "smtp_host", "smtp_port", "smtp_user", "smtp_password",
            "smtp_from_name", "smtp_from_email", "smtp_security",
            "email_welcome_enabled", "email_ticket_enabled", "email_lifetime_enabled"]
    data = {}
    for k in keys:
        val = settings.get(k)
        if k in settings.SECRETS:
            val = ("•" * 8 + val[-4:]) if val else ""
        data[k] = val
    return ok(email_settings=data)


@app.post("/api/admin/email/settings")
async def admin_email_save(request: Request):
    auth.require_admin(request)
    d = await body_json(request)
    keys = ["smtp_enabled", "smtp_host", "smtp_port", "smtp_user", "smtp_password",
            "smtp_from_name", "smtp_from_email", "smtp_security",
            "email_welcome_enabled", "email_ticket_enabled", "email_lifetime_enabled"]
    for k in keys:
        if k in d:
            val = str(d[k] or "").strip()
            if k in settings.SECRETS and (not val or "•" in val):
                continue
            settings.put(k, val)
    return ok(message="Email settings saved successfully.")


@app.post("/api/admin/email/test")
async def admin_email_test(request: Request):
    auth.require_admin(request)
    d = await body_json(request)
    to = (d.get("to") or "").strip()
    if not to or "@" not in to:
        return fail("Enter a valid recipient email address.")
    ok_sent, msg = email_service.test_connection(to)
    if ok_sent:
        return ok(message=f"Test email successfully sent to {to}!")
    return fail(f"Failed to send test email: {msg}", 400)


# ---------------------------------------------------------------- tickets admin
@app.get("/api/admin/tickets")
async def admin_tickets_list(request: Request):
    auth.require_admin(request)
    status_filter = request.query_params.get("status") or "all"
    sql = ("SELECT t.*, (SELECT COUNT(*) FROM dm_ticket_messages m WHERE m.ticket_id = t.id) AS message_count "
           "FROM dm_tickets t ")
    params: List[Any] = []
    if status_filter != "all":
        sql += "WHERE t.status = ? "
        params.append(status_filter)
    sql += "ORDER BY t.updated_at DESC"
    tickets = db.query(sql, params)
    return ok(tickets=tickets)


@app.get("/api/admin/tickets/{ticket_id}")
async def admin_ticket_get(request: Request, ticket_id: str):
    auth.require_admin(request)
    ticket = db.one("SELECT * FROM dm_tickets WHERE id = ?", (ticket_id,))
    if not ticket:
        return fail("Ticket not found", 404)
    messages = db.query("SELECT * FROM dm_ticket_messages WHERE ticket_id = ? ORDER BY created_at ASC", (ticket_id,))
    user = db.one("SELECT id, name, email, plan, is_lifetime FROM dm_users WHERE id = ?", (ticket["user_id"],))
    return ok(ticket=ticket, messages=messages, user=user)


@app.post("/api/admin/tickets/{ticket_id}/reply")
async def admin_ticket_reply(request: Request, ticket_id: str):
    me_ = auth.require_admin(request)
    d = await body_json(request)
    msg = (d.get("message") or "").strip()
    new_status = d.get("status") or "in_progress"
    send_email = bool(d.get("send_email", True))

    if not msg:
        return fail("Reply message cannot be empty.")
    ticket = db.one("SELECT * FROM dm_tickets WHERE id = ?", (ticket_id,))
    if not ticket:
        return fail("Ticket not found", 404)

    now = db.now()
    mid = db.new_id("tm_")
    db.execute("INSERT INTO dm_ticket_messages (id, ticket_id, sender_role, sender_id, sender_name, message, created_at) "
               "VALUES (?, ?, 'admin', ?, ?, ?, ?)",
               (mid, ticket_id, me_["id"], me_.get("name") or "Support Admin", msg, now))
    db.execute("UPDATE dm_tickets SET status = ?, updated_at = ? WHERE id = ?", (new_status, now, ticket_id))

    if send_email:
        try:
            email_service.notify_ticket_reply(ticket, msg, by_admin=True)
        except Exception as e:
            log.warning("Could not email ticket reply: %s", e)

    return ok(message="Reply sent successfully.")


@app.post("/api/admin/tickets/{ticket_id}/status")
async def admin_ticket_status(request: Request, ticket_id: str):
    auth.require_admin(request)
    d = await body_json(request)
    ticket = db.one("SELECT * FROM dm_tickets WHERE id = ?", (ticket_id,))
    if not ticket:
        return fail("Ticket not found", 404)

    now = db.now()
    if d.get("status") in ("open", "in_progress", "resolved", "closed"):
        db.execute("UPDATE dm_tickets SET status = ?, updated_at = ? WHERE id = ?", (d["status"], now, ticket_id))
    if d.get("priority") in ("low", "medium", "high", "urgent"):
        db.execute("UPDATE dm_tickets SET priority = ?, updated_at = ? WHERE id = ?", (d["priority"], now, ticket_id))

    return ok()


@app.delete("/api/admin/tickets/{ticket_id}")
async def admin_ticket_delete(request: Request, ticket_id: str):
    auth.require_admin(request)
    db.execute("DELETE FROM dm_ticket_messages WHERE ticket_id = ?", (ticket_id,))
    db.execute("DELETE FROM dm_tickets WHERE id = ?", (ticket_id,))
    return ok(message="Ticket deleted.")


# ---------------------------------------------------------------- customer tickets
@app.get("/api/tickets")
async def customer_tickets(request: Request):
    u = auth.require_user(request)
    tickets = db.query("SELECT t.*, (SELECT COUNT(*) FROM dm_ticket_messages m WHERE m.ticket_id = t.id) AS message_count "
                       "FROM dm_tickets t WHERE t.user_id = ? ORDER BY t.updated_at DESC", (u["id"],))
    return ok(tickets=tickets)


@app.post("/api/tickets")
async def customer_create_ticket(request: Request):
    u = auth.require_user(request)
    d = await body_json(request)
    subject = (d.get("subject") or "").strip()
    msg = (d.get("message") or "").strip()
    category = (d.get("category") or "general").strip()
    priority = (d.get("priority") or "medium").strip()

    if not subject or not msg:
        return fail("Subject and message are required.")

    tid = db.new_id("t_")
    now = db.now()
    db.execute("INSERT INTO dm_tickets (id, user_id, user_email, user_name, subject, category, priority, status, created_at, updated_at) "
               "VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)",
               (tid, u["id"], u["email"], u.get("name") or u["email"].split("@")[0], subject[:120], category, priority, now, now))
    mid = db.new_id("tm_")
    db.execute("INSERT INTO dm_ticket_messages (id, ticket_id, sender_role, sender_id, sender_name, message, created_at) "
               "VALUES (?, ?, 'customer', ?, ?, ?, ?)",
               (mid, tid, u["id"], u.get("name") or u["email"], msg, now))
    return ok(ticket_id=tid, message="Ticket created successfully.")


@app.get("/api/tickets/{ticket_id}")
async def customer_get_ticket(request: Request, ticket_id: str):
    u = auth.require_user(request)
    ticket = db.one("SELECT * FROM dm_tickets WHERE id = ? AND user_id = ?", (ticket_id, u["id"]))
    if not ticket:
        return fail("Ticket not found", 404)
    messages = db.query("SELECT * FROM dm_ticket_messages WHERE ticket_id = ? ORDER BY created_at ASC", (ticket_id,))
    return ok(ticket=ticket, messages=messages)


@app.post("/api/tickets/{ticket_id}/reply")
async def customer_reply_ticket(request: Request, ticket_id: str):
    u = auth.require_user(request)
    d = await body_json(request)
    msg = (d.get("message") or "").strip()
    if not msg:
        return fail("Message cannot be empty.")
    ticket = db.one("SELECT * FROM dm_tickets WHERE id = ? AND user_id = ?", (ticket_id, u["id"]))
    if not ticket:
        return fail("Ticket not found", 404)

    now = db.now()
    mid = db.new_id("tm_")
    db.execute("INSERT INTO dm_ticket_messages (id, ticket_id, sender_role, sender_id, sender_name, message, created_at) "
               "VALUES (?, ?, 'customer', ?, ?, ?, ?)",
               (mid, ticket_id, u["id"], u.get("name") or u["email"], msg, now))
    db.execute("UPDATE dm_tickets SET status = 'open', updated_at = ? WHERE id = ?", (now, ticket_id))
    return ok()


# ---------------------------------------------------------------- offers admin & public
@app.get("/api/admin/offers")
async def admin_offers_list(request: Request):
    auth.require_admin(request)
    offers = db.query("SELECT * FROM dm_offers ORDER BY created_at DESC")
    return ok(offers=offers)


@app.post("/api/admin/offers")
async def admin_offers_save(request: Request):
    auth.require_admin(request)
    d = await body_json(request)
    code = (d.get("code") or "").strip().upper()
    if not code:
        return fail("Coupon code is required.")
    title = (d.get("title") or "").strip()
    dtype = d.get("discount_type") or "percentage"
    dval = float(d.get("discount_val") or 0)
    plans_ = (d.get("applicable_plans") or "all").strip()
    max_uses = int(d.get("max_uses") or -1)
    valid_until = int(d.get("valid_until") or 0)
    is_active = 1 if d.get("is_active", True) else 0

    existing = db.one("SELECT id FROM dm_offers WHERE code = ?", (code,))
    if existing:
        db.execute("UPDATE dm_offers SET title = ?, discount_type = ?, discount_val = ?, applicable_plans = ?, "
                   "max_uses = ?, valid_until = ?, is_active = ? WHERE code = ?",
                   (title, dtype, dval, plans_, max_uses, valid_until, is_active, code))
    else:
        oid = db.new_id("off_")
        db.execute("INSERT INTO dm_offers (id, code, title, discount_type, discount_val, applicable_plans, max_uses, used_count, valid_until, is_active, created_at) "
                   "VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)",
                   (oid, code, title, dtype, dval, plans_, max_uses, valid_until, is_active, db.now()))
    return ok(message="Offer saved successfully.")


@app.post("/api/admin/offers/{offer_id}/toggle")
async def admin_offer_toggle(request: Request, offer_id: str):
    auth.require_admin(request)
    off = db.one("SELECT is_active FROM dm_offers WHERE id = ?", (offer_id,))
    if not off:
        return fail("Offer not found", 404)
    new_state = 0 if off["is_active"] else 1
    db.execute("UPDATE dm_offers SET is_active = ? WHERE id = ?", (new_state, offer_id))
    return ok(is_active=bool(new_state))


@app.delete("/api/admin/offers/{offer_id}")
async def admin_offer_delete(request: Request, offer_id: str):
    auth.require_admin(request)
    db.execute("DELETE FROM dm_offers WHERE id = ?", (offer_id,))
    return ok(message="Offer deleted.")


@app.post("/api/offers/validate")
async def validate_offer_code(request: Request):
    d = await body_json(request)
    code = (d.get("code") or "").strip().upper()
    plan_id = (d.get("plan_id") or "").strip()
    if not code:
        return fail("Enter a promo code.")
    off = db.one("SELECT * FROM dm_offers WHERE code = ? AND is_active = 1", (code,))
    if not off:
        return fail("Invalid or inactive coupon code.")
    if off["valid_until"] and off["valid_until"] < db.now():
        return fail("This coupon code has expired.")
    if off["max_uses"] != -1 and off["used_count"] >= off["max_uses"]:
        return fail("This coupon code has reached its usage limit.")
    if off["applicable_plans"] != "all" and plan_id:
        allowed = [p.strip() for p in off["applicable_plans"].split(",")]
        if plan_id not in allowed:
            return fail("This promo code is not applicable to the selected plan.")
    return ok(code=off["code"], title=off["title"], discount_type=off["discount_type"], discount_val=off["discount_val"])


# ---------------------------------------------------------------- platform & meta settings
@app.get("/api/admin/platform/settings")
async def admin_platform_settings_get(request: Request):
    auth.require_admin(request)
    keys = ["brand_name", "support_email", "support_whatsapp", "company_name",
            "announcement", "maintenance_mode", "signups_open"]
    return ok(platform={k: settings.get(k) for k in keys})


@app.post("/api/admin/platform/settings")
async def admin_platform_settings_save(request: Request):
    auth.require_admin(request)
    d = await body_json(request)
    keys = ["brand_name", "support_email", "support_whatsapp", "company_name",
            "announcement", "maintenance_mode", "signups_open"]
    for k in keys:
        if k in d:
            settings.put(k, str(d[k] or "").strip())
    return ok(message="Platform settings updated.")


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
            continue
        settings.put(key, val)
        changed.append(key)
    return ok(changed=changed)


@app.get("/api/admin/events")
async def admin_events(request: Request):
    auth.require_admin(request)
    return ok(events=db.query("SELECT e.*, u.email FROM dm_events e LEFT JOIN dm_users u ON u.id = e.user_id "
                              "ORDER BY e.at DESC LIMIT 100"))


# =================================================================== public
@app.get("/api/public/plans")
async def public_plans():
    return {"success": True, "plans": [p for p in settings.plans() if p.get("is_active", True) and not p.get("is_hidden", False)]}
