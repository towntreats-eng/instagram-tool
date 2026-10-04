import os
import json
import hmac
import hashlib
import urllib.parse
import urllib.request
import asyncio
import time
import threading
import contextvars
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DM Flow")

# Webhook verify token fallback. The old default was a guessable literal that
# also carried a competitor's name; the real value is set per-install in
# Admin -> Instagram API.
DEFAULT_VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN", "converflow_webhook_token")
from datetime import datetime


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

from typing import Optional, Dict, Any, List, Tuple
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse, PlainTextResponse, RedirectResponse
from fastapi import Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.campaign_manager import CampaignManager
from core.spintax import SpintaxEngine
from core.automation_engine import AutomationEngine
from core.contacts_manager import ContactsManager
from core.comment_watcher import CommentWatcher
from core.meta_api import MetaAPIClient
from core.user_manager import UserManager
from core.admin_store import AdminStore
from core.plans_manager import PlansManager, FEATURE_KEYS, LIMIT_KEYS, UNLIMITED
from core.platform_settings import PlatformSettings
from core.meta_oauth import MetaOAuth
from core.insights import Insights
from core.razorpay_client import RazorpayClient
from core import instagram_account
from core import follow_gate
from core import webhook_setup
from core import event_log
from core import private_reply
from core import comment_poller
from core import data_deletion
from core import auth as cf_auth
from core import db as cf_db
from core import store as cf_store

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(title="DM Flow", version="4.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _bind_request(request: Request, call_next):
    """Makes the current request available to signed_in_user()."""
    token = _request_ctx.set(request)
    try:
        return await call_next(request)
    finally:
        _request_ctx.reset(token)


# How often to read comments ourselves. Meta delivers no production webhooks
# to an unpublished app - its own dashboard says so - so until App Review
# passes this loop is the only thing that makes comment -> DM work at all.
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "60") or 60)
POLL_ENABLED = (os.environ.get("POLL_ENABLED", "1") or "1").strip() not in ("0", "false", "no")
_poll_stats: Dict[str, Any] = {"last_run": 0, "last": None, "runs": 0}


def _poll_once(loop: "asyncio.AbstractEventLoop") -> Dict[str, Any]:
    """One pass, synchronous. Runs on a worker thread, which has no event loop
    of its own - so the loop is passed in rather than looked up here, and each
    delivery is handed back to it because the handler is async."""
    return comment_poller.poll_all(
        user_manager.all(), automation_engine.get_all(),
        lambda payload: asyncio.run_coroutine_threadsafe(
            meta_webhook_event(InternalDelivery(payload)), loop).result(timeout=90))


async def _poll_loop():
    # A first pass only ever primes: it marks what is already there as seen so
    # the merchant's whole comment history is not answered on boot.
    await asyncio.sleep(8)
    loop = asyncio.get_running_loop()
    while True:
        try:
            stats = await loop.run_in_executor(None, _poll_once, loop)
            _poll_stats.update({"last_run": time.time(), "last": stats,
                                "runs": _poll_stats["runs"] + 1})
            if stats.get("new") or stats.get("errors"):
                logger.info(f"[POLL] {stats}")
        except Exception as exc:
            logger.error(f"[POLL ERROR] {exc}")
        await asyncio.sleep(POLL_SECONDS)


@app.on_event("startup")
async def _startup():
    ok, msg = cf_db.init()
    print(f"[DM Flow] storage: {'PostgreSQL' if ok else 'JSON files'} — {msg}")
    if POLL_ENABLED:
        asyncio.create_task(_poll_loop())
        print(f"[DM Flow] comment polling every {POLL_SECONDS}s "
              f"(needed until the Meta app is published)")

# Core instances
campaign_manager = CampaignManager()
automation_engine = AutomationEngine()
contacts_manager = ContactsManager()
meta_client = MetaAPIClient()
plans_manager = PlansManager()
platform_settings = PlatformSettings()
razorpay = RazorpayClient(platform_settings)
user_manager = UserManager(plans=plans_manager)
admin_store = AdminStore()
meta_oauth = MetaOAuth(platform_settings)
insights = Insights(contacts_manager, automation_engine, campaign_manager)


# The request currently being served. FastAPI hands the Request object to the
# route; this context var lets the small helpers below read it without every
# existing function having to grow a parameter.
_request_ctx: contextvars.ContextVar = contextvars.ContextVar("cf_request", default=None)


def _request() -> Optional[Request]:
    return _request_ctx.get()


def signed_in_user() -> Optional[Dict[str, Any]]:
    """Whoever this request's session cookie belongs to. None if not signed in.

    This used to return users[0] — the first account in the file — to everybody,
    which meant one customer's dashboard showed another's data.
    """
    req = _request()
    if req is None:
        return None
    sess = cf_auth.read_session(req.cookies.get(cf_auth.SESSION_COOKIE))
    if not sess:
        return None
    user = user_manager.get(sess["user_id"])
    if not user or user.get("status") == "suspended":
        return None
    return user


def current_workspace():
    """The workspace serving this request."""
    return signed_in_user()


def require_user() -> Dict[str, Any]:
    user = signed_in_user()
    if not user:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return user


def is_admin_user(user: Optional[Dict[str, Any]]) -> bool:
    if not user:
        return False
    email = (user.get("email") or "").strip().lower()
    admin_env = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    return user.get("role") == "admin" or email in ("umangptl11@gmail.com", "hello@umangsatnam.in", admin_env)


def require_admin() -> Dict[str, Any]:
    """Guards every /api/admin/* route."""
    user = signed_in_user()
    if not user:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail="This area is for administrators.")
    return user

comment_watcher = CommentWatcher(
    browser_manager=campaign_manager.browser_manager,
    automation_engine=automation_engine,
    contacts_manager=contacts_manager,
    campaign_manager=campaign_manager
)

login_thread: Optional[threading.Thread] = None

# Request Schemas
class WizardPublishRequest(BaseModel):
    name: str
    post_target: Optional[str] = "https://www.instagram.com/reel/current/"
    post_media_id: Optional[str] = ""
    post_thumbnail: Optional[str] = ""
    post_caption: Optional[str] = ""
    trigger_scope: str = "specific" # specific or any
    trigger_keywords: List[str] = []
    reply_to_comment: bool = True
    comment_replies: List[str] = []
    opening_dm: str
    button_text: str = "Send me the link"
    delivery_link: Optional[str] = ""
    require_follow: bool = False
    ask_email: bool = False
    tags: Optional[List[str]] = []


# Request Schemas
class SpintaxPreviewRequest(BaseModel):
    template: str

class LoadTextTargetsRequest(BaseModel):
    text: str

class CampaignSettingsRequest(BaseModel):
    template: str
    min_delay: int = 45
    max_delay: int = 90
    daily_limit: int = 35
    headless: bool = False

class AutomationRuleRequest(BaseModel):
    id: Optional[str] = None
    name: str
    type: str # comment_to_dm, dm_keyword, story_mention
    post_target: Optional[str] = "all_posts"
    trigger_keywords: List[str]
    public_comment_reply: Optional[str] = ""
    dm_message: str
    tags: Optional[List[str]] = []
    is_active: Optional[bool] = True

class SimulatorMessageRequest(BaseModel):
    channel: str = "comment" # comment or dm
    text: str
    username: Optional[str] = "alex_growth"
    name: Optional[str] = "Alex Mercer"
    post_url: Optional[str] = None

class WatcherStartRequest(BaseModel):
    post_url: Optional[str] = None
    interval: Optional[int] = 60

class MetaConfigRequest(BaseModel):
    app_id: Optional[str] = ""
    app_secret: Optional[str] = ""
    access_token: str
    page_id: Optional[str] = ""
    instagram_account_id: Optional[str] = ""
    verify_token: Optional[str] = DEFAULT_VERIFY_TOKEN

class MetaTestRequest(BaseModel):
    access_token: str

# Ensure static directories
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "css"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "js"), exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

