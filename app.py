import os
import json
from datetime import datetime
import asyncio
import threading
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse, Response, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.campaign_manager import CampaignManager
from core.spintax import SpintaxEngine
from core.automation_engine import AutomationEngine
from core.contacts_manager import ContactsManager
from core.comment_watcher import CommentWatcher
from core.post_provider import PostProvider
from core.meta_api import MetaAPIClient
from core.user_manager import UserManager
from core.admin_store import AdminStore
from core.plans_manager import PlansManager, FEATURE_KEYS, LIMIT_KEYS, UNLIMITED
from core.platform_settings import PlatformSettings
from core.meta_oauth import MetaOAuth
from core.insights import Insights
from core.razorpay_client import RazorpayClient

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(title="InstaDM ManyChat Suite", version="2.5.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core instances
campaign_manager = CampaignManager()
automation_engine = AutomationEngine()
contacts_manager = ContactsManager()
meta_client = MetaAPIClient()
plans_manager = PlansManager()
platform_settings = PlatformSettings()
user_manager = UserManager(plans=plans_manager)
admin_store = AdminStore()
meta_oauth = MetaOAuth(platform_settings)
insights = Insights(contacts_manager, automation_engine, campaign_manager)
razorpay = RazorpayClient(platform_settings)


def current_workspace():
    """The workspace the local dashboard is signed in as (first account for now)."""
    users = user_manager.all()
    return users[0] if users else None
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
    verify_token: Optional[str] = "manychat_secret_token_123"

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
    return _page("landing.html", "ConverFlow landing page missing")

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

@app.get("/deletion", response_class=HTMLResponse)
async def serve_deletion():
    return _page("deletion.html", "Data deletion instructions page missing")

# --- Product dashboard ---

@app.get("/app", response_class=HTMLResponse)
async def serve_app():
    return _page("index.html", "ConverFlow dashboard loading...")

@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard_alias():
    return _page("index.html", "ConverFlow dashboard loading...")

# --- Admin console ---

@app.get("/admin", response_class=HTMLResponse)
async def serve_admin():
    return _page("admin.html", "Admin console missing")

# --- System & Session Endpoints ---

@app.get("/api/status")
async def get_status():
    active_count = sum(1 for r in automation_engine.get_all() if r.get("is_active") and r.get("type") == "comment_to_dm")
    stats = campaign_manager.get_stats()
    stats["watcher_status"] = comment_watcher.status
    stats["active_reels_count"] = active_count
    stats["billing"] = _billing_payload()
    stats["meta_connected"] = bool(meta_client.config.get("enabled"))
    stats["meta_account"] = meta_client.config.get("connected_account_username", "")
    return {"success": True, "stats": stats}

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
    return {"success": True, "billing": _billing_payload(),
            "plans": plans_manager.all_plans(public_only=True)}

@app.post("/api/billing/upgrade")
async def upgrade_workspace(req: dict = None):
    """Upgrade the signed-in workspace. Body may carry {plan_id, coupon}."""
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
    user = current_workspace()
    if user:
        user_manager.start_trial(user["id"])
    return {"success": True, "billing": _billing_payload()}

@app.post("/api/billing/coupon")
async def preview_coupon(req: dict):
    """Price a plan with a coupon, without consuming it."""
    quote = plans_manager.apply_offer(req.get("code", ""), req.get("plan_id", ""))
    return {"success": quote.get("valid", False), **quote}

# --- Instagram Posts Endpoint ---

@app.get("/api/instagram/posts")
async def get_instagram_posts():
    posts = PostProvider.get_recent_posts(meta_client=meta_client)
    return {"success": True, "posts": posts}

# --- Official Meta Graph API & Webhook Endpoints ---

@app.get("/api/meta/config")
async def get_meta_config():
    cfg = dict(meta_client.config)
    token = cfg.get("access_token", "")
    if token:
        cfg["access_token_masked"] = token[:10] + "..." + token[-6:] if len(token) > 16 else "***"
    return {"success": True, "config": cfg}

@app.post("/api/meta/save")
async def save_meta_config(req: MetaConfigRequest):
    saved = meta_client.save_config(req.dict(exclude_unset=True))
    campaign_manager.add_log("SUCCESS", "Updated Facebook Developer / Meta API configuration.")
    return {"success": True, "config": saved}

@app.post("/api/meta/test")
async def test_meta_connection(req: MetaTestRequest):
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
        meta_client.config.get("verify_token", "manychat_secret_token_123"),
        platform_settings.meta_app().get("verify_token", "converflow_webhook_token"),
        "manychat_secret_token_123",
        "converflow_webhook_token"
    }
    if hub_mode == "subscribe" and hub_verify_token in valid_tokens:
        campaign_manager.add_log("SUCCESS", "Meta Webhook handshake verified successfully!")
        return Response(content=hub_challenge or "", media_type="text/plain")
    return Response(content="Verification token mismatch", status_code=403)

