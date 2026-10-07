"""
DM Flow - transactional email.

Free delivery through a normal Gmail account: Gmail's SMTP server
(smtp.gmail.com:587) with a 16-letter Google *App Password*. Any other SMTP
host still works by choosing "custom".

Every send runs on a small background pool, so a slow mail server never holds
up a signup or a payment, and every attempt is written to dm_email_log so the
admin can see what was delivered and what failed.

Gmail facts the code respects:
  * The From address must be the Gmail account itself (Gmail rewrites any
    other address), so for Gmail From = the login.
  * App Passwords are shown as "abcd efgh ijkl mnop"; the spaces are removed.
  * A free Gmail account sends about 500 emails a day.
"""

import email.utils
import html as _html
import logging
import smtplib
import time
from concurrent.futures import ThreadPoolExecutor
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional, Tuple

from dmflow import db, settings

log = logging.getLogger("dmflow.email")
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mail")

GMAIL_HOST, GMAIL_PORT = "smtp.gmail.com", 587
YES = ("1", "true", "yes", "on")


# ------------------------------------------------------------------ config
def _is_gmail(addr: str) -> bool:
    return addr.lower().endswith(("@gmail.com", "@googlemail.com"))


def get_smtp_config() -> Dict[str, Any]:
    user = settings.get("smtp_user").strip()
    provider = (settings.get("smtp_provider") or "").strip().lower()
    host = settings.get("smtp_host").strip()
    if provider == "gmail" or (not host and _is_gmail(user)):
        provider = "gmail"
    try:
        port = int(settings.get("smtp_port") or 587)
    except ValueError:
        port = 587
    password = settings.get("smtp_password").strip()
    from_email = settings.get("smtp_from_email").strip() or user
    security = settings.get("smtp_security").strip().lower() or "tls"
    if provider == "gmail":
        host, port, security = GMAIL_HOST, GMAIL_PORT, "tls"
        password = password.replace(" ", "")
        from_email = user
    return {
        "enabled": settings.get("smtp_enabled") in YES,
        "provider": provider or "custom",
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "from_name": settings.get("smtp_from_name").strip() or brand(),
        "from_email": from_email,
        "security": security,  # tls | ssl | none
    }


def ready() -> bool:
    c = get_smtp_config()
    return bool(c["enabled"] and c["host"] and c["from_email"])


def brand() -> str:
    return (settings.get("brand_name") or "DM Flow").strip()


# Filled in by the web app from incoming requests, so links in emails work even
# when BASE_URL is not set.
SEEN_BASE = ""


def app_url(path: str = "") -> str:
    base = settings.get("base_url").rstrip("/") or SEEN_BASE
    return (base or "") + path


def _flag(key: str) -> bool:
    return settings.get(key) in YES


# ------------------------------------------------------------------ sending
def _log(kind: str, to: str, subject: str, status: str, error: str = "") -> None:
    try:
        db.execute("INSERT INTO dm_email_log (id, at, kind, to_email, subject, status, error) "
                   "VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (db.new_id("em_"), db.now(), kind, to, subject[:200], status, error[:500]))
    except Exception:
        pass


def send_email(to_email: str, subject: str, body_text: str, body_html: Optional[str] = None,
               kind: str = "manual") -> Tuple[bool, str]:
    """Send now, on the calling thread. Returns (ok, message)."""
    to_email = (to_email or "").strip()
    if not to_email or "@" not in to_email:
        return False, "Invalid recipient email address."
    cfg = get_smtp_config()
    if not cfg["enabled"]:
        return False, "Email sending is switched off in Admin > Email."
    if not cfg["host"]:
        return False, "No mail server is set. Choose Gmail and enter your Gmail + App Password."
    if not cfg["from_email"]:
        return False, "No sender address is set."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email.utils.formataddr((cfg["from_name"], cfg["from_email"]))
    msg["To"] = to_email
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid(domain=cfg["from_email"].split("@")[-1])
    reply_to = (settings.get("support_email") or "").strip()
    if reply_to and reply_to.lower() != cfg["from_email"].lower():
        msg["Reply-To"] = reply_to
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        if cfg["security"] == "ssl" or cfg["port"] == 465:
            server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=20)
        else:
            server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=20)
            if cfg["security"] != "none":
                server.ehlo()
                server.starttls()
                server.ehlo()
        try:
            if cfg["user"] and cfg["password"]:
                server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["from_email"], [to_email], msg.as_string())
        finally:
            try:
                server.quit()
            except Exception:
                pass
        log.info("Email [%s] sent to %s", kind, to_email)
        _log(kind, to_email, subject, "sent")
        return True, "Email sent."
    except smtplib.SMTPAuthenticationError:
        err = ("Gmail refused the login. Use a Google App Password (16 letters), not your normal "
               "Gmail password, and keep 2-Step Verification on.") if cfg["provider"] == "gmail" \
            else "The mail server refused the username or password."
    except (smtplib.SMTPConnectError, OSError) as exc:
        err = f"Could not reach {cfg['host']}:{cfg['port']} ({exc})."
    except Exception as exc:
        err = f"Email delivery error: {exc}"
    log.warning("Email [%s] to %s failed: %s", kind, to_email, err)
    _log(kind, to_email, subject, "failed", err)
    return False, err