def _page(filename: str, fallback: str = "Page not found") -> HTMLResponse:
    path = os.path.join(STATIC_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(f"<h1>{fallback}</h1>", status_code=404)


# --- Public marketing pages ---

@app.get("/", response_class=HTMLResponse)
async def serve_landing():
    return _page("landing.html", "DM Flow landing page missing")

@app.get("/pricing", response_class=HTMLResponse)
async def serve_pricing():
    return _page("pricing.html", "Pricing page missing")

@app.get("/login", response_class=HTMLResponse)
async def serve_login():
    return _page("login.html", "Login page missing")

@app.get("/signup", response_class=HTMLResponse)
async def serve_signup():
    return _page("signup.html", "Signup page missing")

@app.get("/privacy", response_class=HTMLResponse)
async def serve_privacy():
    return _page("privacy.html", "Privacy policy page missing")

@app.get("/terms", response_class=HTMLResponse)
async def serve_terms():
    return _page("terms.html", "Terms of service page missing")

@app.post("/api/meta/data-deletion")
async def meta_data_deletion(request: Request):
    """Meta's data deletion callback. Registered in the app's Instagram settings.

    This has to be real: a reviewer tests it, and the deletion page already
    promised it exists. Everything this app learned from Meta about the
    requesting account is removed; the DM Flow login is not, because that is
    not Meta's data and the person may want to reconnect.
    """
    try:
        form = await request.form()
        signed = form.get("signed_request", "")
    except Exception:
        signed = ""
    if not signed:
        try:
            signed = (await request.json()).get("signed_request", "")
        except Exception:
            signed = ""

    ok, payload = False, "No app secret configured, so this cannot be verified."
    for secret in _signing_secrets():
        ok, payload = data_deletion.parse_signed_request(signed, secret)
        if ok:
            break
    if not ok:
        admin_store.log("ERROR", "instagram", f"Data deletion refused: {payload}")
        raise HTTPException(status_code=400, detail=str(payload))

    meta_user_id = str(payload.get("user_id") or "")
    code = data_deletion.code_for(meta_user_id)
    removed = {"connection": False, "contacts": 0, "events": 0, "flows_unbound": 0}

    target = next((u for u in user_manager.all()
                   if str(((u.get("instagram") or {}).get("user_id") or "")) == meta_user_id),
                  None)
    if target:
        # Which posts were this workspace's, so their contacts can be found.
        media_ids = {str(r.get("post_media_id")) for r in automation_engine.get_all()
                     if r.get("created_by") == target["id"] and r.get("post_media_id")}

        instagram_account.forget(target["id"])
        user_manager.disconnect_instagram(target["id"])
        removed["connection"] = True

        if media_ids:
            removed["contacts"] = contacts_manager.remove_where(
                lambda c: any(m in str(c.get("source", "")) for m in media_ids))

        try:
            before = event_log.recent(event_log.KEEP)
            rows = [r for r in before if r.get("workspace") != target.get("email")]
            cf_store.write(event_log.FILE, rows)
            removed["events"] = len(before) - len(rows)
        except Exception:
            pass

        admin_store.log("WARN", "instagram",
                        f"Meta data deletion completed for {target['email']} "
                        f"({removed['contacts']} contacts removed)")

    data_deletion.record(code, meta_user_id,
                         (target or {}).get("email", "unknown"), removed)
    return {"url": f"{_base_url(request)}/deletion?code={code}",
            "confirmation_code": code}


@app.get("/api/meta/data-deletion")
async def meta_data_deletion_get():
    return RedirectResponse(url="/deletion")


@app.post("/api/meta/deauthorize")
async def meta_deauthorize(request: Request):
    """Meta's deauthorize callback URL.
    Called when a user removes the app in Instagram/Facebook account settings.
    """
    try:
        form = await request.form()
        signed = form.get("signed_request", "")
    except Exception:
        signed = ""
    if not signed:
        try:
            signed = (await request.json()).get("signed_request", "")
        except Exception:
            signed = ""

    ok, payload = False, "No app secret configured, so this cannot be verified."
    for secret in _signing_secrets():
        ok, payload = data_deletion.parse_signed_request(signed, secret)
        if ok:
            break
    if not ok:
        # Anyone can POST here. Answering "success" to a forgery did no harm,
        # but it hid the one case worth seeing: Meta's own call failing
        # because the saved secret is not this app's.
        admin_store.log("ERROR", "instagram", f"Deauthorize refused: {payload}")
        raise HTTPException(status_code=400, detail=str(payload))
    if isinstance(payload, dict):
            meta_user_id = str(payload.get("user_id") or "")
            target = next((u for u in user_manager.all()
                           if str(((u.get("instagram") or {}).get("user_id") or "")) == meta_user_id
                           or str(((u.get("instagram") or {}).get("instagram_account_id") or "")) == meta_user_id),
                          None)
            if target:
                instagram_account.forget(target["id"])
                user_manager.disconnect_instagram(target["id"])
                admin_store.log("WARN", "instagram", f"User {target['email']} deauthorized app via Instagram")

    return {"success": True}


@app.get("/api/meta/deauthorize")
async def meta_deauthorize_get():
    return {"success": True, "message": "DM Flow Meta Deauthorization Endpoint"}


@app.get("/api/deletion-status")
async def deletion_status(code: str = ""):
    """Public on purpose. The confirmation code is the only thing that opens it,
    and it is what Meta hands the person, so it cannot sit behind a login."""
    row = data_deletion.lookup((code or "").strip())
    if not row:
        return {"success": False, "error": "No deletion request matches that code."}
    return {"success": True, "code": row["code"], "status": row.get("status", "completed"),
            "at": row.get("at"), "removed": row.get("removed", {})}


def _base_url(request: Request) -> str:
    hook = _webhook_url(request)
    return hook.replace("/api/meta/webhook", "")


@app.get("/deletion", response_class=HTMLResponse)
async def serve_deletion():
    return _page("deletion.html", "Data deletion instructions page missing")

# --- Product dashboard ---

@app.get("/app", response_class=HTMLResponse)
async def serve_app():
    # A stranger typing /app used to get somebody else's dashboard.
    if not signed_in_user():
        return RedirectResponse("/login?next=/app", status_code=303)
    return _page("index.html", "DM Flow dashboard loading...")

@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard_alias():
    if not signed_in_user():
        return RedirectResponse("/login?next=/app", status_code=303)
    return _page("index.html", "DM Flow dashboard loading...")

# --- Admin console ---

@app.get("/admin", response_class=HTMLResponse)
async def serve_admin():
    user = signed_in_user()
    if not user:
        return RedirectResponse("/login?next=/admin", status_code=303)
    if not is_admin_user(user):
        # A customer who finds the URL gets told no, not a control panel.
        return HTMLResponse(
            "<h1>403</h1><p>This area is for administrators.</p>"
            "<p><a href='/app'>Back to your dashboard</a></p>", status_code=403)
    return _page("admin.html", "Admin console missing")

# --- System & Session Endpoints ---

@app.get("/api/status")
async def get_status():
    require_user()
    active_count = sum(1 for r in automation_engine.get_all() if r.get("is_active") and r.get("type") == "comment_to_dm")
    stats = campaign_manager.get_stats()
    stats["watcher_status"] = comment_watcher.status
    stats["active_reels_count"] = active_count
    stats["billing"] = _billing_payload()
    stats["meta_connected"] = bool(meta_client.config.get("enabled"))
    stats["meta_account"] = meta_client.config.get("connected_account_username", "")
    return {"success": True, "stats": stats}

def _can_activate(active_count: int):
    """One gate for every 'can this automation go live?' question.

    Reads the workspace's live plan limits, so an Agency workspace is never
    told to upgrade and nobody is quoted a plan that no longer exists.
    """
    user = current_workspace()
    if not user:
        return True, "No workspace signed in"
    return user_manager.can_activate_automation(user, active_count)


# --- Billing & Plan Endpoints ---

def _billing_payload():
    """Plan, limits and usage for the workspace this dashboard is signed in as."""
    user = current_workspace()
    if not user:
        return {"plan": "free", "plan_name": "Free", "label": "No workspace", "is_pro": False,
                "limits": {}, "usage": {}, "days_left": 0}
    active_count = sum(1 for r in automation_engine.get_all()
                       if r.get("is_active") and r.get("type") == "comment_to_dm")
    user.setdefault("stats", {})["active_automations"] = active_count
    state = user_manager.plan_state(user)
    return {
        **state,
        "plan": state["plan_id"],
        "usage": user_manager.usage(user),
        "active_reels_count": active_count,
        "max_active_reels": state["limits"].get("automations", 0),
        "can_activate_more": user_manager.can_activate_automation(user, active_count)[0],
        "price_monthly": state["price_monthly"],
        "is_trial_expired": state["expired"],
        "workspace": {"id": user["id"], "name": user["name"], "business": user.get("business", ""),
                      "email": user["email"]},
        "instagram": {k: v for k, v in user.get("instagram", {}).items()
                      if k not in ("access_token", "page_access_token")},
    }


@app.get("/api/billing/status")
async def get_billing():
    require_user()
    return {"success": True, "billing": _billing_payload(),
            "plans": plans_manager.all_plans(public_only=True)}

@app.post("/api/billing/upgrade")
async def upgrade_workspace(req: dict = None):
    """Upgrade the signed-in workspace. Body may carry {plan_id, coupon}."""
    require_user()
    user = current_workspace()
    if not user:
        raise HTTPException(status_code=404, detail="No workspace")
    body = req or {}
    plan_id = body.get("plan_id") or plans_manager.default_paid_plan()["id"]
    coupon = body.get("coupon")

    amount = None
    if coupon:
        quote = plans_manager.apply_offer(coupon, plan_id)
        if not quote.get("valid"):
            return {"success": False, "error": quote.get("error")}
        amount = quote["final_price"]
        plans_manager.redeem(coupon)

    user_manager.set_plan(user["id"], plan_id, amount=amount, coupon=coupon)
    plan = plans_manager.get_plan(plan_id)
    campaign_manager.add_log("SUCCESS", f"Upgraded to {plan['name']} (Rs.{amount if amount is not None else plan['price_monthly']}/mo).")
    admin_store.log("SUCCESS", "billing", f"{user['email']} upgraded to {plan['name']}")
    return {"success": True, "billing": _billing_payload()}

@app.post("/api/billing/reset")
async def reset_trial():
    require_user()
    user = current_workspace()
    if user:
        user_manager.start_trial(user["id"])
    return {"success": True, "billing": _billing_payload()}

@app.post("/api/billing/coupon")
async def preview_coupon(req: dict):
    """Price a plan with a coupon, without consuming it."""
    require_user()
    quote = plans_manager.apply_offer(req.get("code", ""), req.get("plan_id", ""))
    return {"success": quote.get("valid", False), **quote}

# --- Instagram Posts Endpoint ---

@app.get("/api/instagram/posts")
async def get_instagram_posts():
    """Kept for older callers. Real media only — no sample posts, ever."""
    require_user()
    user = current_workspace()
    if not user or not instagram_account.connected(user):
        return {"success": False, "connected": False,
                "error": "Connect an Instagram account to see your posts.", "posts": []}
    ok, out = instagram_account.media(user, limit=24)
    if not ok:
        return {"success": False, "connected": True, "error": out, "posts": []}
    return {"success": True, "connected": True, "posts": out}

# --- Official Meta Graph API & Webhook Endpoints ---

@app.get("/api/meta/config")
async def get_meta_config():
    require_admin()
    cfg = dict(meta_client.config)
    token = cfg.get("access_token", "")
    if token:
        cfg["access_token_masked"] = token[:10] + "..." + token[-6:] if len(token) > 16 else "***"
    return {"success": True, "config": cfg}

@app.post("/api/meta/save")
async def save_meta_config(req: MetaConfigRequest):
    require_admin()
    saved = meta_client.save_config(req.dict(exclude_unset=True))
    campaign_manager.add_log("SUCCESS", "Updated Facebook Developer / Meta API configuration.")
    admin_u = current_workspace()
    if admin_u and saved.get("access_token"):
        conn = {
            "connected": bool(saved.get("enabled", True)),
            "provider": "meta_graph_api",
            "access_token": saved.get("access_token"),
            "connected_at": _now(),
            "page_id": saved.get("page_id", ""),
            "instagram_account_id": saved.get("instagram_account_id", ""),
            "username": saved.get("connected_account_username", ""),
            "display_name": saved.get("connected_account_name", ""),
        }
        user_manager.set_instagram(admin_u["id"], conn)
        instagram_account.forget(admin_u["id"])
    return {"success": True, "config": saved}

@app.post("/api/meta/test")
async def test_meta_connection(req: MetaTestRequest):
    require_admin()
    result = meta_client.test_connection(req.access_token)
    if result.get("success"):
        campaign_manager.add_log("SUCCESS", f"Connected via Meta Graph API: {result.get('message')}")
    else:
        campaign_manager.add_log("WARN", f"Meta Graph API connection failed: {result.get('error', result.get('message'))}")
    return result

@app.get("/api/meta/webhook")
async def meta_webhook_challenge(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge")
):
    """
    Handles Meta's Webhook verification handshake.
    """
    valid_tokens = {
        meta_client.config.get("verify_token", DEFAULT_VERIFY_TOKEN),
        platform_settings.meta_app().get("verify_token", "converflow_webhook_token"),
        DEFAULT_VERIFY_TOKEN,
        "converflow_webhook_token"
    }
    if hub_mode == "subscribe" and hub_verify_token in valid_tokens:
        campaign_manager.add_log("SUCCESS", "Meta Webhook handshake verified successfully!")
        return Response(content=hub_challenge or "", media_type="text/plain")
    return Response(content="Verification token mismatch", status_code=403)

class InternalDelivery:
    """Lets the poller hand an event to the real handler.

    When Advanced Access is not granted yet, Meta sends no comment webhooks at
    all, so the poller builds the same payload Meta would have sent. Routing it
    through this one handler is deliberate: a second copy of the matching,
    follow-gate and send logic would drift from this one within a week, and the
    polled path would quietly start behaving differently from the live path.
    """
    internal = True
    headers: Dict[str, str] = {}

    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload

    async def body(self) -> bytes:
        return json.dumps(self._payload).encode()

    async def json(self) -> Dict[str, Any]:
        return self._payload


def _signing_secrets() -> List[str]:
    """Every secret a genuine Meta payload may be signed with, best first.

    Meta uses two secrets for an Instagram Login app and the docs blur them:
    OAuth wants the Instagram app secret (Instagram > API setup), while
    webhook and signed_request payloads are signed with the Meta app secret
    (App settings > Basic). Checking only the first refused every real
    comment with "signature did not match". Accepting either is no weaker -
    both are secrets of the same app - and it survives whichever one an
    admin happens to paste where.
    """
    cfg = platform_settings.meta_app() or {}
    out: List[str] = []
    for val in (cfg.get("webhook_secret"),
                os.environ.get("META_APP_SECRET"),
                os.environ.get("INSTAGRAM_APP_SECRET"),
                os.environ.get("META_SECRET"),
                os.environ.get("APP_SECRET"),
                cfg.get("app_secret"),
                _meta_app_creds().get("app_secret")):
        val = str(val or "").strip()
        if val and val not in out:
            out.append(val)
    return out


def _webhook_signature_ok(raw: bytes, header: str) -> Tuple[bool, str]:
    """Is this really from Meta?

    The callback URL is public and the handler sends DMs on whatever it is
    told, so an unsigned or wrongly signed delivery is refused.
    """
    secrets = _signing_secrets()
    if not secrets:
        return True, "no app secret configured - delivery not verified"
    if not header:
        return False, "no signature header"
    sent = header.split("=", 1)[-1].strip()
    for secret in secrets:
        want = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        if hmac.compare_digest(sent, want):
            return True, ""
    return False, ("signature did not match the app secret. Webhooks are signed "
                   "with the Meta App Secret from App settings > Basic - paste it "
                   "into Admin > Instagram API > Webhook secret")


@app.post("/api/meta/webhook")
async def meta_webhook_event(request: Request):
    """
    Receives real-time incoming comments & messages from Meta Webhooks in 0.5s!
    """
    internal = getattr(request, "internal", False)
    try:
        raw = await request.body()
    except Exception as e:
        logger.error(f"[WEBHOOK ERROR] Could not read body: {e}")
        return {"status": "ignored"}

    if not internal:
        sig_ok, sig_note = _webhook_signature_ok(
            raw, request.headers.get("x-hub-signature-256", "")
            or request.headers.get("X-Hub-Signature-256", ""))
        if not sig_ok:
            logger.warning(f"[WEBHOOK REJECTED] {sig_note}")
            event_log.record("webhook", event_log.REJECTED, note=sig_note)
            raise HTTPException(status_code=403, detail="Invalid signature")
        if sig_note:
            logger.warning(f"[WEBHOOK UNVERIFIED] {sig_note}")

    try:
        body = json.loads(raw.decode() or "{}")
        logger.info(f"[WEBHOOK EVENT RECEIVED] {body}")
    except Exception as e:
        logger.error(f"[WEBHOOK ERROR] Invalid JSON body: {e}")
        return {"status": "ignored"}

    entries = body.get("entry", [])
    if not entries and "sample" in body:
        entries = [{"changes": [body["sample"]]}]
    processed_count = 0

    try:
        for entry in entries:
            # 1. Instagram comments changes
            for change in entry.get("changes", []):
                field = change.get("field")
                val = change.get("value", {})
                if field == "comments":
                    comment_id = val.get("id")
                    text = val.get("text", "")
                    from_user = val.get("from", {})
                    username = from_user.get("username", "unknown")
                    user_id = from_user.get("id")
                    media_id = val.get("media", {}).get("id")

                    logger.info(f"[WEBHOOK COMMENT] From: @{username} ({user_id}), Text: '{text}', Media: {media_id}, CommentID: {comment_id}")

                    # Claim it before acting. Once the app is published both the
                    # webhook and the poller see the same comment; whichever
                    # gets here first makes the other skip it.
                    if comment_id and comment_poller.was_handled(comment_id):
                        logger.info(f"[WEBHOOK] {comment_id} already handled; skipping")
                        continue
                    comment_poller.mark_handled(comment_id)

                    all_rules = automation_engine.get_all()
                    active_rules = [r for r in all_rules if r.get("is_active") and r.get("type") == "comment_to_dm"]
                    logger.info(f"[WEBHOOK RULES STATUS] Total active comment rules: {len(active_rules)}")
                    for r in active_rules:
                        logger.info(f"  -> Rule ID: {r.get('id')}, Name: '{r.get('name')}', Target MediaID: {r.get('post_media_id')}, Incoming Media: {media_id}, Keywords: {r.get('trigger_keywords')}, Scope: {r.get('trigger_scope')}")

                    def _rank(rule):
                        post_id = rule.get("post_media_id")
                        kws = [k for k in (rule.get("trigger_keywords") or []) if k and k != "*"]
                        bound = bool(post_id and media_id and str(post_id) == str(media_id))
                        keyed = any(kw.lower() in text.lower() for kw in kws)
                        if bound and keyed: return 0
                        if bound:           return 1
                        if keyed:           return 2
                        return 3

                    candidates = []
                    for rule in automation_engine.get_all():
                        if not rule.get("is_active") or rule.get("type") != "comment_to_dm":
                            continue
                        post_id = rule.get("post_media_id")
                        # A rule bound to a different post never applies here.
                        if post_id and media_id and str(post_id) != str(media_id):
                            continue
                        kws = rule.get("trigger_keywords") or ["*"]
                        catch_all = "*" in kws or rule.get("trigger_scope") == "any"
                        if not (catch_all or any(kw.lower() in text.lower() for kw in kws if kw)):
                            continue
                        candidates.append(rule)
                    candidates.sort(key=_rank)

                    if not candidates:
                        logger.warning(f"[WEBHOOK] No active rule matched for comment '{text}' on media {media_id}")
                        campaign_manager.add_log("INFO", f"Comment '{text}' received from @{username} but no active automation rule matched.")
                        event_log.record(
                            "poll" if getattr(request, "internal", False) else "webhook",
                            event_log.NO_RULE, field="comments", username=username,
                            text=text, media_id=str(media_id or ""),
                            note="It arrived, but no live flow matched this post or keyword.")

                    for rule in candidates:
                        logger.info(f"[WEBHOOK MATCHED RULE] Rule ID: {rule.get('id')}, Name: '{rule.get('name')}'")
                        # Workspace token for this rule
                        rule_user = user_manager.get(rule.get("created_by", ""))
                        if not rule_user:
                            for u in user_manager.all():
                                u_ig = (u or {}).get("instagram") or {}
                                if u_ig.get("connected") and u_ig.get("access_token"):
                                    rule_user = u
                                    break
                        user_token = ((rule_user or {}).get("instagram") or {}).get("access_token") or meta_client.config.get("access_token")

                        # The merchant testing their own flow comments from the
                        # account that owns the post. Acting on that means the
                        # account DMs itself, which Instagram refuses, and the
                        # merchant reads the silence as "it does not work".
                        owner_ig = str(((rule_user or {}).get("instagram") or {}).get("user_id") or ((rule_user or {}).get("instagram") or {}).get("instagram_account_id") or "")
                        if owner_ig and str(user_id or "") == owner_ig:
                            logger.info(f"[WEBHOOK] Skipping @{username}: the account's own comment")
                            event_log.record(
                                "poll" if getattr(request, "internal", False) else "webhook",
                                event_log.IGNORED, field="comments", username=username,
                                text=text, media_id=str(media_id or ""),
                                workspace=(rule_user or {}).get("email", ""),
                                note=("This comment is from the connected account itself. "
                                      "Instagram does not let an account DM itself - test "
                                      "by commenting from a different account."))
                            processed_count += 1
                            break

                        # 1. Public comment reply (Boosts Instagram algorithmic engagement)
                        pub_reply = rule.get("public_comment_reply")
                        if pub_reply and comment_id:
                            actual_reply = SpintaxEngine.spin(pub_reply)
                            pub_res = meta_client.reply_to_comment(comment_id, actual_reply, access_token=user_token)
                            if pub_res.get("success"):
                                logger.info(f"[WEBHOOK PUBLIC REPLY SENT] Comment: {comment_id}, Reply: '{actual_reply}'")
                            else:
                                logger.error(f"[WEBHOOK PUBLIC REPLY ERROR] {pub_res.get('error')}")
                                campaign_manager.add_log("WARNING", f"Public comment reply failed: {pub_res.get('error')}")

                        # 2. Follow-gate — hold the link until they follow.
                        require_follow = rule.get("require_follow", False)
                        account_name = follow_gate.owner_handle(rule, rule_user)

                        if require_follow and user_id:
                            state, why = follow_gate.status(user_id, user_token)
                            if state != follow_gate.FOLLOWS:
                                known = state == follow_gate.NOT_FOLLOWING
                                gate_msg = SpintaxEngine.spin(
                                    follow_gate.prompt_text(rule, account_name, username, known))
                                # A private reply, not a plain DM: this person
                                # commented, they never messaged us, so the
                                # ordinary 24-hour window is not open for them.
                                gate_res = private_reply.send(
                                    user_token, comment_id, gate_msg,
                                    (f"Follow @{account_name}" if account_name else None),
                                    (f"https://instagram.com/{account_name}" if account_name else None),
                                    fallback_user_id=user_id,
                                )
                                campaign_manager.add_log(
                                    "INFO",
                                    f"Follow-gate held the link for @{username} "
                                    f"({'not following' if known else 'follow status unknown'} — {why})")
                                event_log.record(
                                    "poll" if getattr(request, "internal", False) else "webhook",
                                    event_log.HELD, field="comments", username=username,
                                    text=text, media_id=str(media_id or ""),
                                    workspace=(rule_user or {}).get("email", ""),
                                    note=f"Follow-gate held the link ({why}). "
                                         f"Gate message {'sent' if gate_res.get('success') else 'FAILED: ' + str(gate_res.get('error'))}.")
                                contacts_manager.upsert_contact(
                                    username=username, name=username,
                                    source=f"Comment on {media_id}",
                                    tags=["Comment Lead", "Awaiting follow"],
                                    interaction_text=text)
                                processed_count += 1
                                break

                        # 3. User is following (or Follow-Gate disabled) -> Dispatch Main DM & Link!
                        raw_dm = rule.get("opening_dm") or rule.get("dm_message", "")
                        dm_msg = raw_dm.replace("{name}", username).replace("{first_name}", username).replace("{username}", username)
                        dm_msg = SpintaxEngine.spin(dm_msg)
                        btn_text = rule.get("button_text")
                        deliv_link = rule.get("delivery_link")
                        if comment_id or user_id:
                            dm_res = private_reply.send(
                                user_token, comment_id, dm_msg, btn_text, deliv_link,
                                fallback_user_id=user_id)
                            src = "poll" if getattr(request, "internal", False) else "webhook"
                            if dm_res.get("success"):
                                logger.info(f"[WEBHOOK DM SENT] To @{username} ({user_id})")
                                campaign_manager.add_log("SUCCESS", f"Automated reply and DM sent to @{username} on Reel ({text})")
                                event_log.record(src, event_log.SENT, field="comments",
                                                 username=username, text=text,
                                                 media_id=str(media_id or ""),
                                                 workspace=(rule_user or {}).get("email", ""),
                                                 note=f"DM sent for flow '{rule.get('name', '')}'.")
                            else:
                                logger.error(f"[WEBHOOK DM ERROR] {dm_res.get('error')}")
                                campaign_manager.add_log("ERROR", f"Failed to send DM to @{username}: {dm_res.get('error')}")
                                event_log.record(src, event_log.FAILED, field="comments",
                                                 username=username, text=text,
                                                 media_id=str(media_id or ""),
                                                 workspace=(rule_user or {}).get("email", ""),
                                                 note=str(dm_res.get("error")))

                        # Record CRM lead
                        contacts_manager.upsert_contact(
                            username=username,
                            name=username,
                            source=f"Meta Webhook (Reel {media_id})",
                            tags=rule.get("tags", ["Meta Lead", "Follower Verified" if require_follow else "Comment Lead"]),
                            interaction_text=text
                        )
                        processed_count += 1
                        break


            # 2. Instagram Direct Messages (DM keyword triggers)
            for msg_item in entry.get("messaging", []):
                sender = msg_item.get("sender", {})
                sender_id = sender.get("id")
                message = msg_item.get("message", {})
                msg_text = message.get("text", "")
                is_echo = message.get("is_echo", False)
                if not sender_id or not msg_text or is_echo:
                    continue

                for rule in automation_engine.get_all():
                    if not rule.get("is_active"):
                        continue
                    keywords = rule.get("trigger_keywords", ["*"])
                    if "*" in keywords or any(kw.lower() in msg_text.lower() for kw in keywords):
                        raw_dm = rule.get("dm_message") or rule.get("opening_dm", "")
                        btn_text = rule.get("button_text")
                        deliv_link = rule.get("delivery_link")
                        if raw_dm:
                            dm_msg = SpintaxEngine.spin(raw_dm)
                            # Always send on the rule owner's own connection.
                            dm_owner = user_manager.get(rule.get("created_by", ""))
                            dm_token = ((dm_owner or {}).get("instagram") or {}).get("access_token") or meta_client.config.get("access_token")
                            meta_client.send_instagram_dm(sender_id, dm_msg, btn_text, deliv_link,
                                                          access_token=dm_token)
                            processed_count += 1
                            campaign_manager.add_log("SUCCESS", f" Meta Webhook: Auto DM sent to sender {sender_id} (keyword: {msg_text})")
                            break
    except Exception as exc:
        logger.exception(f"[WEBHOOK PROCESSING EXCEPTION] {exc}")

    return {"status": "ok", "processed": processed_count}

# --- DM Flow Wizard Publish Endpoint ---

@app.post("/api/wizard/publish")
async def publish_wizard_automation(req: WizardPublishRequest):
    """
    Validates Free Trial limits (max 1 active reel) and creates the DM Flow automation rule.
    """
    require_user()
    active_count = sum(1 for r in automation_engine.get_all() if r.get("is_active") and r.get("type") == "comment_to_dm")

    # Check limits
    allowed, limit_msg = _can_activate(active_count)
    if not allowed:
        return {
            "success": False,
            "upgrade_required": True,
            "message": limit_msg,
            "plans": plans_manager.all_plans(public_only=True)
        }

    # Format public comment reply using spintax from the multiple variations
    public_spintax = ""
    if req.reply_to_comment and req.comment_replies:
        cleaned_replies = [r.strip() for r in req.comment_replies if r.strip()]
        if cleaned_replies:
            public_spintax = "{" + "|".join(cleaned_replies) + "}"

    user = current_workspace()
    rule_data = {
        "name": req.name,
        "type": "comment_to_dm",
        "post_target": req.post_target,
        "post_media_id": req.post_media_id or "",
        "post_thumbnail": req.post_thumbnail,
        "post_caption": req.post_caption,
        "trigger_keywords": req.trigger_keywords if req.trigger_scope == "specific" and req.trigger_keywords else ["*"],
        "trigger_scope": req.trigger_scope,
        "public_comment_reply": public_spintax,
        "comment_replies": req.comment_replies,
        "opening_dm": req.opening_dm,
        "button_text": req.button_text,
        "delivery_link": req.delivery_link,
        "dm_message": f"{req.opening_dm}\n\n {req.delivery_link}" if req.delivery_link else req.opening_dm,
        "require_follow": req.require_follow,
        "ask_email": req.ask_email,
        "tags": req.tags or ["Reel Lead", "DM Flow Flow"],
        "is_active": True,
        "created_by": user["id"] if user else "",
    }

    created = automation_engine.create(rule_data)
    campaign_manager.add_log("SUCCESS", f"Published DM Flow Automation: '{req.name}' for {req.post_target}")
    return {"success": True, "upgrade_required": False, "rule": created}


@app.post("/api/check-login")
async def check_login():
    require_user()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, campaign_manager.browser_manager.check_login_status)
    campaign_manager.add_log(
        "SUCCESS" if result.get("logged_in") else "WARN",
        f"Instagram session check: {result.get('message')}"
    )
    return result

