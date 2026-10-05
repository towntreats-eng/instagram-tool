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

Never commit secrets — this repo is public.

## Meta URLs (shown in /admin)

- OAuth redirect: `https://<domain>/api/instagram/callback`
- Webhook: `https://<domain>/api/meta/webhook` (fields: comments, messages, messaging_postbacks)
- Deauthorize: `https://<domain>/api/meta/deauthorize`
- Data deletion: `https://<domain>/api/meta/data-deletion`

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
  auth.py       users, sessions, passwords
  static/       landing, app panel, admin
legacy/         old code, kept for reference only (safe to delete)
```