def send_later(to_email: str, subject: str, body_text: str, body_html: Optional[str] = None,
               kind: str = "system") -> None:
    """Queue an email in the background. Never raises, never blocks."""
    if not ready():
        _log(kind, to_email or "", subject, "skipped", "Email sending is not set up.")
        return
    try:
        _pool.submit(send_email, to_email, subject, body_text, body_html, kind)
    except Exception as exc:
        log.warning("could not queue email: %s", exc)


# ------------------------------------------------------------------ layout
def esc(v: Any) -> str:
    return _html.escape(str(v if v is not None else ""))


def money(paise: int, currency: str = "INR") -> str:
    amt = (paise or 0) / 100
    sym = "₹" if currency.upper() == "INR" else currency.upper() + " "
    return f"{sym}{amt:,.2f}".replace(".00", "")


def day(ts: int) -> str:
    return time.strftime("%d %b %Y", time.localtime(ts)) if ts else "-"


def layout(heading: str, paragraphs: List[str], button: Optional[Tuple[str, str]] = None,
           extra_html: str = "", footnote: str = "") -> str:
    """One consistent, mobile-friendly email. `paragraphs` are already-escaped HTML."""
    b = esc(brand())
    btn = ""
    if button and button[1]:
        btn = (f'<tr><td style="padding:8px 0 24px"><a href="{esc(button[1])}" '
               'style="display:inline-block;background:#0fbf73;color:#04291a;font-weight:700;'
               'text-decoration:none;padding:13px 26px;border-radius:999px;font-size:15px">'
               f'{esc(button[0])}</a></td></tr>')
    body = "".join(f'<p style="margin:0 0 14px;color:#2b2f2d;font-size:15px;line-height:1.6">{p}</p>'
                   for p in paragraphs)
    support = esc(settings.get("support_email") or "")
    wa = esc(settings.get("support_whatsapp") or "")
    help_line = " · ".join(x for x in (support, ("WhatsApp " + wa) if wa else "") if x)
    return f"""<!doctype html><html><body style="margin:0;background:#f4f5f4;padding:24px 12px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border:1px solid #e6e8e7;border-radius:16px">
<tr><td style="padding:22px 28px;border-bottom:1px solid #eef0ef">
<span style="display:inline-block;width:26px;height:26px;border-radius:8px;background:#0b0d0c;color:#0fbf73;text-align:center;line-height:26px;font-weight:800">&#9889;</span>
<b style="font-size:16px;color:#0b0d0c;vertical-align:middle;margin-left:6px">{b}</b></td></tr>
<tr><td style="padding:28px 28px 8px">
<h1 style="margin:0 0 16px;font-size:22px;line-height:1.3;color:#0b0d0c">{esc(heading)}</h1>
{body}{extra_html}
<table role="presentation" cellpadding="0" cellspacing="0">{btn}</table>
</td></tr>
<tr><td style="padding:18px 28px 24px;border-top:1px solid #eef0ef;color:#8c928f;font-size:12px;line-height:1.6">
{esc(footnote) + '<br>' if footnote else ''}Need help? {help_line or 'Reply to this email.'}<br>
{esc(settings.get('company_name') or b)}</td></tr>
</table></td></tr></table></body></html>"""