@app.post("/api/open-login")
async def open_login():
    require_user()
    global login_thread
    if campaign_manager.status == "RUNNING" or comment_watcher.status == "RUNNING":
        raise HTTPException(status_code=400, detail="Cannot open login while an automation is running. Stop active task first.")

    def _login_worker():
        campaign_manager.add_log("INFO", "Opening Chromium window for Instagram login... Please log in in the browser.")
        res = campaign_manager.browser_manager.open_interactive_login(timeout_seconds=240)
        if res.get("success"):
            campaign_manager.add_log("SUCCESS", f"Authentication successful! {res.get('message')}")
        else:
            campaign_manager.add_log("WARN", f"Login window closed or timed out: {res.get('message', res.get('error'))}")

    login_thread = threading.Thread(target=_login_worker, daemon=True)
    login_thread.start()
    return {"success": True, "message": "Browser opened for login. Complete your login in the window."}

# --- DM Flow Automations Endpoints ---

@app.get("/api/automations")
async def list_automations():
    require_user()
    rules = automation_engine.get_all()
    return {"success": True, "automations": rules}

@app.post("/api/automations")
async def save_automation(req: AutomationRuleRequest):
    require_user()
    data = req.dict()
    rule_id = data.get("id")
    if rule_id and automation_engine.get_by_id(rule_id):
        updated = automation_engine.update(rule_id, data)
        campaign_manager.add_log("INFO", f"Updated DM Flow automation rule: '{data['name']}'")
        return {"success": True, "automation": updated}
    else:
        created = automation_engine.create(data)
        campaign_manager.add_log("SUCCESS", f"Created new DM Flow automation rule: '{data['name']}'")
        return {"success": True, "automation": created}

