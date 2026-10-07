"""
DM Flow - billing with Razorpay.

How a purchase works (Razorpay Standard Checkout, one payment per period):
  1. /api/billing/checkout   we price the plan (coupon, GST) and create a
                             Razorpay Order for the exact amount, in paise.
  2. The browser opens Razorpay Checkout (UPI, cards, net banking, wallets).
  3. /api/billing/verify     the browser hands back order_id, payment_id and
                             signature; we check the HMAC with the key secret.
  4. /api/razorpay/webhook   Razorpay also tells us server-to-server
                             (payment.captured / order.paid), so a closed tab
                             never loses a payment.
Steps 3 and 4 both call `mark_paid`, which is idempotent: the plan is
activated exactly once, whichever arrives first.

Renewals: paying again before the end adds the new period on top of the days
left. A sweep (hourly) emails a reminder a few days before the end and moves
expired workspaces to Free.

No SDK - the two Razorpay calls are plain HTTPS with basic auth.
"""

import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

from dmflow import db, email_service, settings

log = logging.getLogger("dmflow.billing")
API = "https://api.razorpay.com/v1"
PERIOD = {"monthly": 30 * 86400, "yearly": 365 * 86400}
YES = ("1", "true", "yes", "on")


# ------------------------------------------------------------------ config
def keys() -> Tuple[str, str]:
    return settings.get("razorpay_key_id").strip(), settings.get("razorpay_key_secret").strip()


def enabled() -> bool:
    kid, sec = keys()
    return bool(settings.get("razorpay_enabled") in YES and kid and sec)


def mode() -> str:
    kid, _ = keys()
    return "test" if kid.startswith("rzp_test_") else ("live" if kid.startswith("rzp_live_") else "")


def tax_percent() -> float:
    try:
        return max(0.0, float(settings.get("tax_percent") or 0))
    except ValueError:
        return 0.0


# ------------------------------------------------------------------ pricing
def _offer(code: str, plan_id: str) -> Tuple[Optional[Dict[str, Any]], str]:
    code = (code or "").strip().upper()
    if not code:
        return None, ""
    off = db.one("SELECT * FROM dm_offers WHERE code = ? AND is_active = 1", (code,))
    if not off:
        return None, "Invalid or inactive coupon code."
    if off["valid_until"] and off["valid_until"] < db.now():
        return None, "This coupon code has expired."
    if off["max_uses"] != -1 and off["used_count"] >= off["max_uses"]:
        return None, "This coupon code has reached its usage limit."
    if off["applicable_plans"] != "all":
        allowed = [p.strip() for p in off["applicable_plans"].split(",")]
        if plan_id not in allowed:
            return None, "This coupon is not valid for the selected plan."
    return off, ""


def quote(plan_id: str, cycle: str, coupon: str = "") -> Dict[str, Any]:
    """Exact price in paise. Raises ValueError with a message for the customer."""
    cycle = "yearly" if cycle == "yearly" else "monthly"
    plan = next((p for p in settings.plans() if p.get("id") == plan_id), None)
    if not plan or not plan.get("is_active", True) or plan.get("is_hidden"):
        raise ValueError("That plan is not available.")
    if plan_id == "lifetime" or plan.get("id") == "free":
        raise ValueError("That plan cannot be bought.")
    price = float(plan.get("price_yearly" if cycle == "yearly" else "price_monthly") or 0)
    if price <= 0:
        raise ValueError("This plan has no price set for that billing cycle.")
    base = int(round(price * 100))
    discount, lifetime, code = 0, False, ""
    off, err = _offer(coupon, plan_id)
    if err:
        raise ValueError(err)
    if off:
        code = off["code"]
        t, v = off["discount_type"], float(off["discount_val"] or 0)
        if t == "percentage":
            discount = int(round(base * min(100.0, max(0.0, v)) / 100))
        elif t == "flat":
            discount = int(round(v * 100))
        elif t == "lifetime":
            discount, lifetime = base, True
    discount = min(base, max(0, discount))
    taxable = base - discount
    pct = tax_percent()
    tax = int(round(taxable * pct / 100))
    total = taxable + tax
    if 0 < total < 100:          # Razorpay's minimum charge is ₹1
        raise ValueError("The amount after discount is below ₹1.")
    return {"plan_id": plan_id, "plan_name": plan.get("name") or plan_id, "cycle": cycle,
            "currency": (settings.get("currency") or "INR").upper(),
            "base_amount": base, "discount": discount, "tax": tax, "tax_percent": pct,
            "amount": total, "coupon": code, "lifetime": lifetime}