def _first(user: Dict[str, Any]) -> str:
    return ((user.get("name") or "").split(" ")[0] or "there").strip()


def _admin_to() -> str:
    return (settings.get("admin_alert_email") or settings.get("support_email") or "").strip()


# ------------------------------------------------------------------ messages
def test_connection(to_email: str) -> Tuple[bool, str]:
    cfg = get_smtp_config()
    subject = f"{brand()} email is working"
    text = (f"This is a test email from {brand()}.\n\nServer: {cfg['host']}:{cfg['port']}\n"
            f"Sender: {cfg['from_email']}\nTime: {email.utils.formatdate(localtime=True)}\n")
    html = layout("Your email setup works 🎉",
                  [f"This test came from <b>{esc(cfg['from_email'])}</b> through "
                   f"<b>{esc(cfg['host'])}</b>.",
                   "Welcome emails, payment receipts, renewal reminders and password resets "
                   "will now reach your customers."])
    return send_email(to_email, subject, text, html, kind="test")


def notify_welcome(user: Dict[str, Any]) -> None:
    if not _flag("email_welcome_enabled") or not user.get("email"):
        return
    name, url = _first(user), app_url("/app")
    subject = f"Welcome to {brand()}, {name} 👋"
    text = (f"Hi {name},\n\nWelcome to {brand()}! Your account is ready.\n\n"
            "Get your first automation live in 3 steps:\n"
            "1. Connect your Instagram Business or Creator account.\n"
            "2. Pick a post and a keyword (for example: LINK).\n"
            "3. Turn it on - every matching comment gets an instant DM.\n\n"
            f"Open your dashboard: {url}\n\nTeam {brand()}")
    html = layout(f"Welcome, {name} 👋",
                  [f"Your <b>{esc(brand())}</b> account is ready. Every comment on your posts can now turn "
                   "into an instant DM, a follower, and a sale.",
                   "<b>Live in 3 steps:</b><br>1. Connect your Instagram Business or Creator account<br>"
                   "2. Pick a post and a keyword (for example <b>LINK</b>)<br>"
                   "3. Turn it on - every matching comment gets an instant DM"],
                  ("Open my dashboard", url))
    send_later(user["email"], subject, text, html, kind="welcome")
    admin_new_signup(user)


def notify_password_reset(user: Dict[str, Any], link: str) -> None:
    """Always sent when email works - a user who cannot log in has no other way back."""
    name = _first(user)
    subject = f"Reset your {brand()} password"
    text = (f"Hi {name},\n\nSomeone asked to reset the password for this account. "
            f"Open this link within 1 hour to choose a new one:\n{link}\n\n"
            "If it was not you, ignore this email - your password stays the same.")
    html = layout("Reset your password",
                  [f"Hi {esc(name)}, we got a request to reset the password for "
                   f"<b>{esc(user.get('email'))}</b>.",
                   "The link works for <b>1 hour</b> and only once."],
                  ("Choose a new password", link),
                  footnote="Didn't ask for this? Ignore this email - your password stays the same.")
    send_later(user["email"], subject, text, html, kind="password_reset")


def _receipt_table(p: Dict[str, Any], plan_name: str) -> str:
    cur = p.get("currency") or "INR"
    rows = [("Plan", f"{plan_name} ({p.get('cycle')})"),
            ("Valid till", day(p.get("period_end") or 0)),
            ("Price", money(p.get("base_amount"), cur))]
    if p.get("discount"):
        rows.append((f"Discount{(' (' + p['coupon'] + ')') if p.get('coupon') else ''}",
                     "- " + money(p["discount"], cur)))
    if p.get("tax"):
        rows.append((f"GST {p.get('tax_percent') or 0:g}%", money(p["tax"], cur)))
    cells = "".join(f'<tr><td style="padding:7px 0;color:#5c625f;font-size:14px">{esc(k)}</td>'
                    f'<td style="padding:7px 0;text-align:right;font-size:14px;color:#0b0d0c">{esc(v)}</td></tr>'
                    for k, v in rows)
    cells += ('<tr><td style="padding:10px 0 4px;border-top:1px solid #eef0ef;font-weight:700">Total paid</td>'
              f'<td style="padding:10px 0 4px;border-top:1px solid #eef0ef;text-align:right;font-weight:800;font-size:16px">'
              f'{esc(money(p.get("amount"), cur))}</td></tr>')
    return ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'style="background:#f7f8f7;border-radius:12px;padding:6px 16px;margin:4px 0 20px">'
            f'{cells}</table>')


