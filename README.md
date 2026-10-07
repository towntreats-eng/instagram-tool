# DM Flow

Instagram comment-to-DM automation for Indian D2C brands.
Someone comments a keyword on a post → DM Flow replies publicly, sends an opening DM with a button, and sends the link when they tap it (optionally only after they follow).

## Run locally

```
pip install -r requirements.txt
python run.py            # http://localhost:8000  (SQLite in data/dmflow.db)
```

## Deploy (Railway)

Start command comes from `Procfile` (`uvicorn main:app`). Set these variables:

| Variable | Needed | What |
|---|---|---|
| `DATABASE_URL` | yes | Postgres URL (Railway adds it) |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | first deploy | creates the admin login if it does not exist |
| `IG_APP_ID`, `IG_APP_SECRET` | optional | Instagram App ID / Secret (else set in /admin) |
| `META_APP_SECRET` | optional | App settings > Basic secret; signs webhooks (else set in /admin) |
| `VERIFY_TOKEN`, `BASE_URL` | optional | webhook verify token, public https URL |

| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` | optional | else set in /admin > Payment Gateways |
| `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_ENABLED=1` | optional | Gmail + 16-letter App Password (else set in /admin > Email) |

Never commit secrets — this repo is public.

## Meta URLs (shown in /admin)

- OAuth redirect: `https://<domain>/api/instagram/callback`
- Webhook: `https://<domain>/api/meta/webhook` (fields: comments, messages, messaging_postbacks)
- Deauthorize: `https://<domain>/api/meta/deauthorize`
- Data deletion: `https://<domain>/api/meta/data-deletion`

## Payments (Razorpay)

Customers pay from `/app/billing` (UPI, cards, net banking). One payment per month/year;
paying early adds the new period on top. Razorpay webhook: `https://<domain>/api/razorpay/webhook`
(events: payment.captured, payment.failed, order.paid). An hourly job emails renewal reminders and
moves expired plans to Free. Invoices: `/api/billing/invoice/<id>`.

## Email (free via Gmail)

Admin > Email: choose Gmail, enter the Gmail address and a Google App Password
(myaccount.google.com/apppasswords, needs 2-Step Verification). About 500 emails/day.
Emails: welcome, payment receipt, payment failed, renewal reminder, plan expired, password reset,
ticket reply, lifetime VIP, owner alerts (signup + payment). Every send is logged in Admin > Email.

## Layout

```
dmflow/
  web.py        FastAPI routes (pages, APIs, webhook, admin)
  instagram.py  Instagram Graph API calls (graph.instagram.com)
  accounts.py   connect / status / real disconnect
  engine.py     flows, comment + postback handling
  poller.py     fallback comment polling (unpublished apps get no webhooks)
  db.py         Postgres or SQLite, dm_* tables
  settings.py   config + plans
  billing.py    Razorpay orders, verification, webhook, renewals, invoices
  email_service.py  Gmail/SMTP sending + all email templates
  auth.py       users, sessions, passwords
  static/       landing, app panel, admin
legacy/         old code, kept for reference only (safe to delete)
```
