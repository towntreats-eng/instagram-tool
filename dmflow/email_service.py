"""
DM Flow — Email & SMTP Service.
Handles transactional emails, ticket replies, welcome emails, lifetime VIP notifications,
and SMTP diagnostic test sending using Python stdlib smtplib.
"""

import email.utils
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional, Tuple

from dmflow import db, settings

log = logging.getLogger("dmflow.email")


def get_smtp_config() -> Dict[str, Any]:
    enabled = settings.get("smtp_enabled") in ("1", "true", "yes")
    port_str = settings.get("smtp_port") or "587"
    try:
        port = int(port_str)
    except ValueError:
        port = 587

    return {
        "enabled": enabled,
        "host": settings.get("smtp_host").strip(),
        "port": port,
        "user": settings.get("smtp_user").strip(),
        "password": settings.get("smtp_password").strip(),
        "from_name": settings.get("smtp_from_name").strip() or settings.get("brand_name").strip() or "DM Flow",
        "from_email": settings.get("smtp_from_email").strip() or settings.get("smtp_user").strip(),
        "security": settings.get("smtp_security").strip().lower() or "tls",  # tls | ssl | none
    }


def send_email(to_email: str, subject: str, body_text: str, body_html: Optional[str] = None) -> Tuple[bool, str]:
    """
    Sends an email using configured SMTP settings.
    Returns (success: bool, message: str).
    """
    to_email = (to_email or "").strip()
    if not to_email or "@" not in to_email:
        return False, "Invalid recipient email address."

    cfg = get_smtp_config()
    if not cfg["enabled"]:
        return False, "SMTP is currently disabled in Email Settings."
    if not cfg["host"]:
        return False, "SMTP Host is not configured."

    sender_email = cfg["from_email"] or cfg["user"]
    if not sender_email:
        return False, "SMTP From Email or Username is not configured."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email.utils.formataddr((cfg["from_name"], sender_email))
    msg["To"] = to_email
    msg["Date"] = email.utils.formatdate(localtime=True)

    part_text = MIMEText(body_text, "plain", "utf-8")
    msg.attach(part_text)

    if body_html:
        part_html = MIMEText(body_html, "html", "utf-8")
        msg.attach(part_html)

    try:
        sec = cfg["security"]
        host, port = cfg["host"], cfg["port"]
        timeout = 12

        if sec == "ssl" or port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=timeout)
        else:
            server = smtplib.SMTP(host, port, timeout=timeout)
            if sec != "none":
                server.ehlo()
                server.starttls()
                server.ehlo()

        if cfg["user"] and cfg["password"]:
            server.login(cfg["user"], cfg["password"])

        server.sendmail(sender_email, [to_email], msg.as_string())
        server.quit()
        log.info("Email sent to %s: %s", to_email, subject)
        return True, "Email sent successfully."
    except smtplib.SMTPAuthenticationError as exc:
        err = f"SMTP Authentication failed: check username and password ({exc})"
        log.warning(err)
        return False, err
    except smtplib.SMTPConnectError as exc:
        err = f"Failed to connect to SMTP server {cfg['host']}:{cfg['port']} ({exc})"
        log.warning(err)
        return False, err
    except Exception as exc:
        err = f"Email delivery error: {str(exc)}"
        log.warning(err)
        return False, err


def test_connection(to_email: str) -> Tuple[bool, str]:
    brand = settings.get("brand_name") or "DM Flow"
    subject = f"[{brand}] SMTP Configuration Test — Success"
    text = (f"Hello,\n\n"
            f"This is a test email from {brand} to confirm that your SMTP email settings are working perfectly!\n\n"
            f"Time: {email.utils.formatdate(localtime=True)}\n"
            f"Host: {settings.get('smtp_host')}\n\n"
            f"Regards,\n"
            f"{brand} Team")
    html = f"""<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:540px;margin:20px auto;padding:24px;border:1px solid #e5e7eb;border-radius:12px;background:#ffffff;">
      <h2 style="color:#111827;margin-top:0;">{brand} SMTP Test Successful 🎉</h2>
      <p style="color:#4b5563;font-size:15px;line-height:1.5;">Your SMTP server settings are correctly configured. Transactional emails, support ticket replies, and account notices are ready to deliver.</p>
      <div style="background:#f3f4f6;padding:12px 16px;border-radius:8px;font-size:13px;color:#374151;margin:18px 0;">
        <b>Server:</b> {settings.get('smtp_host')}:{settings.get('smtp_port')}<br>
        <b>Timestamp:</b> {email.utils.formatdate(localtime=True)}
      </div>
      <p style="color:#9ca3af;font-size:12px;margin-bottom:0;">Automated test message from {brand} Control Center.</p>
    </div>"""
    return send_email(to_email, subject, text, html)