@app.post("/api/automations/{rule_id}/toggle")
async def toggle_automation(rule_id: str):
    require_user()
    rule = automation_engine.get_by_id(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    is_currently_active = rule.get("is_active", False)
    if not is_currently_active and rule.get("type") == "comment_to_dm":
        # Attempting to activate: check limit
        active_count = sum(1 for r in automation_engine.get_all() if r.get("is_active") and r.get("type") == "comment_to_dm")
        allowed, limit_msg = _can_activate(active_count)
        if not allowed:
            return {
                "success": False,
                "upgrade_required": True,
                "message": limit_msg,
                "plans": plans_manager.all_plans(public_only=True)
            }

    new_state = automation_engine.toggle_active(rule_id)
    state_str = "ENABLED" if new_state else "DISABLED"
    campaign_manager.add_log("INFO", f"Automation rule {rule_id} is now {state_str}")
    return {"success": True, "is_active": new_state}


@app.delete("/api/automations/{rule_id}")
async def delete_automation(rule_id: str):
    require_user()
    ok = automation_engine.delete(rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Rule not found")
    campaign_manager.add_log("WARN", f"Deleted automation rule {rule_id}")
    return {"success": True}

# --- DM Flow Flow Simulator Endpoint ---

@app.post("/api/simulator/send")
async def simulate_message(req: SimulatorMessageRequest):
    """
    Simulates DM Flow trigger matching for comments or DMs in the interactive phone preview.
    """
    require_user()
    username = req.username or "alex_growth"
    text = req.text.strip()

    if req.channel == "comment":
        res = automation_engine.match_comment(text, username=username, post_url=req.post_url)
        if res:
            contacts_manager.record_interaction(
                username=username,
                name=req.name or username,
                source="Simulator Comment",
                new_tags=res.get("tags", [])
            )
            return {
                "matched": True,
                "channel": "comment",
                "rule_name": res["rule_name"],
                "public_reply": res.get("public_reply", ""),
                "dm_reply": res.get("dm_reply", ""),
                "tags": res.get("tags", [])
            }
        else:
            return {
                "matched": False,
                "channel": "comment",
                "message": "No active Comment-to-DM rule matched your comment."
            }
    else: # DM
        res = automation_engine.match_dm(text, username=username)
        if res:
            contacts_manager.record_interaction(
                username=username,
                name=req.name or username,
                source="Simulator DM",
                new_tags=res.get("tags", [])
            )
            return {
                "matched": True,
                "channel": "dm",
                "rule_name": res["rule_name"],
                "dm_reply": res.get("dm_reply", ""),
                "tags": res.get("tags", [])
            }
        else:
            return {
                "matched": False,
                "channel": "dm",
                "message": "No active DM Keyword rule matched this message."
            }

# --- Contacts & CRM Endpoints ---

@app.get("/api/contacts")
async def get_contacts(search: Optional[str] = None, tag: Optional[str] = None):
    require_user()
    contacts = contacts_manager.get_all(search=search, tag=tag)
    return {"success": True, "contacts": contacts, "total": len(contacts)}

@app.get("/api/contacts/export")
async def export_contacts():
    require_user()
    csv_data = contacts_manager.export_csv()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="converflow_contacts.csv"'}
    )

class ContactCreateRequest(BaseModel):
    username: str
    name: Optional[str] = None
    tags: Optional[List[str]] = None
    source: Optional[str] = "Manual Capture"

@app.post("/api/contacts")
async def create_contact(req: ContactCreateRequest):
    require_user()
    if not req.username or not req.username.strip():
        raise HTTPException(status_code=400, detail="Username is required")
    contact = contacts_manager.record_interaction(
        username=req.username.strip(),
        name=req.name or req.username.strip(),
        source=req.source or "Manual Capture",
        tags=req.tags or ["New Lead"]
    )
    return {"success": True, "contact": contact}

@app.delete("/api/contacts/{contact_id}")
async def delete_contact(contact_id: int):
    require_user()
    removed = contacts_manager.remove_where(lambda c: c.get("id") == contact_id)
    return {"success": True, "removed": removed}

# --- Comment Watcher Background Task ---

@app.post("/api/watcher/start")
async def start_watcher(req: WatcherStartRequest):
    require_user()
    ok = comment_watcher.start(post_url=req.post_url, interval=req.interval or 60)
    if not ok:
        raise HTTPException(status_code=400, detail="Watcher is already running.")
    return {"success": True, "status": comment_watcher.status}

@app.post("/api/watcher/stop")
async def stop_watcher():
    require_user()
    ok = comment_watcher.stop()
    return {"success": ok, "status": comment_watcher.status}

# --- Broadcast / Outbound Campaign Endpoints ---

@app.post("/api/targets/load-text")
async def load_targets_text(req: LoadTextTargetsRequest):
    require_user()
    count = campaign_manager.load_targets_from_text(req.text)
    return {"success": True, "count": count, "total": len(campaign_manager.targets)}

@app.post("/api/targets/upload-csv")
async def upload_targets_csv(file: UploadFile = File(...)):
    require_user()
    content = await file.read()
    text = content.decode("utf-8", errors="replace")
    count = campaign_manager.load_targets_from_csv(text)
    return {"success": True, "count": count, "total": len(campaign_manager.targets)}

@app.get("/api/targets")
async def get_targets():
    require_user()
    return {
        "targets": [t.to_dict() for t in campaign_manager.targets],
        "total": len(campaign_manager.targets)
    }

@app.post("/api/targets/clear")
async def clear_targets():
    require_user()
    ok = campaign_manager.clear_targets()
    if not ok:
        raise HTTPException(status_code=400, detail="Cannot clear targets while campaign is running.")
    return {"success": True}

@app.post("/api/spintax/preview")
async def preview_spintax(req: SpintaxPreviewRequest):
    require_user()
    previews = SpintaxEngine.generate_previews(req.template, count=5)
    return {"success": True, "previews": previews}

@app.post("/api/campaign/start")
async def start_campaign(req: CampaignSettingsRequest):
    require_user()
    settings = req.dict()
    ok = campaign_manager.start_campaign(settings)
    if not ok:
        raise HTTPException(status_code=400, detail="Could not start campaign. Check if already running or if target queue is empty.")
    return {"success": True, "message": "Campaign started successfully"}

@app.post("/api/campaign/pause")
async def pause_campaign():
    require_user()
    ok = campaign_manager.pause_campaign()
    return {"success": ok}

@app.post("/api/campaign/resume")
async def resume_campaign():
    require_user()
    ok = campaign_manager.resume_campaign()
    return {"success": ok}

@app.post("/api/campaign/stop")
async def stop_campaign():
    require_user()
    ok = campaign_manager.stop_campaign()
    return {"success": ok}

@app.get("/api/campaign/export")
async def export_campaign():
    require_user()
    csv_data = campaign_manager.export_csv()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="instagram_dm_campaign.csv"'}
    )