# ------------------------------------------------------------------ razorpay api
def _call(method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
    kid, sec = keys()
    req = urllib.request.Request(API + path, method=method,
                                 data=json.dumps(payload).encode() if payload is not None else None)
    req.add_header("Authorization", "Basic " + base64.b64encode(f"{kid}:{sec}".encode()).decode())
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return True, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode() or "{}")
        except Exception:
            body = {}
        msg = ((body.get("error") or {}).get("description")) or f"Razorpay error {e.code}"
        return False, {"error": msg}
    except Exception as e:
        return False, {"error": f"Could not reach Razorpay ({e})"}


def create_checkout(user: Dict[str, Any], plan_id: str, cycle: str, coupon: str = "") -> Dict[str, Any]:
    q = quote(plan_id, cycle, coupon)
    pid = db.new_id("pay_")
    base_row = (pid, user["id"], q["plan_id"], q["cycle"], q["currency"], q["base_amount"], q["discount"],
                q["tax"], q["amount"], q["tax_percent"], q["coupon"], db.now())
    insert = ("INSERT INTO dm_payments (id, user_id, plan_id, cycle, currency, base_amount, discount, tax, "
              "amount, tax_percent, coupon, created_at, gateway, order_id, status) "
              "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")

    if q["amount"] == 0:          # 100% coupon: nothing to charge
        db.execute(insert, base_row + ("coupon", "", "created"))
        mark_paid(pid, payment_id="", method="coupon")
        return {"free": True, "payment": public(get(pid)), "quote": q}

    if not enabled():
        raise ValueError("Online payments are not switched on yet. Please contact support.")
    ok, order = _call("POST", "/orders", {
        "amount": q["amount"], "currency": q["currency"], "receipt": pid,
        "notes": {"user_id": user["id"], "email": user.get("email") or "", "plan": q["plan_id"],
                  "cycle": q["cycle"], "payment_ref": pid}})
    if not ok:
        raise ValueError(order.get("error") or "Could not start the payment.")
    db.execute(insert, base_row + ("razorpay", order["id"], "created"))
    kid, _ = keys()
    return {"free": False, "quote": q, "payment_ref": pid,
            "checkout": {"key": kid, "order_id": order["id"], "amount": q["amount"], "currency": q["currency"],
                         "name": settings.get("brand_name") or "DM Flow",
                         "description": f"{q['plan_name']} plan - {q['cycle']}",
                         "prefill": {"name": user.get("name") or "", "email": user.get("email") or ""},
                         "notes": {"payment_ref": pid}}}