@app.post("/api/meta/webhook")
async def meta_webhook_event(request: Request):
    """
    Receives real-time incoming comments & messages from Meta Webhooks in 0.5s!
    """
    try:
        body = await request.json()
    except Exception:
        return {"status": "ignored"}

    entries = body.get("entry", [])
    processed_count = 0

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

                for rule in automation_engine.get_all():
                    if not rule.get("is_active") or rule.get("type") != "comment_to_dm":
                        continue
                    keywords = rule.get("trigger_keywords", ["*"])
                    if "*" in keywords or any(kw.lower() in text.lower() for kw in keywords):
                        # Public comment reply
                        pub_reply = rule.get("public_comment_reply")
                        if pub_reply and comment_id:
                            actual_reply = SpintaxEngine.spin(pub_reply)
                            meta_client.reply_to_comment(comment_id, actual_reply)

                        # Instant direct message with variable replacement
                        raw_dm = rule.get("opening_dm") or rule.get("dm_message", "")
                        dm_msg = raw_dm.replace("{name}", username).replace("{first_name}", username).replace("{username}", username)
                        dm_msg = SpintaxEngine.spin(dm_msg)
                        btn_text = rule.get("button_text")
                        deliv_link = rule.get("delivery_link")
                        if user_id:
                            meta_client.send_instagram_dm(user_id, dm_msg, btn_text, deliv_link)

                        # Record CRM lead
                        contacts_manager.upsert_contact(
                            username=username,
                            name=username,
                            source=f"Meta Webhook (Reel {media_id})",
                            tags=rule.get("tags", ["Meta Lead"]),
                            interaction_text=text
                        )
                        processed_count += 1
                        campaign_manager.add_log("SUCCESS", f"⚡ Meta Webhook: Automated reply sent to @{username} on Reel ({text})")
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
                        meta_client.send_instagram_dm(sender_id, dm_msg, btn_text, deliv_link)
                        processed_count += 1
                        campaign_manager.add_log("SUCCESS", f"⚡ Meta Webhook: Auto DM sent to sender {sender_id} (keyword: {msg_text})")
                        break

    return {"status": "ok", "processed": processed_count}

# --- ManyChat Wizard Publish Endpoint ---

@app.post("/api/wizard/publish")
async def publish_wizard_automation(req: WizardPublishRequest):
    """
    Create an automation and switch it on.

    The limit check reads the live plan catalogue, not the old single-plan
    BillingManager — that one still believed in "Free Trial, 1 reel, Rs.299/mo"
    and blocked workspaces on unlimited plans with an upsell for a plan that no
    longer exists.
    """
    active_count = sum(1 for r in automation_engine.get_all()
                       if r.get("is_active") and r.get("type") == "comment_to_dm")

    user = current_workspace()
    if user:
        allowed, limit_msg = user_manager.can_activate_automation(user, active_count)
        if not allowed:
            state = user_manager.plan_state(user)
            nxt = user_manager._next_plan_up(state["plan_id"])
            return {
                "success": False,
                "upgrade_required": True,
                "error": limit_msg,
                "message": limit_msg,
                "plan": state["plan_name"],
                "suggest_plan": nxt["id"] if nxt else None,
                "price": nxt["price_monthly"] if nxt else None,
            }

    # Format public comment reply using spintax from the multiple variations
    public_spintax = ""
    if req.reply_to_comment and req.comment_replies:
        cleaned_replies = [r.strip() for r in req.comment_replies if r.strip()]
        if cleaned_replies:
            public_spintax = "{" + "|".join(cleaned_replies) + "}"

    rule_data = {
        "name": req.name,
        "type": "comment_to_dm",
        "post_target": req.post_target,
        "post_thumbnail": req.post_thumbnail,
        "post_caption": req.post_caption,
        "trigger_keywords": req.trigger_keywords if req.trigger_scope == "specific" and req.trigger_keywords else ["*"],
        "public_comment_reply": public_spintax,
        "comment_replies": req.comment_replies,
        "opening_dm": req.opening_dm,
        "button_text": req.button_text,
        "delivery_link": req.delivery_link,
        "dm_message": f"{req.opening_dm}\n\n👉 {req.delivery_link}" if req.delivery_link else req.opening_dm,
        "require_follow": req.require_follow,
        "ask_email": req.ask_email,
        "tags": req.tags or ["Reel Lead", "ManyChat Flow"],
        "is_active": True
    }

    created = automation_engine.create(rule_data)
    campaign_manager.add_log("SUCCESS", f"Published ManyChat Automation: '{req.name}' for {req.post_target}")
    return {"success": True, "upgrade_required": False, "rule": created}