def notify_payment_success(user: Dict[str, Any], p: Dict[str, Any], plan_name: str) -> None:
    if _flag("email_payment_enabled") and user.get("email"):
        name = _first(user)
        inv = p.get("invoice_no") or p.get("id")
        subject = f"Payment received - {plan_name} plan is active (Invoice {inv})"
        text = (f"Hi {name},\n\nThanks! We received {money(p.get('amount'), p.get('currency') or 'INR')} "
                f"for the {plan_name} plan ({p.get('cycle')}).\nInvoice: {inv}\n"
                f"Payment ID: {p.get('payment_id') or '-'}\nValid till: {day(p.get('period_end') or 0)}\n\n"
                f"Download your invoice: {app_url('/api/billing/invoice/' + p['id'])}\n\nTeam {brand()}")
        html = layout(f"Payment received - {plan_name} is active ✅",
                      [f"Thanks {esc(name)}! Your <b>{esc(plan_name)}</b> plan is now active.",
                       f"Invoice <b>{esc(inv)}</b> · Payment ID {esc(p.get('payment_id') or '-')}"],
                      ("Download invoice", app_url("/api/billing/invoice/" + p["id"])),
                      extra_html=_receipt_table(p, plan_name))
        send_later(user["email"], subject, text, html, kind="payment_receipt")
    admin_new_payment(user, p, plan_name)


def notify_payment_failed(user: Dict[str, Any], plan_name: str, reason: str = "") -> None:
    if not _flag("email_payment_failed_enabled") or not user.get("email"):
        return
    name, url = _first(user), app_url("/app/billing")
    subject = f"Your {brand()} payment didn't go through"
    text = (f"Hi {name},\n\nYour payment for the {plan_name} plan did not complete"
            f"{(': ' + reason) if reason else ''}.\nNo money was taken for this attempt - if it was, "
            f"your bank refunds it automatically within 5-7 days.\n\nTry again: {url}")
    html = layout("Payment didn't go through",
                  [f"Hi {esc(name)}, your payment for the <b>{esc(plan_name)}</b> plan did not complete"
                   f"{(' - ' + esc(reason)) if reason else ''}.",
                   "If money left your account, your bank returns it automatically within 5-7 working days.",
                   "You can try again with UPI, card or net banking."],
                  ("Try again", url))
    send_later(user["email"], subject, text, html, kind="payment_failed")


def notify_renewal_reminder(user: Dict[str, Any], plan_name: str, expires_at: int) -> None:
    if not _flag("email_renewal_enabled") or not user.get("email"):
        return
    name, url = _first(user), app_url("/app/billing")
    days = max(0, round((expires_at - time.time()) / 86400))
    when = "today" if days == 0 else ("tomorrow" if days == 1 else f"in {days} days")
    subject = f"Your {plan_name} plan ends {when} - renew to keep your DMs running"
    text = (f"Hi {name},\n\nYour {plan_name} plan ends {when} ({day(expires_at)}). After that your "
            "workspace moves to the Free plan and automations above the Free limit stop.\n\n"
            f"Renew in one click: {url}")
    html = layout(f"Your plan ends {when}",
                  [f"Hi {esc(name)}, your <b>{esc(plan_name)}</b> plan ends on <b>{esc(day(expires_at))}</b>.",
                   "After that your workspace moves to the Free plan, and automations above the Free limit "
                   "stop replying to comments.",
                   "Renew now and your new period starts after the current one ends - you lose no days."],
                  ("Renew my plan", url))
    send_later(user["email"], subject, text, html, kind="renewal_reminder")