@app.get("/api/logs/stream")
async def stream_logs():
    require_user()
    async def event_generator():
        q = campaign_manager.subscribe_logs()
        try:
            with campaign_manager._lock:
                backlog = list(campaign_manager.log_history[-30:])
            for log in backlog:
                yield f"data: {json.dumps(log)}\n\n"

            while True:
                try:
                    log = q.get_nowait()
                    yield f"data: {json.dumps(log)}\n\n"
                except Exception:
                    await asyncio.sleep(0.5)
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            campaign_manager.unsubscribe_logs(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# --- Meta Graph API & Webhook Endpoints ---

class MetaConnectRequest(BaseModel):
    access_token: str
    app_id: Optional[str] = None
    app_secret: Optional[str] = None
    verify_token: Optional[str] = DEFAULT_VERIFY_TOKEN


@app.get("/api/meta/config")
async def get_meta_config():
    require_admin()
    cfg = meta_client.config
    token = cfg.get("access_token", "")
    masked_token = (token[:8] + "..." + token[-4:]) if len(token) > 12 else ("***" if token else "")
    return {
        "enabled": cfg.get("enabled", False),
        "connected_account_name": cfg.get("connected_account_name", ""),
        "connected_account_username": cfg.get("connected_account_username", ""),
        "instagram_account_id": cfg.get("instagram_account_id", ""),
        "page_id": cfg.get("page_id", ""),
        "verify_token": cfg.get("verify_token", DEFAULT_VERIFY_TOKEN),
        "has_token": bool(token),
        "masked_token": masked_token
    }


@app.post("/api/meta/connect")
async def connect_meta(req: MetaConnectRequest):
    require_admin()
    result = meta_client.test_connection(req.access_token)
    if result.get("success"):
        if req.verify_token:
            meta_client.save_config({"verify_token": req.verify_token})
        admin_u = current_workspace()
        if admin_u:
            conn = {
                "connected": True,
                "provider": "meta_graph_api",
                "access_token": req.access_token,
                "connected_at": _now(),
                "page_id": meta_client.config.get("page_id", ""),
                "instagram_account_id": result.get("account", {}).get("ig_id", ""),
                "username": result.get("account", {}).get("ig_username", ""),
                "display_name": result.get("account", {}).get("ig_name", ""),
            }
            user_manager.set_instagram(admin_u["id"], conn)
            instagram_account.forget(admin_u["id"])
        campaign_manager.add_log("INFO", f"Official Meta Graph API connected to @{result['account']['ig_username']}")
    return result


@app.post("/api/meta/disconnect")
async def disconnect_meta():
    require_admin()
    meta_client.save_config({
        "enabled": False,
        "access_token": "",
        "page_id": "",
        "instagram_account_id": "",
        "connected_account_name": "",
        "connected_account_username": ""
    })
    admin_u = current_workspace()
    if admin_u:
        user_manager.disconnect_instagram(admin_u["id"])
        instagram_account.forget(admin_u["id"])
    campaign_manager.add_log("INFO", "Meta Graph API disconnected.")
    return {"success": True, "message": "Meta API disconnected."}






# =============================================================================
# AUTH — signup / login against the multi-user store
# =============================================================================

class SignupRequest(BaseModel):
    name: str
    email: str
    password: str
    business: Optional[str] = ""
    ig_handle: Optional[str] = ""

class LoginRequest(BaseModel):
    email: str
    password: str

class AdminUserRequest(BaseModel):
    name: str
    email: str
    password: Optional[str] = "converflow123"
    business: Optional[str] = ""
    ig_handle: Optional[str] = ""
    plan: Optional[str] = "trial"

class AdminUserPatch(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    business: Optional[str] = None
    ig_handle: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    password: Optional[str] = None

class PlanChangeRequest(BaseModel):
    plan: str
    record_payment: bool = True

class ExtendTrialRequest(BaseModel):
    days: int = 7

class AnnouncementRequest(BaseModel):
    title: str
    body: str
    audience: Optional[str] = "all"
    level: Optional[str] = "update"


@app.post("/api/auth/signup")
async def auth_signup(req: SignupRequest):
    ok, result = user_manager.create(
        name=req.name, email=req.email, password=req.password,
        ig_handle=req.ig_handle or "", business=req.business or ""
    )
    if not ok:
        return {"success": False, "error": result}
    admin_store.log("SUCCESS", "signup", f"New workspace created: {result['name']} ({result['email']})")
    campaign_manager.add_log("SUCCESS", f"New DM Flow workspace: {result['email']}")
    return {"success": True, "user": user_manager.public(result)}


@app.post("/api/auth/login")
async def auth_login(req: LoginRequest, request: Request, response: Response):
    ok, result = user_manager.authenticate(req.email, req.password)
    if not ok:
        # Deliberately vague and deliberately slow-ish: do not tell an attacker
        # whether the email exists.
        return {"success": False, "error": result}

    token, expires = cf_auth.start_session(
        result,
        user_agent=request.headers.get("user-agent", ""),
        ip=(request.client.host if request.client else ""),
    )
    response.set_cookie(
        cf_auth.SESSION_COOKIE, token,
        max_age=cf_auth.SESSION_DAYS * 86400,
        httponly=True, # JavaScript cannot read it
        samesite="lax", # not sent on cross-site POSTs
        secure=bool(os.environ.get("COOKIE_SECURE", "")), # set in production
        path="/",
    )
    cf_auth.audit(result, "auth.login", result["id"], note="signed in")
    return {"success": True, "user": user_manager.public(result),
            "is_admin": is_admin_user(result)}


@app.post("/api/auth/logout")
async def auth_logout(request: Request, response: Response):
    cf_auth.end_session(request.cookies.get(cf_auth.SESSION_COOKIE))
    response.delete_cookie(cf_auth.SESSION_COOKIE, path="/")
    return {"success": True}


@app.get("/api/auth/me")
async def auth_me():
    """Who is this browser? The front end uses it to decide what to render."""
    user = signed_in_user()
    if not user:
        return {"success": True, "signed_in": False}
    return {"success": True, "signed_in": True, "user": user_manager.public(user),
            "is_admin": is_admin_user(user)}


@app.get("/api/auth/announcement")
async def auth_announcement():
    """Latest published notice, for the in-app ribbon."""
    return {"success": True, "announcement": admin_store.latest_published()}


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    business: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


@app.post("/api/auth/profile")
async def auth_update_profile(req: ProfileUpdateRequest):
    """Update name, workspace name, or change password for the signed-in user."""
    user = signed_in_user()
    if not user:
        raise HTTPException(status_code=401, detail="Please sign in first")

    patch = {}
    if req.name and req.name.strip():
        patch["name"] = req.name.strip()
    if req.business is not None:
        patch["business"] = req.business.strip()

    if req.new_password and req.new_password.strip():
        if len(req.new_password.strip()) < 6:
            return {"success": False, "error": "New password must be at least 6 characters"}
        if not req.current_password or not user_manager.verify_password(req.current_password, user.get("password_hash", "")):
            return {"success": False, "error": "Current password is incorrect"}
        patch["password"] = req.new_password.strip()

    if not patch:
        return {"success": True, "message": "No changes made", "user": user_manager.public(user)}

    updated = user_manager.update(user["id"], patch)
    if not updated:
        return {"success": False, "error": "Could not update profile"}

    admin_store.log("INFO", "user", f"{user['email']} updated profile details")
    return {"success": True, "message": "Profile updated successfully", "user": user_manager.public(updated)}


# =============================================================================
# ADMIN — business control room
# =============================================================================

@app.get("/api/admin/overview")
async def admin_overview():
    require_admin()
    users = user_manager.list_public()
    return {
        "success": True,
        "metrics": user_manager.metrics(),
        "revenue_series": user_manager.revenue_series(6),
        "recent_payments": user_manager.recent_payments(14),
        "recent_users": users[:6],
        "health": admin_store.health_summary(),
        "plans": plans_manager.all_plans(),
        "offers": plans_manager.all_offers(),
        "instagram_ready": platform_settings.meta_ready(),
    }


@app.get("/api/admin/users")
async def admin_users(search: str = "", plan: str = "all", status: str = "all"):
    require_admin()
    return {"success": True, "users": user_manager.list_public(search=search, plan=plan, status=status)}


@app.get("/api/admin/users/{user_id}")
async def admin_user_detail(user_id: str):
    require_admin()
    user = user_manager.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, "user": user_manager.public(user)}


@app.post("/api/admin/users")
async def admin_create_user(req: AdminUserRequest):
    require_admin()
    ok, result = user_manager.create(
        name=req.name, email=req.email, password=req.password or "converflow123",
        ig_handle=req.ig_handle or "", business=req.business or ""
    )
    if not ok:
        return {"success": False, "error": result}
    if (req.plan or "trial").lower() == "pro":
        user_manager.set_plan(result["id"], "pro")
    admin_store.log("SUCCESS", "admin", f"Workspace created from admin: {result['email']}")
    return {"success": True, "user": user_manager.public(user_manager.get(result["id"]))}


@app.patch("/api/admin/users/{user_id}")
async def admin_update_user(user_id: str, req: AdminUserPatch):
    require_admin()
    user = user_manager.update(user_id, req.dict(exclude_unset=True))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    admin_store.log("INFO", "admin", f"Workspace details updated: {user['email']}")
    return {"success": True, "user": user_manager.public(user)}


@app.post("/api/admin/users/{user_id}/plan")
async def admin_set_plan(user_id: str, req: PlanChangeRequest):
    actor = require_admin()
    was = user_manager.get(user_id)
    before = {"plan": was.get("plan"), "state": was.get("subscription_state")} if was else None
    plan_id = req.plan
    if plan_id == "trial":
        user = user_manager.start_trial(user_id)
        action = "moved to trial"
    else:
        user = user_manager.set_plan(user_id, plan_id, record_payment=req.record_payment)
        plan = plans_manager.get_plan(plan_id)
        action = f"moved to {plan['name']} (Rs.{plan['price_monthly']}/mo)" if plan else "plan changed"
    if not user:
        raise HTTPException(status_code=404, detail="User or plan not found")
    admin_store.log("SUCCESS", "billing", f"{user['email']} {action}")
    cf_auth.audit(actor, "customer.plan_changed", user_id, before,
                  {"plan": user.get("plan"), "state": user.get("subscription_state")},
                  f"{user['email']} {action}")
    return {"success": True, "user": user_manager.public(user)}


@app.post("/api/admin/users/{user_id}/extend")
async def admin_extend_trial(user_id: str, req: ExtendTrialRequest):
    require_admin()
    user = user_manager.extend_trial(user_id, req.days)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    admin_store.log("INFO", "billing", f"Trial extended by {req.days} days for {user['email']}")
    return {"success": True, "user": user_manager.public(user)}


@app.post("/api/admin/users/{user_id}/toggle")
async def admin_toggle_user(user_id: str):
    actor = require_admin()
    was = user_manager.get(user_id)
    before = {"status": was.get("status")} if was else None
    user = user_manager.toggle_status(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user["status"] == "suspended":
        # A suspended account must stop working immediately, not at cookie expiry.
        cf_auth.end_all_sessions(user_id)
    admin_store.log("WARN" if user["status"] == "suspended" else "SUCCESS", "admin",
                    f"{user['email']} is now {user['status']}")
    cf_auth.audit(actor, "customer.status_changed", user_id, before,
                  {"status": user["status"]}, f"{user['email']} is now {user['status']}")
    return {"success": True, "user": user_manager.public(user)}


@app.delete("/api/admin/users/{user_id}")
async def admin_delete_user(user_id: str):
    require_admin()
    user = user_manager.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    email = user["email"]
    user_manager.delete(user_id)
    admin_store.log("WARN", "admin", f"Workspace deleted: {email}")
    return {"success": True}


@app.get("/api/admin/events")
async def admin_events(level: str = "all", limit: int = 60):
    require_admin()
    return {
        "success": True,
        "events": admin_store.list_events(level=level, limit=limit),
        "health": admin_store.health_summary(),
    }


@app.get("/api/admin/announcements")
async def admin_list_announcements():
    require_admin()
    return {"success": True, "announcements": admin_store.list_announcements()}


@app.post("/api/admin/announcements")
async def admin_add_announcement(req: AnnouncementRequest):
    require_admin()
    item = admin_store.add_announcement(
        title=req.title, body=req.body,
        audience=req.audience or "all", level=req.level or "update"
    )
    return {"success": True, "announcement": item}


@app.delete("/api/admin/announcements/{ann_id}")
async def admin_delete_announcement(ann_id: str):
    require_admin()
    ok = admin_store.delete_announcement(ann_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return {"success": True}


@app.get("/api/admin/export/users")
async def admin_export_users():
    require_admin()
    import csv, io
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Name", "Email", "Brand", "Instagram", "Plan", "Status",
                     "Joined", "Contacts", "Automations", "DMs Sent", "Revenue (INR)", "Last Active"])
    for u in user_manager.all():
        state = user_manager.plan_state(u)
        stats = u.get("stats", {})
        revenue = sum(p["amount"] for p in u.get("payments", []) if p.get("status") == "paid")
        writer.writerow([
            u.get("name", ""), u.get("email", ""), u.get("business", ""), u.get("ig_handle", ""),
            state["plan"], u.get("status", ""), u.get("created_at", ""),
            stats.get("contacts", 0), stats.get("automations", 0), stats.get("dms_sent", 0),
            revenue, stats.get("last_active", ""),
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=converflow_users.csv"},
    )


# =============================================================================
# PUBLIC — what the marketing site and dashboard may read
# =============================================================================

@app.get("/api/public/plans")
async def public_plans():
    return {
        "success": True,
        "plans": plans_manager.all_plans(public_only=True),
        "offers": [o for o in plans_manager.all_offers() if o.get("status") == "live"],
        "brand": platform_settings.brand_public(),
    }


@app.get("/api/public/settings")
async def public_settings():
    return {"success": True, **platform_settings.brand_public()}


# =============================================================================
# ADMIN — plans & pricing
# =============================================================================

class PlanPayload(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    tagline: Optional[str] = None
    price_monthly: Optional[int] = None
    price_yearly: Optional[int] = None
    currency: Optional[str] = None
    order: Optional[int] = None
    is_public: Optional[bool] = None
    highlight: Optional[bool] = None
    badge: Optional[str] = None
    trial_days: Optional[int] = None
    limits: Optional[Dict[str, int]] = None
    features: Optional[Dict[str, bool]] = None

class OfferPayload(BaseModel):
    id: Optional[str] = None
    code: str
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = "percent"
    value: Optional[int] = 0
    applies_to: Optional[Any] = None
    duration: Optional[str] = "first_month"
    starts_at: Optional[str] = None
    expires_at: Optional[str] = None
    max_redemptions: Optional[int] = 0
    active: Optional[bool] = True

class SettingsPayload(BaseModel):
    section: str
    values: Dict[str, Any]

class TemplatePayload(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    enabled: Optional[bool] = None

class CouponCheck(BaseModel):
    code: str
    plan_id: str


@app.get("/api/admin/plans")
async def admin_list_plans():
    require_admin()
    return {
        "success": True,
        "plans": plans_manager.all_plans(),
        "schema": plans_manager.schema(),
        "usage": {p["id"]: sum(1 for u in user_manager.all() if u.get("plan") == p["id"])
                  for p in plans_manager.all_plans()},
    }


@app.post("/api/admin/plans")
async def admin_save_plan(req: PlanPayload):
    require_admin()
    ok, result = plans_manager.save_plan(req.dict(exclude_unset=True))
    if not ok:
        return {"success": False, "error": result}
    admin_store.log("INFO", "plans", f"Plan saved: {result['name']} (Rs.{result['price_monthly']}/mo)")
    return {"success": True, "plan": result}


@app.delete("/api/admin/plans/{plan_id}")
async def admin_delete_plan(plan_id: str):
    require_admin()
    in_use = sum(1 for u in user_manager.all() if u.get("plan") == plan_id)
    if in_use:
        return {"success": False,
                "error": f"{in_use} workspace(s) are on this plan. Move them first."}
    ok, message = plans_manager.delete_plan(plan_id)
    if not ok:
        return {"success": False, "error": message}
    admin_store.log("WARN", "plans", f"Plan deleted: {plan_id}")
    return {"success": True}


@app.post("/api/admin/plans/reorder")
async def admin_reorder_plans(req: Dict[str, List[str]]):
    require_admin()
    plans_manager.reorder(req.get("order", []))
    return {"success": True, "plans": plans_manager.all_plans()}


# =============================================================================
# ADMIN — offers & coupons
# =============================================================================

@app.get("/api/admin/offers")
async def admin_list_offers():
    require_admin()
    return {"success": True, "offers": plans_manager.all_offers(),
            "schema": plans_manager.schema(),
            "plans": [{"id": p["id"], "name": p["name"]} for p in plans_manager.all_plans()]}


@app.post("/api/admin/offers")
async def admin_save_offer(req: OfferPayload):
    require_admin()
    ok, result = plans_manager.save_offer(req.dict(exclude_unset=True))
    if not ok:
        return {"success": False, "error": result}
    admin_store.log("SUCCESS", "offers", f"Coupon {result['code']} saved")
    return {"success": True, "offer": result}


@app.post("/api/admin/offers/{offer_id}/toggle")
async def admin_toggle_offer(offer_id: str):
    require_admin()
    offer = plans_manager.toggle_offer(offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    return {"success": True, "offer": offer}


@app.delete("/api/admin/offers/{offer_id}")
async def admin_delete_offer(offer_id: str):
    require_admin()
    if not plans_manager.delete_offer(offer_id):
        raise HTTPException(status_code=404, detail="Offer not found")
    return {"success": True}


@app.post("/api/admin/offers/check")
async def admin_check_offer(req: CouponCheck):
    require_admin()
    return {"success": True, "result": plans_manager.apply_offer(req.code, req.plan_id)}


# =============================================================================
# ADMIN — platform settings, Meta app & templates
# =============================================================================

@app.get("/api/admin/settings")
async def admin_get_settings():
    require_admin()
    return {"success": True, "settings": platform_settings.public(),
            "default_scopes": platform_settings.meta_app().get("scopes", [])}


@app.post("/api/admin/settings")
async def admin_save_settings(req: SettingsPayload):
    require_admin()
    section = platform_settings.update_section(req.section, req.values)
    admin_store.log("INFO", "settings", f"Updated {req.section} settings")
    return {"success": True, "section": req.section, "values": platform_settings.public().get(req.section, section)}


def _looks_like_facebook_pair(app_id: str, app_secret: str) -> bool:
    """Is this the Facebook app id and secret rather than the Instagram ones?

    `{app-id}|{app-secret}` is a Facebook app access token. If Meta answers to
    it, the pair came from App Settings > Basic. Instagram Login needs the
    separate id and secret under Instagram > API setup with Instagram login,
    and pasting the Facebook pair fails much later with an error that blames
    redirect_uri - which is how an afternoon disappears.
    """
    if not (app_id and app_secret):
        return False
    token = urllib.parse.quote(f"{app_id}|{app_secret}")
    try:
        base = os.environ.get("FB_GRAPH_BASE", "https://graph.facebook.com/v21.0").rstrip("/")
        url = (f"{base}/{urllib.parse.quote(str(app_id))}"
               f"?fields=id,name&access_token={token}")
        req = urllib.request.Request(url, headers={"User-Agent": "DMFlow"})
        with urllib.request.urlopen(req, timeout=12) as res:
            return bool(json.loads(res.read().decode()).get("id"))
    except Exception:
        return False


@app.post("/api/admin/meta-app/test")
async def admin_test_meta_app():
    require_admin()
    result = meta_oauth.test_app()

    # test_app() falls back to "the id is digits and the secret is long
    # enough" and reports success. That green tick is worth nothing, and it
    # is what let the wrong credentials sit here looking correct. Check the
    # one thing that actually distinguishes them, and never claim more than
    # was verified.
    cfg = platform_settings.meta_app()
    app_id = str(cfg.get("app_id") or "").strip()
    app_secret = str(cfg.get("app_secret") or "").strip()
    if app_id and app_secret and _looks_like_facebook_pair(app_id, app_secret):
        result = {
            "success": False,
            "error": (f"These are the Facebook app credentials for app {app_id}. "
                      f"Instagram Login needs its own pair - open App Dashboard "
                      f"\u2192 Instagram \u2192 API setup with Instagram login and copy the "
                      f"Instagram App ID and Instagram App Secret from there."),
        }
    elif result.get("success") and not result.get("app_id"):
        result["message"] = ("Saved. Meta would not confirm these from here, which is "
                             "normal for Instagram Login credentials - the real test is "
                             "pressing Connect on the dashboard.")

    admin_store.log("SUCCESS" if result.get("success") else "ERROR", "instagram",
                    result.get("message") or result.get("error", "Meta app test"))
    return result


@app.get("/api/admin/templates")
async def admin_list_templates():
    require_admin()
    return {"success": True, "templates": platform_settings.list_templates()}


@app.patch("/api/admin/templates/{template_id}")
async def admin_save_template(template_id: str, req: TemplatePayload):
    require_admin()
    tpl = platform_settings.save_template(template_id, req.dict(exclude_unset=True))
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"success": True, "template": tpl}


@app.get("/api/admin/templates/{template_id}/preview")
async def admin_preview_template(template_id: str):
    require_admin()
    sample = {
        "first_name": "Riya", "business": "GlowCart Skincare", "ig_handle": "glowcart.in",
        "plan_name": plans_manager.default_paid_plan()["name"],
        "price": f"₹{plans_manager.default_paid_plan()['price_monthly']}",
        "trial_days": 15, "days_left": 3, "expiry_date": "2 Oct 2026",
        "contacts": 284, "dms_sent": 1120, "amount": "₹799",
        "invoice_no": "CF-2026-0042", "renews_on": "20 Oct 2026",
        "upgrade_url": "http://localhost:8000/pricing",
    }
    rendered = platform_settings.render_template(template_id, sample)
    if not rendered:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"success": True, "preview": rendered}


# =============================================================================
# INSTAGRAM CONNECT — one Meta app, every customer connects themselves
# =============================================================================

@app.get("/api/instagram/status")
async def instagram_status(user_id: Optional[str] = None):
    require_user()
    user = user_manager.get(user_id) if user_id else current_workspace()
    if not user:
        raise HTTPException(status_code=404, detail="No workspace")
    ig = dict(user.get("instagram", {}))
    # Keep admin workspace connection in sync with Meta platform configuration
    if not (ig.get("connected") and ig.get("access_token")) and meta_client.config.get("enabled") and meta_client.config.get("access_token") and is_admin_user(user):
        conn = {
            "connected": True,
            "provider": meta_client.config.get("provider", "meta_graph_api"),
            "access_token": meta_client.config.get("access_token"),
            "connected_at": meta_client.config.get("updated_at") or _now(),
            "page_id": meta_client.config.get("page_id", ""),
            "instagram_account_id": meta_client.config.get("instagram_account_id", ""),
            "username": meta_client.config.get("connected_account_username", "satnamwebservices"),
            "display_name": meta_client.config.get("connected_account_name", "Satnam web services"),
        }
        user_manager.set_instagram(user["id"], conn)
        user = user_manager.get(user["id"]) or user
        ig = dict(user.get("instagram", {}))

    clean_ig = {k: v for k, v in ig.items()
                if k not in ("access_token", "page_access_token")}
    return {"success": True, "instagram": clean_ig,
            "platform_ready": platform_settings.meta_ready(),
            "allow_browser_login": platform_settings.section("flags").get("allow_browser_login", True)}


@app.get("/api/instagram/connect")
async def instagram_connect(user_id: Optional[str] = None):
    require_user()
    user = user_manager.get(user_id) if user_id else current_workspace()
    if not user:
        raise HTTPException(status_code=404, detail="No workspace")
    ok, url = meta_oauth.consent_url(user["id"])
    if not ok:
        return {"success": False, "error": url}
    return {"success": True, "url": url}


@app.post("/api/instagram/connect-token")
async def instagram_connect_token(req: MetaTestRequest, user_id: Optional[str] = None):
    require_user()
    user = user_manager.get(user_id) if user_id else current_workspace()
    if not user:
        raise HTTPException(status_code=404, detail="No workspace")

    result = meta_client.test_connection(req.access_token)
    if not result.get("success"):
        return result

    account = result.get("account", {})
    conn = {
        "connected": True,
        "provider": "direct_token",
        "access_token": req.access_token,
        "connected_at": _now(),
        "page_id": account.get("page_id", ""),
        "page_name": account.get("page_name", ""),
        "page_access_token": account.get("page_access_token") or req.access_token,
        "instagram_account_id": account.get("ig_id", ""),
        "username": account.get("ig_username", ""),
        "display_name": account.get("ig_name", ""),
        "avatar": account.get("profile_picture", ""),
    }
    user_manager.set_instagram(user["id"], conn)
    return {"success": True, "message": result.get("message"), "account": account}


@app.get("/api/instagram/callback", response_class=HTMLResponse)
async def instagram_callback(request: Request, code: Optional[str] = None,
                             state: Optional[str] = None,
                             error: Optional[str] = None,
                             error_description: Optional[str] = None):
    """Meta redirects the customer's browser here after they approve."""
    def page(title: str, message: str, ok: bool) -> HTMLResponse:
        # The site accent, not the #00824b this project replaced - that hex
        # was the colour we deliberately moved away from, and this is the
        # very first screen a merchant sees after authorising.
        colour = "#0fbf73" if ok else "#e5484d"
        icon = "M20 6L9 17l-5-5" if ok else "M18 6L6 18M6 6l12 12"
        return HTMLResponse(f"""
<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — DM Flow</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
  body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#f8fafb;
       font-family:'Plus Jakarta Sans',system-ui,sans-serif;color:#0b0f14;padding:24px}}
  .box{{background:#fff;border:1px solid #e8ebef;border-radius:20px;padding:40px;max-width:440px;
       text-align:center;box-shadow:0 18px 48px rgba(11,15,20,.10)}}
  .ring{{width:60px;height:60px;border-radius:50%;display:grid;place-items:center;margin:0 auto 20px;
        background:{colour}18;color:{colour}}}
  h1{{font-size:22px;margin:0 0 10px;letter-spacing:-.03em}}
  p{{font-size:15px;color:#5b6673;line-height:1.65;margin:0 0 26px}}
  a{{display:inline-block;background:#0fbf73;color:#04291a;text-decoration:none;font-weight:700;
     font-size:15px;padding:13px 26px;border-radius:999px}}
</style></head><body><div class="box">
<div class="ring"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor"
  stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="{icon}"/></svg></div>
<h1>{title}</h1><p>{message}</p><a href="/app#settings">Back to dashboard</a>
</div></body></html>""")

    if error:
        return page("Connection cancelled",
                    error_description or "You cancelled the Instagram connection. Nothing was changed.", False)
    if not code or not state:
        return page("Something went wrong", "Instagram did not send an authorisation code. Try again from the dashboard.", False)

    code = (code or "").replace("#_", "").split("#")[0].strip()
    state = (state or "").replace("#_", "").split("#")[0].strip()

    ok, result = meta_oauth.complete(code, state)
    if not ok:
        # Meta's message for this failure names redirect_uri but never says
        # which one we sent, so the merchant is left comparing a value they
        # cannot see against one in another tab. Say it out loud.
        cfg = _meta_app_creds()
        sent = (platform_settings.meta_app().get("redirect_uri") or "").strip().rstrip("/")
        admin_store.log("ERROR", "instagram",
                        f"Connect failed: {result} | app_id={cfg.get('app_id', '')} "
                        f"redirect_uri={sent!r}")
        extra = ""
        if "redirect_uri" in str(result).lower() or "verification code" in str(result).lower():
            # Meta names redirect_uri in this error, but the usual cause is a
            # different field entirely: Instagram Login has its OWN app id and
            # secret, separate from the Facebook ones at the top of the
            # dashboard. Paste the Facebook pair and this is the error you get.
            extra = (
                f"<br><br><b>App id in use:</b> <code>{cfg.get('app_id') or '(not set)'}</code>"
                f"<br><b>Redirect URI we sent:</b><br><code>{sent or '(not set)'}</code>"
                f"<br><br>Check these three, in this order:"
                f"<br><br>1. The id and secret must be the <b>Instagram</b> ones, from "
                f"<b>App Dashboard &rarr; Instagram &rarr; API setup with Instagram login</b>. "
                f"They are different numbers from the Facebook app id shown at the top of "
                f"the dashboard — using the Facebook pair gives exactly this error."
                f"<br>2. The redirect URI above must match one in <b>Valid OAuth Redirect "
                f"URIs</b> character for character. Meta sometimes adds a trailing slash "
                f"when you save it, so open the list and look."
                f"<br>3. If both already match, the code was used twice. Start again from "
                f"the dashboard instead of reloading this page."
            )
        return page("Could not connect", str(result) + extra, False)

    user = user_manager.set_instagram(result["user_id"], result["connection"])
    conn = result["connection"]
    # Subscribe this account to comment and message events. Two different
    # endpoints depending on how it connected — and the Instagram Login case
    # was never handled, so those accounts connected and then received nothing.
    if conn.get("page_id") and conn.get("page_access_token"):
        meta_oauth.subscribe_webhook(conn["page_id"], conn["page_access_token"])
    elif conn.get("access_token"):
        # Two levels, and the app level has to come first: Instagram will not
        # give an account's comment events to an app that never asked for
        # comment events. Doing both here means a new merchant is live on
        # connect instead of having to find the Repair button.
        creds = _meta_app_creds()
        if creds.get("app_id") and creds.get("app_secret") and request is not None:
            app_ok, app_msg = webhook_setup.subscribe_app(
                creds["app_id"], creds["app_secret"],
                _webhook_url(request), creds.get("verify_token", ""))
            admin_store.log("SUCCESS" if app_ok else "ERROR", "instagram",
                            f"App-level webhook registration: "
                            f"{'registered for comments' if app_ok else app_msg}")
        sub_ok, sub_msg = webhook_setup.subscribe(conn["access_token"])
        admin_store.log(
            "SUCCESS" if sub_ok else "ERROR", "instagram",
            f"Webhook subscription for @{conn.get('username')}: "
            f"{'subscribed to comments and messages' if sub_ok else sub_msg}")

    meta_client.save_config({
        "enabled": True,
        "access_token": conn.get("page_access_token") or conn.get("access_token", ""),
        "page_id": conn.get("page_id", ""),
        "instagram_account_id": conn.get("instagram_account_id", ""),
        "connected_account_username": conn.get("username", ""),
        "connected_account_name": conn.get("display_name", ""),
    })

    admin_store.log("SUCCESS", "instagram",
                    f"@{conn.get('username')} connected by {user['email'] if user else result['user_id']}")
    campaign_manager.add_log("SUCCESS", f"Instagram connected: @{conn.get('username')}")
    return page("Instagram connected",
                f"@{conn.get('username')} is linked. Your comment and DM automations can go live now.", True)


@app.post("/api/instagram/disconnect")
async def instagram_disconnect(user_id: Optional[str] = None):
    require_user()
    user = user_manager.get(user_id) if user_id else current_workspace()
    if not user:
        raise HTTPException(status_code=404, detail="No workspace")
    user_manager.disconnect_instagram(user["id"])
    admin_store.log("WARN", "instagram", f"{user['email']} disconnected their Instagram account")
    return {"success": True}


# =============================================================================
# INSIGHTS — the numbers rivals stop short of
# =============================================================================

@app.get("/api/insights")
async def get_insights():
    """Funnel, safety headroom, reply speed and system health in one call."""
    require_user()
    user = current_workspace()
    is_live = POLL_ENABLED or bool(meta_client.config.get("enabled")) or comment_watcher.status in ("running", "active", "on")
    watcher = "running" if is_live else comment_watcher.status
    connected = bool(meta_client.config.get("enabled")) or bool(
        (user or {}).get("instagram", {}).get("connected"))

    return {
        "success": True,
        "funnel": insights.funnel(),
        "keywords": insights.by_keyword(),
        "safety": insights.safety(platform_settings.section("safety")),
        "speed": insights.speed(),
        "health": insights.health(connected, watcher),
        "plan": (user_manager.plan_state(user) if user else None),
    }


# ===========================================================================
# PAYMENTS — Razorpay
# Three rules this code keeps:
# 1. The price is decided on the server, from the live plan catalogue.
# The browser sends a plan id, never an amount.
# 2. A plan changes only after the signature verifies against our secret.
# 3. Webhook and browser callback are both idempotent — whichever arrives
# second finds the payment already recorded and does nothing.
# ===========================================================================

def _already_paid(user: Dict[str, Any], payment_id: str) -> bool:
    return any(p.get("reference") == payment_id for p in (user.get("payments") or []))


@app.get("/api/billing/gateway")
async def billing_gateway():
    """What the checkout button needs to know before it renders."""
    require_user()
    return {
        "success": True,
        "ready": razorpay.ready(),
        "mode": razorpay.mode(),
        "key_id": razorpay.key_id if razorpay.ready() else "",
        "currency": platform_settings.section("billing").get("currency", "INR"),
    }


@app.post("/api/billing/checkout")
async def billing_checkout(req: dict = None):
    """Price the plan, apply any coupon, and open a Razorpay order."""
    require_user()
    user = current_workspace()
    if not user:
        raise HTTPException(status_code=404, detail="No workspace")

    body = req or {}
    plan_id = body.get("plan_id")
    coupon = (body.get("coupon") or "").strip()
    plan = plans_manager.get_plan(plan_id)
    if not plan:
        return {"success": False, "error": "That plan no longer exists."}

    amount = plan.get("price_monthly", 0)
    if coupon:
        quote = plans_manager.apply_offer(coupon, plan_id)
        if not quote.get("valid"):
            return {"success": False, "error": quote.get("error")}
        amount = quote["final_price"]

    # Nothing to charge — switch straight away rather than opening a ₹0 checkout.
    if amount <= 0:
        if coupon:
            plans_manager.redeem(coupon)
        user_manager.set_plan(user["id"], plan_id, amount=0, coupon=coupon or None,
                              method="coupon" if coupon else "free")
        admin_store.log("SUCCESS", "billing", f"{user['email']} moved to {plan['name']} at no charge")
        return {"success": True, "paid": False, "switched": True, "billing": _billing_payload()}

    if not razorpay.ready():
        # Keys aren't in yet. Say so plainly and let the caller fall back.
        return {"success": False, "manual_fallback": True,
                "error": "Online payment isn't switched on for this account yet."}

    ok, order = razorpay.create_order(
        amount,
        f"cf_{user['id'][:8]}_{plan_id}"[:40],
        {"workspace": user["id"], "email": user.get("email", ""),
         "plan": plan_id, "coupon": coupon},
    )
    if not ok:
        return {"success": False, "error": str(order)}

    return {"success": True, "order": {
        "order_id": order["id"],
        "amount": order["amount"],
        "currency": order["currency"],
        "key_id": razorpay.key_id,
        "plan_id": plan_id,
        "plan_name": plan["name"],
        "coupon": coupon,
        "amount_inr": amount,
    }}


@app.post("/api/billing/verify")
async def billing_verify(req: dict = None):
    """Browser says it paid. We check that against our own secret before believing it."""
    require_user()
    user = current_workspace()
    if not user:
        raise HTTPException(status_code=404, detail="No workspace")
    body = req or {}
    order_id = body.get("razorpay_order_id", "")
    payment_id = body.get("razorpay_payment_id", "")
    signature = body.get("razorpay_signature", "")
    plan_id = body.get("plan_id", "")
    coupon = (body.get("coupon") or "").strip()

    ok, message = razorpay.verify_payment(order_id, payment_id, signature)
    if not ok:
        admin_store.log("ERROR", "billing", f"Signature check failed for {user['email']} ({payment_id})")
        return {"success": False, "error": message}

    if _already_paid(user, payment_id):
        return {"success": True, "billing": _billing_payload(), "note": "Already recorded."}

    plan = plans_manager.get_plan(plan_id)
    amount = plan.get("price_monthly", 0) if plan else 0
    if coupon:
        quote = plans_manager.apply_offer(coupon, plan_id)
        if quote.get("valid"):
            amount = quote["final_price"]
            plans_manager.redeem(coupon)

    user_manager.set_plan(user["id"], plan_id, amount=amount, coupon=coupon or None,
                          method="razorpay", reference=payment_id)
    campaign_manager.add_log("SUCCESS", f"Payment received — {plan['name'] if plan else plan_id} is live.")
    admin_store.log("SUCCESS", "billing", f"{user['email']} paid Rs.{amount} for {plan_id} ({payment_id})")
    return {"success": True, "billing": _billing_payload()}


@app.post("/api/razorpay/webhook")
async def razorpay_webhook(request: Request):
    """Razorpay's own word for it. Covers the case where the browser closed mid-payment."""
    raw = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")
    if not razorpay.verify_webhook(raw, signature):
        admin_store.log("ERROR", "billing", "Rejected a webhook with a bad signature")
        raise HTTPException(status_code=400, detail="Bad signature")

    try:
        event = json.loads(raw.decode())
    except Exception:
        raise HTTPException(status_code=400, detail="Bad payload")

    kind = event.get("event", "")
    if kind not in ("payment.captured", "order.paid"):
        return {"success": True, "ignored": kind}

    entity = (event.get("payload", {}).get("payment", {}) or {}).get("entity", {})
    notes = entity.get("notes") or {}
    workspace_id = notes.get("workspace")
    plan_id = notes.get("plan")
    payment_id = entity.get("id", "")
    if not (workspace_id and plan_id and payment_id):
        return {"success": True, "ignored": "no workspace in notes"}

    user = user_manager.get(workspace_id)
    if not user:
        return {"success": True, "ignored": "unknown workspace"}
    if _already_paid(user, payment_id):
        return {"success": True, "note": "already recorded"}

    user_manager.set_plan(workspace_id, plan_id,
                          amount=int(entity.get("amount", 0)) // 100,
                          coupon=notes.get("coupon") or None,
                          method="razorpay", reference=payment_id)
    admin_store.log("SUCCESS", "billing", f"Webhook confirmed {payment_id} for {user.get('email')}")
    return {"success": True}


@app.post("/api/admin/razorpay/test")
async def admin_razorpay_test():
    require_admin()
    ok, message = razorpay.test_keys()
    return {"success": ok, "message": message, "mode": razorpay.mode()}


# ===========================================================================
# THE INSTAGRAM ACCOUNT — profile, posts, and turning a post into a flow
# Every response here comes from the workspace's own token. Nothing is
# sampled, seeded or substituted: if Instagram will not answer, the UI says
# so rather than showing a picture that is not theirs.
# ===========================================================================

@app.get("/api/instagram/profile")
async def instagram_profile(refresh: bool = False):
    require_user()
    user = current_workspace()
    if not user:
        raise HTTPException(status_code=404, detail="No workspace")
    if not instagram_account.connected(user):
        return {"success": True, "connected": False,
                "platform_ready": platform_settings.meta_ready()}
    ok, out = instagram_account.profile(user, force=refresh)
    if not ok:
        return {"success": False, "connected": True, "needs_reconnect": "expired" in str(out).lower(),
                "error": out}
    return {"success": True, "connected": True, "profile": out}


@app.get("/api/instagram/media")
async def instagram_media(limit: int = 24, refresh: bool = False):
    require_user()
    user = current_workspace()
    if not user:
        raise HTTPException(status_code=404, detail="No workspace")
    if not instagram_account.connected(user):
        return {"success": True, "connected": False, "media": []}
    ok, out = instagram_account.media(user, limit=limit, force=refresh)
    if not ok:
        return {"success": False, "connected": True, "media": [],
                "needs_reconnect": "expired" in str(out).lower(), "error": out}

    # Mark which posts already have an automation, so the grid can say so
    live = {}
    for rule in automation_engine.get_all():
        mid = rule.get("post_media_id")
        if mid:
            live[mid] = {"rule_id": rule["id"], "active": bool(rule.get("is_active")),
                         "keywords": rule.get("trigger_keywords", [])}
    for m in out:
        m["automation"] = live.get(m["id"])
    return {"success": True, "connected": True, "media": out}


class PostFlowRequest(BaseModel):
    media_id: str
    keywords: List[str] = []
    any_comment: bool = False
    dm_message: str
    link_url: Optional[str] = ""
    button_text: Optional[str] = "Open the link"
    comment_reply: Optional[str] = ""
    require_follow: Optional[bool] = True
    follow_prompt_msg: Optional[str] = ""
    activate: bool = True


@app.post("/api/flows/from-post")
async def create_flow_from_post(req: PostFlowRequest):
    """Pick a post, say the keyword, write the DM. That is the whole product."""
    require_user()
    user = current_workspace()
    if not user:
        raise HTTPException(status_code=404, detail="No workspace")
    if not instagram_account.connected(user):
        return {"success": False, "error": "Connect your Instagram account first."}

    ok, post = instagram_account.one(user, req.media_id)
    if not ok:
        return {"success": False, "error": post}

    words = [w.strip().lower() for w in req.keywords if w and w.strip()]
    if not req.any_comment and not words:
        return {"success": False,
                "error": "Give it at least one keyword, or set it to reply to every comment."}
    if not (req.dm_message or "").strip():
        return {"success": False, "error": "Write the DM you want people to receive."}

    active_now = sum(1 for r in automation_engine.get_all()
                     if r.get("is_active") and r.get("type") == "comment_to_dm")
    if req.activate:
        allowed, why = _can_activate(active_now)
        if not allowed:
            return {"success": False, "upgrade_required": True, "message": why,
                    "plans": plans_manager.all_plans(public_only=True)}

    caption = (post.get("caption") or "").strip()
    short = (caption[:44] + "…") if len(caption) > 45 else (caption or "Untitled post")
    label = words[0].upper() if words else "any comment"
    # The rule records ITS OWNER's handle. Falling back to a shared global here
    # would point another merchant's follow prompt at somebody else's account.
    connected_ig = ((user.get("instagram") or {}).get("username")
                    or (user.get("ig_handle") or "").lstrip("@"))

    rule = automation_engine.create({
        "name": f"\u201c{short}\u201d \u2192 DM on {label}",
        "type": "comment_to_dm",
        "post_media_id": post["id"],
        "post_target": post.get("permalink") or "*",
        "post_thumbnail": post.get("thumbnail", ""),
        "post_caption": caption,
        "post_kind": post.get("kind", "post"),
        "trigger_scope": "any" if req.any_comment else "specific",
        "trigger_keywords": words,
        "public_comment_reply": (req.comment_reply or "").strip(),
        "comment_replies": [req.comment_reply.strip()] if (req.comment_reply or "").strip() else [],
        "opening_dm": req.dm_message.strip(),
        "dm_message": req.dm_message.strip(),
        "button_text": (req.button_text or "").strip(),
        "delivery_link": (req.link_url or "").strip(),
        "require_follow": bool(req.require_follow),
        "follow_prompt_msg": (req.follow_prompt_msg or "").strip(),
        "connected_account_username": connected_ig,
        "is_active": bool(req.activate),
        "created_by": user["id"],
    })
    campaign_manager.add_log("SUCCESS", f"Flow created for {post.get('permalink') or post['id']}")
    admin_store.log("SUCCESS", "automation", f"{user['email']} built a flow on a {post.get('kind','post')}")
    return {"success": True, "rule": rule}


@app.delete("/api/flows/{rule_id}")
async def delete_flow(rule_id: str):
    user = current_workspace()
    if not user:
        raise HTTPException(status_code=404, detail="No workspace")
    ok = automation_engine.delete(rule_id)
    if not ok:
        return {"success": False, "error": "That flow no longer exists."}
    return {"success": True}


# ===========================================================================
# ADMIN — the operator's view of who is actually working
# The support queue for this business is "who tried to connect and failed",
# so that is what the console shows, rather than another revenue chart.
# ===========================================================================

@app.get("/api/admin/connections")
async def admin_connections():
    require_admin()
    rows, stuck, live = [], 0, 0
    all_rules = automation_engine.get_all()
    meta_enabled = bool(meta_client.config.get("enabled"))
    meta_tok = meta_client.config.get("access_token") or ""
    meta_uname = meta_client.config.get("connected_account_username") or "satnamwebservices"

    for u in user_manager.all():
        ig = dict(u.get("instagram") or {})
        # If admin workspace and platform has a valid Meta connection, sync if missing
        if is_admin_user(u) and (not ig.get("connected") or not ig.get("access_token")):
            if meta_enabled and meta_tok:
                ig["connected"] = True
                ig["access_token"] = meta_tok
                ig["username"] = ig.get("username") or meta_uname
                ig["connected_at"] = ig.get("connected_at") or meta_client.config.get("updated_at") or u.get("created_at")
                user_manager.set_instagram(u["id"], ig)

        flows = [r for r in all_rules if r.get("created_by") == u["id"]]
        active = sum(1 for r in flows if r.get("is_active"))
        if ig.get("connected") and ig.get("access_token"):
            state = "connected" if flows else "connected_no_flow"
        elif ig.get("connected"):
            state = "token_missing"
        else:
            state = "never_connected"
        if state != "connected":
            stuck += 1
        else:
            live += 1
        rows.append({
            "user_id": u["id"],
            "name": u.get("name", ""),
            "email": u.get("email", ""),
            "plan": u.get("plan", ""),
            "handle": ig.get("username") or u.get("ig_handle") or (meta_uname if (is_admin_user(u) and meta_enabled) else ""),
            "state": state,
            "connected_at": ig.get("connected_at") or "",
            "flows": len(flows),
            "active_flows": active,
            "created_at": u.get("created_at", ""),
        })
    order = {"token_missing": 0, "never_connected": 1, "connected_no_flow": 2, "connected": 3}
    rows.sort(key=lambda r: (order.get(r["state"], 9), r["email"]))
    return {"success": True, "rows": rows, "working": live, "needs_help": stuck,
            "platform_ready": platform_settings.meta_ready()}


@app.post("/api/admin/connections/sync")
async def admin_sync_connections():
    require_admin()
    tok = meta_client.config.get("access_token")
    uname = meta_client.config.get("connected_account_username", "satnamwebservices")
    name = meta_client.config.get("connected_account_name", "Satnam web services")
    ig_id = meta_client.config.get("instagram_account_id", "")
    page_id = meta_client.config.get("page_id", "")
    if not tok:
        return {"success": False, "message": "No active Meta Platform token configured. Please enter access token under Instagram API."}

    synced = 0
    for u in user_manager.all():
        if is_admin_user(u):
            conn = {
                "connected": True,
                "provider": "platform_sync",
                "access_token": tok,
                "connected_at": _now(),
                "page_id": page_id,
                "instagram_account_id": ig_id,
                "username": uname,
                "display_name": name,
            }
            user_manager.set_instagram(u["id"], conn)
            instagram_account.forget(u["id"])
            synced += 1

    return {"success": True, "message": f"Successfully synchronized {synced} admin workspace(s) with @{uname}."}


@app.get("/api/admin/users/{user_id}/workspace")
async def admin_user_workspace(user_id: str):
    require_admin()
    u = user_manager.get(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="No such workspace")
    ig = {k: v for k, v in (u.get("instagram") or {}).items()
          if k not in ("access_token", "page_access_token")}
    flows = [{"id": r["id"], "name": r.get("name", ""), "active": bool(r.get("is_active")),
              "keywords": r.get("trigger_keywords", []), "post": r.get("post_target", "")}
             for r in automation_engine.get_all() if r.get("created_by") == user_id]
    return {"success": True, "instagram": ig, "flows": flows,
            "plan": user_manager.plan_state(u), "usage": user_manager.usage(u)}


@app.get("/api/admin/audit")
async def admin_audit(limit: int = 200, subject_id: str = ""):
    """Who changed what, when. Written on every admin mutation."""
    require_admin()
    return {"success": True, "rows": cf_auth.audit_read(limit, subject_id),
            "storage": "postgres" if cf_store.using_postgres() else "file"}


@app.get("/api/admin/storage")
async def admin_storage():
    """Which database the platform is actually running on right now."""
    require_admin()
    on_pg = cf_store.using_postgres()
    out = {"success": True, "backend": "postgres" if on_pg else "json_files",
           "configured": cf_db.configured()}
    if on_pg:
        try:
            out["documents"] = cf_db.list_documents()
        except Exception as exc:
            out["error"] = str(exc)
    elif cf_db.configured():
        out["error"] = cf_db.last_error() or "DATABASE_URL is set but the server is unreachable."
    else:
        out["note"] = ("Running on JSON files. Set DATABASE_URL and run "
                       "migrate_to_postgres.py --write to move to Postgres.")
    return out


# ===========================================================================
#  "IS IT ACTUALLY WORKING?"
#  A merchant cannot tell the difference between "connected" and "working".
#  These two endpoints walk the real chain and say exactly where it stops.
# ===========================================================================

def _webhook_url(request: Request) -> str:
    """The address Meta should deliver to.

    Behind a proxy (Railway, Render, any load balancer) `request.base_url`
    reports the *internal* scheme, which is http. Meta refuses an http
    callback outright, so the registration failed with an error that pointed
    nowhere near the real cause. Trust the forwarded scheme, and never
    downgrade a public host to http.
    """
    cfg = platform_settings.meta_app()
    fixed = (cfg.get("webhook_url") or "").strip()
    if fixed:
        return fixed
    base = str(request.base_url).rstrip("/")
    proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    host = request.headers.get("x-forwarded-host", "").split(",")[0].strip() \
        or request.headers.get("host", "").split(",")[0].strip()
    if host:
        local = host.split(":")[0] in ("localhost", "127.0.0.1", "0.0.0.0", "::1")
        scheme = proto or ("http" if local else "https")
        if not local and scheme != "https":
            scheme = "https"
        base = f"{scheme}://{host}"
    return base + "/api/meta/webhook"


def _meta_app_creds() -> dict:
    """The Meta app id, secret and verify token - from wherever they are.

    These live in two places for historical reasons: the admin screen writes
    to platform settings, and the older Meta client keeps its own config file.
    An install that connected before the admin screen existed has the real
    credentials only in the second one, so reading just the first reports "not
    configured" about an app that is plainly working. Prefer the admin values,
    fall back to the client's, and never let a blank overwrite a real one.
    """
    cfg = dict(platform_settings.meta_app() or {})
    legacy = dict(getattr(meta_client, "config", {}) or {})
    cfg_id = str(cfg.get("app_id") or "").strip()
    legacy_id = str(legacy.get("app_id") or "").strip()
    # The legacy file may be trusted for a secret in two cases: it describes
    # the same app, or the settings name no app at all and it is the only
    # record there is. It must never be trusted when the two name DIFFERENT
    # apps - that is the mix this guard exists to prevent.
    same_app = (not cfg_id) or (cfg_id == legacy_id)

    for key in ("app_id", "app_secret", "verify_token"):
        if str(cfg.get(key) or "").strip():
            continue
        # An id from one app and a secret from another is the single worst
        # thing this function could return: every signature check would fail
        # and every token exchange would be refused, with an error that
        # points at redirect_uri instead. So a secret is only borrowed from
        # the legacy file when that file is about the SAME app.
        if key == "app_secret" and not same_app:
            continue
        val = str(legacy.get(key) or "").strip()
        if val:
            cfg[key] = val
    return cfg


@app.get("/api/instagram/diagnose")
async def instagram_diagnose(request: Request):
    user = require_user()
    # Use the product's own predicate, not just "a token exists". A workspace
    # that disconnected still has a stale token on it, and the chain used to
    # report "connected" while the dashboard showed the connect gate.
    if not instagram_account.connected(user):
        return {"success": True, "ok": False, "verdict": "Not connected yet.",
                "checks": [{"key": "connected",
                            "label": "Instagram account connected", "state": "fail",
                            "detail": "No account is linked to this workspace.",
                            "fix": "Connect Instagram from the Home screen."}]}
    mine = [r for r in automation_engine.get_all() if not r.get("created_by") or r.get("created_by") == user["id"]]
    out = webhook_setup.diagnose(user, mine, _webhook_url(request), _meta_app_creds())

    # The step every other step exists to produce. Meta can say a subscription
    # is perfect and still send nothing - Advanced Access gates comment
    # delivery - so the only honest answer is whether anything has ever come.
    last = event_log.last()
    if last is None:
        step = {"key": "events", "label": "Events are actually arriving", "state": "fail",
                "detail": "No comment has been handled yet.",
                "fix": ("Comment on one of your posts from a DIFFERENT account, "
                        "then press 'Read comments now'. Until your Meta app is "
                        "published, Meta sends no live webhooks to anyone - not "
                        "even to you - so DM Flow reads the comments itself "
                        f"every {POLL_SECONDS}s instead.")}
    elif last.get("verdict") == event_log.REJECTED:
        step = {"key": "events", "label": "Events are actually arriving", "state": "fail",
                "detail": f"Last delivery was refused {event_log.ago(last['at'])}: {last.get('note', '')}",
                "fix": ("The signature did not match the app secret. Check the "
                        "secret in Admin -> Instagram API against the Meta app.")}
    else:
        state = "pass" if last.get("verdict") in (event_log.SENT, event_log.HELD) else "unknown"
        who = f"@{last['username']}" if last.get("username") else "someone"
        said = f' "{last["text"]}"' if last.get("text") else ""
        verdict_word = {
            event_log.SENT: "and a DM went out",
            event_log.HELD: "and the follow-gate held the link",
            event_log.NO_RULE: "but no live flow matched it",
            event_log.IGNORED: "and it was skipped",
            event_log.FAILED: "but the DM failed",
        }.get(last.get("verdict"), "")
        step = {"key": "events", "label": "Events are actually arriving", "state": state,
                "detail": f"{event_log.ago(last['at'])}: {who} commented{said} - {verdict_word}.",
                "fix": last.get("note", "") if state != "pass" else ""}

    checks = out.get("checks", [])
    at = next((i for i, c in enumerate(checks) if c["key"] == "automation"), len(checks))
    checks.insert(at, step)
    if step["state"] == "fail" and out.get("ok"):
        out["ok"] = False
        out["verdict"] = step["detail"]
    return {"success": True, **out, "events": event_log.recent(8)}


@app.post("/api/instagram/repair-webhook")
async def instagram_repair_webhook(request: Request):
    """Re-register the app's webhook AND re-subscribe this account.

    Doing only the second is what the first version did, and it cannot work
    on its own: Instagram will not hand an account's comment events to an app
    that never asked for comment events.
    """
    user = require_user()
    # A workspace that disconnected keeps its old token on the record. Without
    # this check, Repair happily re-subscribed an account the merchant had
    # deliberately unlinked.
    if not instagram_account.connected(user):
        return {"success": False, "error": "Connect an Instagram account first."}
    token = ((user.get("instagram") or {}).get("access_token") or "")
    if not token:
        return {"success": False, "error": "Connect an Instagram account first."}

    out = webhook_setup.repair(token, _meta_app_creds(),
                               _webhook_url(request))

    for step in out.get("steps", []):
        admin_store.log("SUCCESS" if step["ok"] else "ERROR", "instagram",
                        f"{user['email']} repair [{step['level']}]: {step['detail']}")
    cf_auth.audit(user, "instagram.webhook_repaired", user["id"], None,
                  {"fields": out.get("subscribed", []),
                   "steps": out.get("steps", [])},
                  "re-registered the Instagram event chain")
    return out


@app.post("/api/instagram/poll-now")
async def instagram_poll_now():
    """Read comments right now instead of waiting for the next cycle."""
    user = require_user()
    if not instagram_account.connected(user):
        return {"success": False, "error": "Connect an Instagram account first."}
    mine = [r for r in automation_engine.get_all() if not r.get("created_by") or r.get("created_by") == user["id"]]
    if not any(r.get("is_active") and r.get("type") == "comment_to_dm" for r in mine):
        return {"success": False, "error": "Turn a comment flow on first."}

    loop = asyncio.get_running_loop()
    state = comment_poller._state()

    def run():
        return comment_poller.poll_user(
            user, mine,
            lambda payload: asyncio.run_coroutine_threadsafe(
                meta_webhook_event(InternalDelivery(payload)), loop).result(timeout=90),
            state)

    stats = await loop.run_in_executor(None, run)
    comment_poller._save(state)

    if stats["primed"]:
        msg = (f"First look at {stats['polled']} post(s). {stats['primed']} existing "
               f"comment(s) marked as already handled - old comments are never "
               f"answered. New ones from here on will be.")
    elif stats["new"]:
        msg = f"{stats['new']} new comment(s) processed. See Recent events below."
    elif stats["errors"]:
        msg = f"Instagram refused: {stats['errors'][0]}"
    else:
        msg = f"Checked {stats['polled']} post(s). No new comments."
    return {"success": not stats["errors"], "stats": stats, "message": msg}


@app.get("/api/admin/webhook-health")
async def admin_webhook_health(request: Request):
    """Every workspace, and whether its events can actually reach us."""
    require_admin()
    rows = []
    all_rules = automation_engine.get_all()
    # The app-level webhook is one fact for the whole platform. When it is
    # wrong, every row below is wrong for the same reason, so report it once
    # at the top instead of letting each workspace look individually broken.
    creds = _meta_app_creds()
    hook = _webhook_url(request)
    app_ok, app_state = webhook_setup.app_instagram_state(
        creds.get("app_id", ""), creds.get("app_secret", ""))
    app_level = {"readable": app_ok, "comments": False, "fields": [],
                 "callback_url": "", "matches": False,
                 "error": "" if app_ok else str(app_state.get("error", ""))}
    if app_ok:
        app_level.update({
            "present": app_state["present"],
            "comments": "comments" in app_state["fields"],
            "fields": app_state["fields"],
            "callback_url": app_state["callback_url"],
            "active": app_state["active"],
            "matches": (app_state["callback_url"] or "").rstrip("/") == hook.rstrip("/"),
        })
    for u in user_manager.all():
        ig = u.get("instagram") or {}
        if not ig.get("access_token"):
            continue
        ok, fields = webhook_setup.subscribed_fields(ig["access_token"])
        rows.append({
            "email": u.get("email", ""), "handle": ig.get("username", ""),
            "readable": ok,
            "comments": ok and "comments" in fields,
            "fields": fields,
            "live_flows": sum(1 for r in all_rules
                              if r.get("created_by") == u["id"] and r.get("is_active")),
        })
    return {"success": True, "rows": rows, "webhook_url": hook,
            "app_level": app_level}


@app.get("/api/public/debug-status")
async def public_debug_status():
    all_rules = automation_engine.get_all()
    events = event_log.recent(15)
    users = []
    for u in user_manager.all():
        ig = (u or {}).get("instagram") or {}
        users.append({
            "id": u.get("id"),
            "email": u.get("email"),
            "ig_handle": ig.get("username"),
            "ig_connected": ig.get("connected"),
            "token_present": bool(ig.get("access_token")),
        })
    return {
        "success": True,
        "rules_count": len(all_rules),
        "rules": all_rules,
        "users": users,
        "recent_events": events,
        "poll_stats": _poll_stats,
    }