@app.post("/api/check-login")
async def check_login():
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, campaign_manager.browser_manager.check_login_status)
    campaign_manager.add_log(
        "SUCCESS" if result.get("logged_in") else "WARN",
        f"Instagram session check: {result.get('message')}"
    )
    return result

@app.post("/api/open-login")
async def open_login():
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

# --- ManyChat Automations Endpoints ---

@app.get("/api/automations")
async def list_automations():
    rules = automation_engine.get_all()
    return {"success": True, "automations": rules}

@app.post("/api/automations")
async def save_automation(req: AutomationRuleRequest):
    data = req.dict()
    rule_id = data.get("id")
    if rule_id and automation_engine.get_by_id(rule_id):
        updated = automation_engine.update(rule_id, data)
        campaign_manager.add_log("INFO", f"Updated ManyChat automation rule: '{data['name']}'")
        return {"success": True, "automation": updated}
    else:
        created = automation_engine.create(data)
        campaign_manager.add_log("SUCCESS", f"Created new ManyChat automation rule: '{data['name']}'")
        return {"success": True, "automation": created}

@app.post("/api/automations/{rule_id}/toggle")
async def toggle_automation(rule_id: str):
    rule = automation_engine.get_by_id(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    is_currently_active = rule.get("is_active", False)
    if not is_currently_active and rule.get("type") == "comment_to_dm":
        # Attempting to activate: check limit
        active_count = sum(1 for r in automation_engine.get_all()
                           if r.get("is_active") and r.get("type") == "comment_to_dm")
        user = current_workspace()
        if user:
            allowed, limit_msg = user_manager.can_activate_automation(user, active_count)
            if not allowed:
                state = user_manager.plan_state(user)
                nxt = user_manager._next_plan_up(state["plan_id"])
                return {
                    "success": False,
                    "upgrade_required": True,
                    "error": limit_msg,
                    "message": limit_msg,
                    "plan": state["plan_name"],
                    "suggest_plan": nxt["id"] if nxt else None,
                    "price": nxt["price_monthly"] if nxt else None,
                }

    new_state = automation_engine.toggle_active(rule_id)
    state_str = "ENABLED" if new_state else "DISABLED"
    campaign_manager.add_log("INFO", f"Automation rule {rule_id} is now {state_str}")
    return {"success": True, "is_active": new_state}


@app.delete("/api/automations/{rule_id}")
async def delete_automation(rule_id: str):
    ok = automation_engine.delete(rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Rule not found")
    campaign_manager.add_log("WARN", f"Deleted automation rule {rule_id}")
    return {"success": True}

# --- ManyChat Flow Simulator Endpoint ---

@app.post("/api/simulator/send")
async def simulate_message(req: SimulatorMessageRequest):
    """
    Simulates ManyChat trigger matching for comments or DMs in the interactive phone preview.
    """
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
    contacts = contacts_manager.get_all(search=search, tag=tag)
    return {"success": True, "contacts": contacts, "total": len(contacts)}

@app.get("/api/contacts/export")
async def export_contacts():
    csv_data = contacts_manager.export_csv()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="manychat_contacts.csv"'}
    )

# --- Comment Watcher Background Task ---

@app.post("/api/watcher/start")
async def start_watcher(req: WatcherStartRequest):
    ok = comment_watcher.start(post_url=req.post_url, interval=req.interval or 60)
    if not ok:
        raise HTTPException(status_code=400, detail="Watcher is already running.")
    return {"success": True, "status": comment_watcher.status}

@app.post("/api/watcher/stop")
async def stop_watcher():
    ok = comment_watcher.stop()
    return {"success": ok, "status": comment_watcher.status}

# --- Broadcast / Outbound Campaign Endpoints ---

@app.post("/api/targets/load-text")
async def load_targets_text(req: LoadTextTargetsRequest):
    count = campaign_manager.load_targets_from_text(req.text)
    return {"success": True, "count": count, "total": len(campaign_manager.targets)}

@app.post("/api/targets/upload-csv")
async def upload_targets_csv(file: UploadFile = File(...)):
    content = await file.read()
    text = content.decode("utf-8", errors="replace")
    count = campaign_manager.load_targets_from_csv(text)
    return {"success": True, "count": count, "total": len(campaign_manager.targets)}

@app.get("/api/targets")
async def get_targets():
    return {
        "targets": [t.to_dict() for t in campaign_manager.targets],
        "total": len(campaign_manager.targets)
    }

@app.post("/api/targets/clear")
async def clear_targets():
    ok = campaign_manager.clear_targets()
    if not ok:
        raise HTTPException(status_code=400, detail="Cannot clear targets while campaign is running.")
    return {"success": True}

@app.post("/api/spintax/preview")
async def preview_spintax(req: SpintaxPreviewRequest):
    previews = SpintaxEngine.generate_previews(req.template, count=5)
    return {"success": True, "previews": previews}

@app.post("/api/campaign/start")
async def start_campaign(req: CampaignSettingsRequest):
    settings = req.dict()
    ok = campaign_manager.start_campaign(settings)
    if not ok:
        raise HTTPException(status_code=400, detail="Could not start campaign. Check if already running or if target queue is empty.")
    return {"success": True, "message": "Campaign started successfully"}

@app.post("/api/campaign/pause")
async def pause_campaign():
    ok = campaign_manager.pause_campaign()
    return {"success": ok}

@app.post("/api/campaign/resume")
async def resume_campaign():
    ok = campaign_manager.resume_campaign()
    return {"success": ok}

@app.post("/api/campaign/stop")
async def stop_campaign():
    ok = campaign_manager.stop_campaign()
    return {"success": ok}

@app.get("/api/campaign/export")
async def export_campaign():
    csv_data = campaign_manager.export_csv()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="instagram_dm_campaign.csv"'}
    )