def notify_plan_expired(user: Dict[str, Any], plan_name: str) -> None:
    if not _flag("email_expired_enabled") or not user.get("email"):
        return
    name, url = _first(user), app_url("/app/billing")
    subject = f"Your {plan_name} plan has ended"
    text = (f"Hi {name},\n\nYour {plan_name} plan has ended and your workspace is now on the Free plan. "
            f"Your automations and contacts are safe. Renew to switch everything back on: {url}")
    html = layout(f"Your {plan_name} plan has ended",
                  [f"Hi {esc(name)}, your workspace is now on the <b>Free</b> plan.",
                   "Your automations, contacts and settings are all saved. Renew and everything switches "
                   "back on straight away."],
                  ("Renew now", url))
    send_later(user["email"], subject, text, html, kind="plan_expired")


def notify_lifetime_granted(user: Dict[str, Any]) -> None:
    if not _flag("email_lifetime_enabled") or not user.get("email"):
        return
    name = _first(user)
    subject = f"🌟 You've got Lifetime VIP access on {brand()}"
    text = (f"Hi {name},\n\nYour {brand()} account is now Lifetime VIP: unlimited automations, DMs and "
            f"contacts, with no monthly fee. Sign in: {app_url('/app')}")
    html = layout("Lifetime VIP is on 🌟",
                  [f"Hi {esc(name)}, your account is now <b>Lifetime VIP</b>.",
                   "Unlimited automations · Unlimited DMs · Unlimited contacts · No monthly fee, ever."],
                  ("Open my dashboard", app_url("/app")))
    send_later(user["email"], subject, text, html, kind="lifetime")


def notify_ticket_reply(ticket: Dict[str, Any], reply_text: str, by_admin: bool = True) -> None:
    if not _flag("email_ticket_enabled") or not by_admin or not ticket.get("user_email"):
        return
    subject = f"[{brand()} Support] Re: {ticket.get('subject', '')} (#{ticket['id']})"
    text = (f"Hello {ticket.get('user_name', '')},\n\nOur team replied to your ticket:\n\n{reply_text}\n\n"
            f"Reply from your dashboard: {app_url('/app/support')}")
    html = layout("We replied to your ticket",
                  [f"<b>{esc(ticket.get('subject', ''))}</b>",
                   f'<span style="display:block;background:#f7f8f7;border-radius:10px;padding:14px 16px;'
                   f'white-space:pre-wrap">{esc(reply_text)}</span>'],
                  ("View ticket", app_url("/app/support")))
    send_later(ticket["user_email"], subject, text, html, kind="ticket_reply")


# ------------------------------------------------------------------ owner alerts
def admin_new_signup(user: Dict[str, Any]) -> None:
    to = _admin_to()
    if not _flag("email_admin_alerts_enabled") or not to:
        return
    subject = f"🆕 New signup: {user.get('email')}"
    text = f"New {brand()} signup\nName: {user.get('name')}\nEmail: {user.get('email')}"
    html = layout("New signup", [f"<b>{esc(user.get('name'))}</b> &lt;{esc(user.get('email'))}&gt;"],
                  ("Open admin", app_url("/admin")))
    send_later(to, subject, text, html, kind="admin_signup")


def admin_new_payment(user: Dict[str, Any], p: Dict[str, Any], plan_name: str) -> None:
    to = _admin_to()
    if not _flag("email_admin_alerts_enabled") or not to:
        return
    amt = money(p.get("amount"), p.get("currency") or "INR")
    subject = f"💰 {amt} received - {plan_name} ({user.get('email')})"
    text = (f"Payment received\nCustomer: {user.get('email')}\nPlan: {plan_name} ({p.get('cycle')})\n"
            f"Amount: {amt}\nPayment ID: {p.get('payment_id')}\nInvoice: {p.get('invoice_no')}")
    html = layout(f"{amt} received 💰",
                  [f"<b>{esc(user.get('email'))}</b> paid for <b>{esc(plan_name)}</b> ({esc(p.get('cycle'))})."],
                  ("Open admin", app_url("/admin")), extra_html=_receipt_table(p, plan_name))
    send_later(to, subject, text, html, kind="admin_payment")