# ------------------------------------------------------------------ signatures
def verify_checkout_signature(order_id: str, payment_id: str, signature: str) -> bool:
    _, sec = keys()
    if not (sec and order_id and payment_id and signature):
        return False
    want = hmac.new(sec.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(want, signature)


def verify_webhook_signature(raw: bytes, signature: str) -> bool:
    sec = settings.get("razorpay_webhook_secret").strip()
    if not (sec and signature):
        return False
    want = hmac.new(sec.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(want, signature)


# ------------------------------------------------------------------ state changes
def get(pid: str) -> Optional[Dict[str, Any]]:
    return db.one("SELECT * FROM dm_payments WHERE id = ?", (pid,))


def by_order(order_id: str) -> Optional[Dict[str, Any]]:
    return db.one("SELECT * FROM dm_payments WHERE order_id = ?", (order_id,)) if order_id else None


def _next_invoice_no() -> str:
    prefix = (settings.get("invoice_prefix") or "DMF").strip().upper()
    year = time.strftime("%Y")
    n = int((db.one("SELECT COUNT(*) AS n FROM dm_payments WHERE invoice_no LIKE ?",
                    (f"{prefix}-{year}-%",)) or {}).get("n") or 0)
    return f"{prefix}-{year}-{n + 1:05d}"


def mark_paid(pid: str, payment_id: str = "", method: str = "") -> bool:
    """Activate the plan for a payment. True only the first time."""
    claimed = db.execute("UPDATE dm_payments SET status = 'paid', payment_id = ?, method = ?, paid_at = ? "
                         "WHERE id = ? AND status != 'paid'", (payment_id, method, db.now(), pid))
    if claimed != 1:
        return False
    p = get(pid)
    user = db.one("SELECT * FROM dm_users WHERE id = ?", (p["user_id"],))
    if not user:
        return True
    now = db.now()
    lifetime = p["gateway"] == "coupon" and _is_lifetime_coupon(p["coupon"])
    if lifetime:
        db.execute("UPDATE dm_users SET is_lifetime = 1, plan = 'lifetime', plan_expires_at = 0, status = 'active' "
                   "WHERE id = ?", (user["id"],))
        start, end = now, 0
    else:
        # Same plan, still running: stack the new period on the days left.
        current_end = int(user.get("plan_expires_at") or 0)
        start = current_end if (user.get("plan") == p["plan_id"] and current_end > now) else now
        end = start + PERIOD.get(p["cycle"], PERIOD["monthly"])
        if not user.get("is_lifetime"):
            db.execute("UPDATE dm_users SET plan = ?, plan_expires_at = ?, reminded_for = 0, status = 'active' "
                       "WHERE id = ?", (p["plan_id"], end, user["id"]))
    db.execute("UPDATE dm_payments SET invoice_no = ?, period_start = ?, period_end = ? WHERE id = ?",
               (_next_invoice_no(), start, end, pid))
    if p.get("coupon"):
        db.execute("UPDATE dm_offers SET used_count = used_count + 1 WHERE code = ?", (p["coupon"],))
    p = get(pid)
    try:
        if lifetime:
            email_service.notify_lifetime_granted(user)
        else:
            email_service.notify_payment_success(user, p, settings.plan(p["plan_id"]).get("name") or p["plan_id"])
    except Exception as exc:
        log.warning("receipt email failed: %s", exc)
    log.info("payment %s paid: user=%s plan=%s amount=%s", pid, user["email"], p["plan_id"], p["amount"])
    return True


def _is_lifetime_coupon(code: str) -> bool:
    row = db.one("SELECT discount_type FROM dm_offers WHERE code = ?", (code or "",))
    return bool(row and row["discount_type"] == "lifetime")


def mark_failed(pid: str, reason: str = "", payment_id: str = "") -> None:
    changed = db.execute("UPDATE dm_payments SET status = 'failed', error = ?, payment_id = ? "
                         "WHERE id = ? AND status = 'created'", (reason[:300], payment_id, pid))
    if changed == 1:
        p = get(pid)
        user = db.one("SELECT * FROM dm_users WHERE id = ?", (p["user_id"],))
        if user:
            email_service.notify_payment_failed(user, settings.plan(p["plan_id"]).get("name") or p["plan_id"], reason)


def handle_webhook(event: Dict[str, Any]) -> str:
    kind = event.get("event") or ""
    payload = event.get("payload") or {}
    pay = ((payload.get("payment") or {}).get("entity")) or {}
    order = ((payload.get("order") or {}).get("entity")) or {}
    order_id = pay.get("order_id") or order.get("id") or ""
    row = by_order(order_id)
    if not row:
        return f"{kind}: no matching order"
    if kind in ("payment.captured", "order.paid"):
        if pay and int(pay.get("amount") or 0) != int(row["amount"]):
            log.error("amount mismatch on %s: paid %s expected %s", row["id"], pay.get("amount"), row["amount"])
            return "amount mismatch - not activated"
        done = mark_paid(row["id"], pay.get("id") or row["payment_id"], pay.get("method") or "")
        return f"{kind}: {'activated' if done else 'already active'}"
    if kind == "payment.failed":
        mark_failed(row["id"], pay.get("error_description") or "Payment failed", pay.get("id") or "")
        return "payment.failed recorded"
    return f"{kind}: ignored"


# ------------------------------------------------------------------ sweep
def sweep() -> Dict[str, int]:
    """Renewal reminders and expiries. Safe to run as often as you like."""
    now = db.now()
    stats = {"reminded": 0, "expired": 0}
    try:
        days = max(1, int(settings.get("renewal_reminder_days") or 3))
    except ValueError:
        days = 3
    rows = db.query("SELECT * FROM dm_users WHERE is_lifetime = 0 AND plan != 'free' AND plan_expires_at > 0 "
                    "AND role != 'admin'")
    for u in rows:
        end = int(u["plan_expires_at"])
        name = settings.plan(u["plan"]).get("name") or u["plan"]
        if end <= now:
            if db.execute("UPDATE dm_users SET plan = 'free', plan_expires_at = 0 WHERE id = ? AND plan_expires_at = ?",
                          (u["id"], end)) == 1:
                _pause_extra_flows(u["id"])
                email_service.notify_plan_expired(u, name)
                stats["expired"] += 1
        elif end - now <= days * 86400 and int(u.get("reminded_for") or 0) != end:
            if db.execute("UPDATE dm_users SET reminded_for = ? WHERE id = ? AND reminded_for != ?",
                          (end, u["id"], end)) == 1:
                email_service.notify_renewal_reminder(u, name, end)
                stats["reminded"] += 1
    # Abandoned checkouts older than a day are not "pending" any more.
    db.execute("UPDATE dm_payments SET status = 'abandoned' WHERE status = 'created' AND created_at < ?",
               (now - 86400,))
    return stats


def _pause_extra_flows(user_id: str) -> None:
    """Keep only as many live automations as the Free plan allows (newest stay on)."""
    limit = int((settings.plan("free").get("limits") or {}).get("automations", 1))
    if limit < 0:
        return
    live = db.query("SELECT id FROM dm_flows WHERE user_id = ? AND status = 'live' ORDER BY updated_at DESC",
                    (user_id,))
    for f in live[limit:]:
        db.execute("UPDATE dm_flows SET status = 'paused' WHERE id = ?", (f["id"],))


# ------------------------------------------------------------------ views
def public(p: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not p:
        return None
    keep = ("id", "plan_id", "cycle", "status", "currency", "base_amount", "discount", "tax", "amount",
            "tax_percent", "coupon", "method", "invoice_no", "period_start", "period_end", "created_at",
            "paid_at", "payment_id", "gateway")
    out = {k: p.get(k) for k in keep}
    out["plan_name"] = settings.plan(p.get("plan_id") or "").get("name") or p.get("plan_id")
    return out


def invoice_html(p: Dict[str, Any], user: Dict[str, Any]) -> str:
    e, money, day = email_service.esc, email_service.money, email_service.day
    cur = p.get("currency") or "INR"
    plan_name = settings.plan(p["plan_id"]).get("name") or p["plan_id"]
    gstin = settings.get("company_gstin").strip()
    lines = [(f"{plan_name} plan - {p['cycle']} ({day(p['period_start'])} to {day(p['period_end'])})",
              money(p["base_amount"], cur))]
    if p["discount"]:
        lines.append((f"Discount {p['coupon']}", "- " + money(p["discount"], cur)))
    if p["tax"]:
        lines.append((f"GST @ {p['tax_percent']:g}%", money(p["tax"], cur)))
    rows = "".join(f"<tr><td>{e(a)}</td><td class='r'>{e(b)}</td></tr>" for a, b in lines)
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Invoice {e(p['invoice_no'])}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#0b0d0c;background:#f4f5f4;margin:0;padding:24px}}
.inv{{max-width:720px;margin:auto;background:#fff;border:1px solid #e6e8e7;border-radius:14px;padding:36px}}
h1{{margin:0;font-size:26px}}.muted{{color:#5c625f;font-size:13px;line-height:1.6}}.top{{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}}
table{{width:100%;border-collapse:collapse;margin-top:28px}}td,th{{padding:11px 0;border-bottom:1px solid #eef0ef;text-align:left;font-size:14px}}
.r{{text-align:right}}.tot td{{font-weight:800;font-size:16px;border-bottom:0}}.paid{{display:inline-block;background:#e3f8ee;color:#0a8f56;font-weight:800;padding:4px 12px;border-radius:99px;font-size:12px}}
button{{margin-top:24px;padding:10px 20px;border-radius:99px;border:1px solid #0b0d0c;background:#0b0d0c;color:#fff;font-weight:700;cursor:pointer}}
@media print{{body{{background:#fff;padding:0}}.inv{{border:0}}button{{display:none}}}}</style></head><body>
<div class="inv"><div class="top"><div><h1>{e(settings.get('brand_name') or 'DM Flow')}</h1>
<div class="muted">{e(settings.get('company_name'))}<br>{e(settings.get('company_address'))}<br>
{('GSTIN: ' + e(gstin) + '<br>') if gstin else ''}{e(settings.get('support_email'))}</div></div>
<div class="r"><div class="muted">{'TAX INVOICE' if gstin else 'INVOICE'}</div><h1>{e(p['invoice_no'])}</h1>
<div class="muted">Date: {e(day(p['paid_at']))}</div><span class="paid">PAID</span></div></div>
<div class="muted" style="margin-top:26px"><b style="color:#0b0d0c">Billed to</b><br>{e(user.get('name'))}<br>{e(user.get('email'))}</div>
<table><tr><th>Description</th><th class="r">Amount</th></tr>{rows}
<tr class="tot"><td>Total paid</td><td class="r">{e(money(p['amount'], cur))}</td></tr></table>
<div class="muted" style="margin-top:18px">Payment ID: {e(p['payment_id'] or '-')} · Method: {e(p['method'] or p['gateway'])}</div>
<button onclick="window.print()">Download / Print PDF</button></div></body></html>"""