@app.get("/api/logs/stream")
async def stream_logs():
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
    verify_token: Optional[str] = "manychat_secret_token_123"


@app.get("/api/meta/config")
async def get_meta_config():
    cfg = meta_client.config
    token = cfg.get("access_token", "")
    masked_token = (token[:8] + "..." + token[-4:]) if len(token) > 12 else ("***" if token else "")
    return {
        "enabled": cfg.get("enabled", False),
        "connected_account_name": cfg.get("connected_account_name", ""),
        "connected_account_username": cfg.get("connected_account_username", ""),
        "instagram_account_id": cfg.get("instagram_account_id", ""),
        "page_id": cfg.get("page_id", ""),
        "verify_token": cfg.get("verify_token", "manychat_secret_token_123"),
        "has_token": bool(token),
        "masked_token": masked_token
    }


@app.post("/api/meta/connect")
async def connect_meta(req: MetaConnectRequest):
    result = meta_client.test_connection(req.access_token)
    if result.get("success"):
        if req.verify_token:
            meta_client.save_config({"verify_token": req.verify_token})
        campaign_manager.add_log("INFO", f"Official Meta Graph API connected to @{result['account']['ig_username']}")
    return result


@app.post("/api/meta/disconnect")
async def disconnect_meta():
    meta_client.save_config({
        "enabled": False,
        "access_token": "",
        "page_id": "",
        "instagram_account_id": "",
        "connected_account_name": "",
        "connected_account_username": ""
    })
    campaign_manager.add_log("INFO", "Meta Graph API disconnected.")
    return {"success": True}