def notify_welcome(user: Dict[str, Any]) -> None:
    if settings.get("email_welcome_enabled") not in ("1", "true", "yes"):
        return
    email_addr = user.get("email")
    if not email_addr:
        return
    brand = settings.get("brand_name") or "DM Flow"
    name = user.get("name") or "there"
    subject = f"Welcome to {brand} — Your Instagram Automation is Ready"
    text = (f"Hi {name},\n\n"
            f"Welcome to {brand}! Your account is now live.\n\n"
            f"Here is how to get started:\n"
            f"1. Connect your Instagram Professional account in the dashboard.\n"
            f"2. Create your first keyword automation flow.\n"
            f"3. Turn comments on your reels and posts into automatic sales & leads!\n\n"
            f"If you need any help, submit a ticket in your customer panel or reply to this email.\n\n"
            f"Cheers,\n"
            f"The {brand} Team")
    send_email(email_addr, subject, text)


def notify_lifetime_granted(user: Dict[str, Any]) -> None:
    if settings.get("email_lifetime_enabled") not in ("1", "true", "yes"):
        return
    email_addr = user.get("email")
    if not email_addr:
        return
    brand = settings.get("brand_name") or "DM Flow"
    name = user.get("name") or "there"
    subject = f"🌟 You've Been Gifted Free Lifetime VIP Access on {brand}!"
    text = (f"Hi {name},\n\n"
            f"We have exciting news! Your account has been upgraded to a Free Lifetime VIP Membership on {brand}.\n\n"
            f"What this means for you:\n"
            f"• Unlimited monthly DMs\n"
            f"• Unlimited active automations\n"
            f"• Unlimited contacts storage\n"
            f"• All premium features unlocked forever with zero monthly fees\n\n"
            f"Sign in now to explore your upgraded workspace.\n\n"
            f"Cheers,\n"
            f"The {brand} Team")
    html = f"""<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:540px;margin:20px auto;padding:28px;border:1px solid #10b981;border-radius:14px;background:#ffffff;">
      <span style="background:#ecfdf5;color:#059669;font-weight:700;font-size:12px;padding:4px 10px;border-radius:20px;text-transform:uppercase;letter-spacing:0.05em;">VIP Upgrade</span>
      <h2 style="color:#111827;margin:14px 0 10px;">Free Lifetime Account Activated 🎉</h2>
      <p style="color:#374151;font-size:15px;line-height:1.5;">Hi <b>{name}</b>, your account on <b>{brand}</b> has been upgraded to <b>Lifetime VIP</b> access!</p>
      <ul style="color:#4b5563;font-size:14px;line-height:1.7;padding-left:20px;">
        <li><b>Unlimited Automations</b> — Run as many comment-to-DM flows as you need</li>
        <li><b>Unlimited DMs</b> — Zero monthly message limits</li>
        <li><b>Unlimited Contacts</b> — Store every lead forever</li>
        <li><b>No Subscriptions</b> — Free forever, no recurring fees</li>
      </ul>
      <p style="color:#6b7280;font-size:13px;margin-top:20px;">Sign in to your account to enjoy your lifetime perks.</p>
    </div>"""
    send_email(email_addr, subject, text, html)


def notify_ticket_reply(ticket: Dict[str, Any], reply_text: str, by_admin: bool = True) -> None:
    if settings.get("email_ticket_enabled") not in ("1", "true", "yes"):
        return
    to_email = ticket.get("user_email")
    if not to_email or not by_admin:
        return
    brand = settings.get("brand_name") or "DM Flow"
    subject = f"[{brand} Support] Response to Ticket #{ticket['id']}: {ticket.get('subject', '')}"
    text = (f"Hello {ticket.get('user_name', '')},\n\n"
            f"Our team has responded to your support ticket #{ticket['id']} ({ticket.get('subject', '')}):\n\n"
            f"----------------------------------------\n"
            f"{reply_text}\n"
            f"----------------------------------------\n\n"
            f"To view the full ticket and reply, log in to your {brand} dashboard.\n\n"
            f"Regards,\n"
            f"{brand} Support")
    send_email(to_email, subject, text)