@app.get("/api/meta/webhook")
async def verify_meta_webhook(request: Request):
    """
    Handles Meta Webhook Verification challenge
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    expected_token = meta_client.config.get("verify_token", "manychat_secret_token_123")
    if mode == "subscribe" and token == expected_token:
        return PlainTextResponse(content=challenge or "")
    raise HTTPException(status_code=403, detail="Verification token mismatch")


@app.post("/api/meta/webhook")
async def receive_meta_webhook(request: Request):
    """
    Receives real-time Meta comments / messages webhook event (0.5s auto-responder)
    """
    try:
        data = await request.json()
    except Exception:
        return {"status": "ignored"}

    entries = data.get("entry", [])
    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            field = change.get("field")
            val = change.get("value", {})
            if field == "comments":
                comment_text = val.get("text", "")
                comment_id = val.get("id", "")
                sender = val.get("from", {})
                username = sender.get("username", "")
                user_id = sender.get("id", "")

                match = automation_engine.match_comment(comment_text, username=username)
                if match:
                    if match.get("public_reply") and comment_id:
                        meta_client.reply_to_comment(comment_id, match["public_reply"])
                    if match.get("dm_reply") and user_id:
                        meta_client.send_instagram_dm(
                            recipient_ig_id=user_id,
                            message_text=match["dm_reply"],
                            button_text=match.get("button_text"),
                            button_url=match.get("button_url")
                        )
                    contacts_manager.record_interaction(
                        username=username or user_id,
                        source="Meta Webhook Comment",
                        new_tags=match.get("tags", [])
                    )
    return {"status": "ok"}



# =============================================================================
#  AUTH  —  signup / login against the multi-user store
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
    campaign_manager.add_log("SUCCESS", f"New ConverFlow workspace: {result['email']}")
    return {"success": True, "user": user_manager.public(result)}


@app.post("/api/auth/login")
async def auth_login(req: LoginRequest):
    ok, result = user_manager.authenticate(req.email, req.password)
    if not ok:
        return {"success": False, "error": result}
    return {"success": True, "user": user_manager.public(result)}


@app.get("/api/auth/announcement")
async def auth_announcement():
    """Latest published notice, for the in-app ribbon."""
    return {"success": True, "announcement": admin_store.latest_published()}


# =============================================================================
#  ADMIN  —  business control room
# =============================================================================

@app.get("/api/admin/overview")
async def admin_overview():
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
    return {"success": True, "users": user_manager.list_public(search=search, plan=plan, status=status)}


@app.get("/api/admin/users/{user_id}")
async def admin_user_detail(user_id: str):
    user = user_manager.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, "user": user_manager.public(user)}


@app.post("/api/admin/users")
async def admin_create_user(req: AdminUserRequest):
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
    user = user_manager.update(user_id, req.dict(exclude_unset=True))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    admin_store.log("INFO", "admin", f"Workspace details updated: {user['email']}")
    return {"success": True, "user": user_manager.public(user)}


@app.post("/api/admin/users/{user_id}/plan")
async def admin_set_plan(user_id: str, req: PlanChangeRequest):
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
    return {"success": True, "user": user_manager.public(user)}


@app.post("/api/admin/users/{user_id}/extend")
async def admin_extend_trial(user_id: str, req: ExtendTrialRequest):
    user = user_manager.extend_trial(user_id, req.days)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    admin_store.log("INFO", "billing", f"Trial extended by {req.days} days for {user['email']}")
    return {"success": True, "user": user_manager.public(user)}


@app.post("/api/admin/users/{user_id}/toggle")
async def admin_toggle_user(user_id: str):
    user = user_manager.toggle_status(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    admin_store.log("WARN" if user["status"] == "suspended" else "SUCCESS", "admin",
                    f"{user['email']} is now {user['status']}")
    return {"success": True, "user": user_manager.public(user)}


@app.delete("/api/admin/users/{user_id}")
async def admin_delete_user(user_id: str):
    user = user_manager.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    email = user["email"]
    user_manager.delete(user_id)
    admin_store.log("WARN", "admin", f"Workspace deleted: {email}")
    return {"success": True}


@app.get("/api/admin/events")
async def admin_events(level: str = "all", limit: int = 60):
    return {
        "success": True,
        "events": admin_store.list_events(level=level, limit=limit),
        "health": admin_store.health_summary(),
    }


@app.get("/api/admin/announcements")
async def admin_list_announcements():
    return {"success": True, "announcements": admin_store.list_announcements()}


@app.post("/api/admin/announcements")
async def admin_add_announcement(req: AnnouncementRequest):
    item = admin_store.add_announcement(
        title=req.title, body=req.body,
        audience=req.audience or "all", level=req.level or "update"
    )
    return {"success": True, "announcement": item}


@app.delete("/api/admin/announcements/{ann_id}")
async def admin_delete_announcement(ann_id: str):
    ok = admin_store.delete_announcement(ann_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return {"success": True}


@app.get("/api/admin/export/users")
async def admin_export_users():
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
#  PUBLIC  —  what the marketing site and dashboard may read
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
#  ADMIN  —  plans & pricing
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
    return {
        "success": True,
        "plans": plans_manager.all_plans(),
        "schema": plans_manager.schema(),
        "usage": {p["id"]: sum(1 for u in user_manager.all() if u.get("plan") == p["id"])
                  for p in plans_manager.all_plans()},
    }


@app.post("/api/admin/plans")
async def admin_save_plan(req: PlanPayload):
    ok, result = plans_manager.save_plan(req.dict(exclude_unset=True))
    if not ok:
        return {"success": False, "error": result}
    admin_store.log("INFO", "plans", f"Plan saved: {result['name']} (Rs.{result['price_monthly']}/mo)")
    return {"success": True, "plan": result}


@app.delete("/api/admin/plans/{plan_id}")
async def admin_delete_plan(plan_id: str):
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
    plans_manager.reorder(req.get("order", []))
    return {"success": True, "plans": plans_manager.all_plans()}


# =============================================================================
#  ADMIN  —  offers & coupons
# =============================================================================

@app.get("/api/admin/offers")
async def admin_list_offers():
    return {"success": True, "offers": plans_manager.all_offers(),
            "schema": plans_manager.schema(),
            "plans": [{"id": p["id"], "name": p["name"]} for p in plans_manager.all_plans()]}


@app.post("/api/admin/offers")
async def admin_save_offer(req: OfferPayload):
    ok, result = plans_manager.save_offer(req.dict(exclude_unset=True))
    if not ok:
        return {"success": False, "error": result}
    admin_store.log("SUCCESS", "offers", f"Coupon {result['code']} saved")
    return {"success": True, "offer": result}


@app.post("/api/admin/offers/{offer_id}/toggle")
async def admin_toggle_offer(offer_id: str):
    offer = plans_manager.toggle_offer(offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    return {"success": True, "offer": offer}


@app.delete("/api/admin/offers/{offer_id}")
async def admin_delete_offer(offer_id: str):
    if not plans_manager.delete_offer(offer_id):
        raise HTTPException(status_code=404, detail="Offer not found")
    return {"success": True}


@app.post("/api/admin/offers/check")
async def admin_check_offer(req: CouponCheck):
    return {"success": True, "result": plans_manager.apply_offer(req.code, req.plan_id)}


# =============================================================================
#  ADMIN  —  platform settings, Meta app & templates
# =============================================================================

@app.get("/api/admin/settings")
async def admin_get_settings():
    return {"success": True, "settings": platform_settings.public(),
            "default_scopes": platform_settings.meta_app().get("scopes", [])}


@app.post("/api/admin/settings")
async def admin_save_settings(req: SettingsPayload):
    section = platform_settings.update_section(req.section, req.values)
    admin_store.log("INFO", "settings", f"Updated {req.section} settings")
    return {"success": True, "section": req.section, "values": platform_settings.public().get(req.section, section)}


@app.post("/api/admin/meta-app/test")
async def admin_test_meta_app():
    result = meta_oauth.test_app()
    admin_store.log("SUCCESS" if result.get("success") else "ERROR", "instagram",
                    result.get("message") or result.get("error", "Meta app test"))
    return result


@app.get("/api/admin/templates")
async def admin_list_templates():
    return {"success": True, "templates": platform_settings.list_templates()}


@app.patch("/api/admin/templates/{template_id}")
async def admin_save_template(template_id: str, req: TemplatePayload):
    tpl = platform_settings.save_template(template_id, req.dict(exclude_unset=True))
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"success": True, "template": tpl}


@app.get("/api/admin/templates/{template_id}/preview")
async def admin_preview_template(template_id: str):
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
#  INSTAGRAM CONNECT  —  one Meta app, every customer connects themselves
# =============================================================================

@app.get("/api/instagram/status")
async def instagram_status(user_id: Optional[str] = None):
    user = user_manager.get(user_id) if user_id else current_workspace()
    if not user:
        raise HTTPException(status_code=404, detail="No workspace")
    ig = {k: v for k, v in user.get("instagram", {}).items()
          if k not in ("access_token", "page_access_token")}
    return {"success": True, "instagram": ig,
            "platform_ready": platform_settings.meta_ready(),
            "allow_browser_login": platform_settings.section("flags").get("allow_browser_login", True)}


@app.get("/api/instagram/connect")
async def instagram_connect(user_id: Optional[str] = None):
    user = user_manager.get(user_id) if user_id else current_workspace()
    if not user:
        raise HTTPException(status_code=404, detail="No workspace")
    ok, url = meta_oauth.consent_url(user["id"])
    if not ok:
        return {"success": False, "error": url}
    return {"success": True, "url": url}


@app.post("/api/instagram/connect-token")
async def instagram_connect_token(req: MetaTestRequest, user_id: Optional[str] = None):
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
async def instagram_callback(code: Optional[str] = None, state: Optional[str] = None,
                             error: Optional[str] = None,
                             error_description: Optional[str] = None):
    """Meta redirects the customer's browser here after they approve."""
    def page(title: str, message: str, ok: bool) -> HTMLResponse:
        colour = "#00824b" if ok else "#e5484d"
        icon = "M20 6L9 17l-5-5" if ok else "M18 6L6 18M6 6l12 12"
        return HTMLResponse(f"""
<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — ConverFlow</title>
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
  a{{display:inline-block;background:#00824b;color:#fff;text-decoration:none;font-weight:700;
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

    ok, result = meta_oauth.complete(code, state)
    if not ok:
        admin_store.log("ERROR", "instagram", f"Connect failed: {result}")
        return page("Could not connect", str(result), False)

    user = user_manager.set_instagram(result["user_id"], result["connection"])
    conn = result["connection"]
    if conn.get("page_id") and conn.get("page_access_token"):
        meta_oauth.subscribe_webhook(conn["page_id"], conn["page_access_token"])

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
    user = user_manager.get(user_id) if user_id else current_workspace()
    if not user:
        raise HTTPException(status_code=404, detail="No workspace")
    user_manager.disconnect_instagram(user["id"])
    admin_store.log("WARN", "instagram", f"{user['email']} disconnected their Instagram account")
    return {"success": True}


# =============================================================================
#  INSIGHTS  —  the numbers rivals stop short of
# =============================================================================

@app.get("/api/insights")
async def get_insights():
    """Funnel, safety headroom, reply speed and system health in one call."""
    user = current_workspace()
    watcher = comment_watcher.status
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


# =============================================================================
#  PAYMENTS  —  Razorpay
#  A plan only changes after a signature we computed ourselves matches, or
#  after a signed webhook confirms it. The browser is never trusted on its own.
# =============================================================================

class CheckoutRequest(BaseModel):
    plan_id: str
    coupon: Optional[str] = None

class VerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    plan_id: str
    coupon: Optional[str] = None
    amount: Optional[int] = None


@app.get("/api/billing/gateway")
async def billing_gateway():
    """What the checkout button should do — pay, or fall back to manual."""
    return {
        "success": True,
        "ready": razorpay.ready(),
        "mode": razorpay.mode(),
        "key_id": razorpay.key_id if razorpay.ready() else "",
        "currency": platform_settings.section("billing").get("currency", "INR"),
    }


@app.post("/api/billing/checkout")
async def billing_checkout(req: CheckoutRequest):
    user = current_workspace()
    if not user:
        raise HTTPException(status_code=404, detail="No workspace")
    plan = plans_manager.get_plan(req.plan_id)
    if not plan:
        return {"success": False, "error": "That plan does not exist."}

    amount = plan.get("price_monthly", 0)
    if req.coupon:
        quote = plans_manager.apply_offer(req.coupon, req.plan_id)
        if not quote.get("valid"):
            return {"success": False, "error": quote.get("error")}
        amount = quote["final_price"]

    if amount <= 0:
        # free plan, or a coupon that covers the whole month — no gateway needed
        user_manager.set_plan(user["id"], req.plan_id, record_payment=False, coupon=req.coupon)
        admin_store.log("SUCCESS", "billing", f"{user['email']} moved to {plan['name']} at no charge")
        return {"success": True, "free": True, "billing": _billing_payload()}

    ok, order = razorpay.create_order(
        amount_inr=amount,
        receipt=f"cf_{user['id'][-10:]}_{req.plan_id}",
        notes={"workspace": user["id"], "plan": req.plan_id, "email": user["email"]},
    )
    if not ok:
        return {"success": False, "error": order, "manual_fallback": True}

    return {
        "success": True,
        "order": order,
        "plan": {"id": plan["id"], "name": plan["name"]},
        "amount_inr": amount,
        "prefill": {"name": user.get("name", ""), "email": user.get("email", "")},
        "brand": platform_settings.section("brand").get("name", "ConverFlow"),
    }


@app.post("/api/billing/verify")
async def billing_verify(req: VerifyRequest):
    user = current_workspace()
    if not user:
        raise HTTPException(status_code=404, detail="No workspace")

    ok, message = razorpay.verify_payment(
        req.razorpay_order_id, req.razorpay_payment_id, req.razorpay_signature)
    if not ok:
        admin_store.log("ERROR", "billing",
                        f"Signature mismatch on {req.razorpay_payment_id} for {user['email']}")
        return {"success": False, "error": message}

    plan = plans_manager.get_plan(req.plan_id)
    amount = req.amount if req.amount is not None else (plan or {}).get("price_monthly", 0)
    user_manager.set_plan(user["id"], req.plan_id, record_payment=False, coupon=req.coupon)

    updated = user_manager.get(user["id"])
    updated.setdefault("payments", []).append({
        "id": req.razorpay_payment_id,
        "order_id": req.razorpay_order_id,
        "date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "amount": amount,
        "plan": req.plan_id,
        "method": "razorpay",
        "coupon": req.coupon,
        "status": "paid",
    })
    user_manager._save()

    if req.coupon:
        plans_manager.redeem(req.coupon)

    admin_store.log("SUCCESS", "billing",
                    f"Razorpay payment {req.razorpay_payment_id} — {user['email']} on {(plan or {}).get('name')} (Rs.{amount})")
    campaign_manager.add_log("SUCCESS", f"Payment received. You're on {(plan or {}).get('name')}.")
    return {"success": True, "billing": _billing_payload()}


@app.post("/api/razorpay/webhook")
async def razorpay_webhook(request: Request):
    """Razorpay's own confirmation. Runs even if the browser closed mid-payment."""
    raw = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")
    if not razorpay.verify_webhook(raw, signature):
        admin_store.log("WARN", "billing", "Rejected a webhook with a bad signature")
        raise HTTPException(status_code=400, detail="Bad signature")

    try:
        event = json.loads(raw.decode())
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed payload")

    if event.get("event") in ("payment.captured", "order.paid"):
        payment = (event.get("payload", {}).get("payment", {}) or {}).get("entity", {})
        notes = payment.get("notes", {}) or {}
        workspace_id, plan_id = notes.get("workspace"), notes.get("plan")
        amount = int(payment.get("amount", 0)) // 100

        user = user_manager.get(workspace_id) if workspace_id else None
        if user and plan_id:
            already = any(p.get("id") == payment.get("id") for p in user.get("payments", []))
            if not already:
                user_manager.set_plan(user["id"], plan_id, record_payment=False)
                user = user_manager.get(user["id"])
                user.setdefault("payments", []).append({
                    "id": payment.get("id"),
                    "order_id": payment.get("order_id"),
                    "date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                    "amount": amount, "plan": plan_id,
                    "method": "razorpay", "status": "paid",
                })
                user_manager._save()
                admin_store.log("SUCCESS", "billing",
                                f"Webhook confirmed {payment.get('id')} for {user['email']}")
    return {"status": "ok"}


@app.post("/api/admin/razorpay/test")
async def admin_test_razorpay():
    result = razorpay.test_keys()
    admin_store.log("SUCCESS" if result.get("success") else "ERROR", "billing",
                    result.get("message") or result.get("error", "Razorpay key check"))
    return result
