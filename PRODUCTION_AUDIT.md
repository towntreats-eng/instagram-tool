# ConverFlow — production readiness audit
**1 October 2026 · Phase 1 of 3 complete**

This is the report the brief asks for. It is honest about what is done and what
is not: nothing below is called complete unless the chain
*user action → backend → database → business logic → result → UI* was actually
exercised and observed.

---

## 0. Where the brief and the codebase disagree

The brief assumes Next.js, Prisma, server actions and TypeScript. This codebase
is **FastAPI + vanilla JS**, with no ORM and no database at all before today.
So "reuse the existing ORM" had no referent — Postgres was a build, not an
extension. Everything else in the brief still applies.

---

## 1. Existing functionality discovered

| Area | State before today |
|---|---|
| Landing, pricing, login, signup, privacy, terms, deletion pages | Real, served by FastAPI |
| Customer dashboard | Real UI, mixed real/placeholder data |
| Admin console | 10 panels, real UI, **no access control** |
| Instagram OAuth (`meta_oauth.py`) | Real: HMAC-signed state, 15-min TTL, long-lived token exchange |
| Instagram API client (`meta_api.py`) | Real: DM send, comment reply, media fetch |
| Plans, offers, coupons | Real, data-driven |
| Razorpay | Real, built earlier this week |
| Persistence | 11 JSON files on disk |

## 2. Placeholder functionality discovered

- **`current_workspace()` returned `users[0]`** — the first account in the file,
  to every request from anyone. One customer's dashboard showed another's data.
- **Login set nothing.** It checked the password and returned the user object.
  No cookie, no session, no token. The login screen decided nothing.
- **All 30 `/api/admin/*` routes were unauthenticated.** Any visitor who typed
  `/admin` could read every customer, change plans and open platform settings.
- **Passwords were one round of salted SHA-256** — a GPU tries those in the
  billions per second.
- **Eight invented customers** (Riya Mehta/glowcart.in, Rohit Verma/fitforge.in …)
  seeded by `user_manager._seed()`, counting toward MRR, revenue and the signup
  chart. The admin console was lying to its owner about the business.
- **Fourteen invented activity-log rows** naming those customers.
- **Two seeded announcements.**

## 3. Placeholder → real

| Was | Now |
|---|---|
| `users[0]` for everyone | Session cookie → `signed_in_user()`, per request |
| Login sets nothing | 32-byte token, HttpOnly + SameSite=Lax cookie, SHA-256 stored |
| 30 open admin routes | `require_admin()` on all 32; customers get 403 |
| 40 open customer routes | `require_user()` |
| `/app`, `/admin` open | 303 to `/login?next=…`; `/admin` 403s non-admins |
| SHA-256 passwords | PBKDF2-HMAC-SHA256, 240,000 rounds, old hashes upgraded on next sign-in |
| 8 fake customers | Deleted; `_seed()` now creates one admin from `ADMIN_EMAIL`/`ADMIN_PASSWORD`, or nothing |
| 14 fake log rows | Deleted; the log shows what happened |
| JSON files only | PostgreSQL, with JSON fallback when `DATABASE_URL` is unset |
| No audit trail | `audit_log` table, written on every admin mutation |

## 4. PostgreSQL models

```
documents (name PK, body JSONB, updated_at)   -- the 11 existing collections
sessions  (token_hash PK, user_id, role, expires_at, last_seen, ua, ip)
audit_log (id, at, actor_id, actor_email, action, subject_id, old_value, new_value, note)
```
Plus indexes on `sessions(user_id)`, `sessions(expires_at)`, `audit_log(at DESC)`,
`audit_log(subject_id)`.

**Why a document table and not 11 relational tables.** Eight managers already
read and write whole JSON collections. Swapping only the read/write primitive
underneath them moved all of it to Postgres without rewriting eight working
modules at once — which is what "do not break existing functionality" requires.
Sessions and the audit log are append-heavy and must be *queried*, so they got
real tables immediately. Contacts, conversations, messages and events are the
next promotions. **The document table is the bridge, not the destination.**

## 5. API / server actions created

`POST /api/auth/logout` · `GET /api/auth/me` · `GET /api/admin/audit` ·
`GET /api/admin/storage` · `GET /api/admin/connections` ·
`GET /api/admin/users/{id}/workspace`
`POST /api/auth/login` rewritten to mint a session.

## 6. Customer functionality fixed

Each session now resolves its own workspace. Verified with two concurrent
sessions: admin saw `hello@umangsatnam.in / agency`, customer saw
`umangptl11@gmail.com / growth`. Neither could see the other.

## 7. Admin functionality fixed

Plan change writes to the database and the customer's own dashboard reflects it
on the next request (growth → agency showed `automations: -1` to the customer).
Suspension ends every live session for that account immediately — the suspended
customer's next request returned **401**, not a cached page.

## 8–10. Automation, flow builder, analytics

Partly done in earlier work: the post → keyword → DM composer writes a real rule
bound to a real Instagram media id, and analytics counts people from real
records. **The flow builder (nodes/edges/positions/versions) is NOT built.**
Automation state is still `active`/`inactive`, not DRAFT/PUBLISHED/PAUSED/ARCHIVED.

## 11–12. SEO and legal pages

**Not started.** No `robots.txt`, no `sitemap.xml`, no favicon, no OG images,
no custom 404, no cookie banner, no per-page meta. `privacy.html` and
`terms.html` exist; a cookie policy does not.

## 13. Security fixes

Done: authentication, session management, RBAC on every route, PBKDF2,
HttpOnly/SameSite cookies, `COOKIE_SECURE` env flag for production, session
revocation on suspend, audit trail, atomic writes (a crash mid-write no longer
truncates a collection).

**Not done:** rate limiting, CSRF tokens on state-changing routes, input
validation beyond Pydantic's types, password reset, email verification, 2FA.

## 14. Mobile

Not revisited this phase.

## 15. Instagram integration — intentionally preserved

`core/meta_oauth.py` and `core/meta_api.py` are **byte-identical** to how they
were before this work, except that `meta_api.py`'s three file reads/writes now
go through `core/store.py` like every other module, so its config persists to
Postgres. No OAuth change, no permission change, no token-flow change, no second
integration, no mocked responses.

`core/instagram_account.py` is new (added earlier this week) and *reads* profile
and media using the token the existing OAuth already stored.

## 16. Tests performed

Against a real PostgreSQL 16 instance:

- Anonymous: 5 customer routes → 401, 4 admin routes → 401, `/app` `/admin`
  `/dashboard` → 303 to login. ✅
- Wrong password rejected. ✅
- Admin and customer signed in concurrently, each saw only their own workspace. ✅
- Customer hitting admin routes → 403 on all, `/admin` page → 403. ✅
- Legacy SHA-256 hashes verified, then silently upgraded to PBKDF2 — confirmed
  in the database. ✅
- Admin changed a plan → customer's own `/api/billing/status` reflected it. ✅
- Admin suspended a customer → that customer's live session returned 401. ✅
- Audit rows written for login, plan change and status change, with before/after. ✅
- **Every JSON file deleted, app restarted:** login, 2 users, 2 flows, 7 contacts,
  4 plans and all settings recovered from Postgres. ✅

### A data-loss bug this testing caught

Every manager guarded its read with `if os.path.exists(FILE)`. On a fresh
container with Postgres already holding the data, that answer is *no* — so each
manager re-seeded itself and **wrote the empty state back over the live
database.** The first Railway restart would have erased every customer. Fixed:
the guards now ask `store.exists()`, which asks Postgres first.

A second ordering bug: managers are constructed at import time, before FastAPI's
startup event, so `db.init()` in that event ran too late. Init is now lazy on
first use.

## 17. Remaining issues

1. **Phase 2 — the four restored features.** Inbox, Broadcast, AI Assist and
   Flow Tester are to be restored from backup and given real backends. Not started.
2. **Flow builder persistence** (nodes, edges, positions, versions).
3. **Automation lifecycle states** — DRAFT/PUBLISHED/PAUSED/ARCHIVED.
4. **Conversations and messages** have no tables yet; the Inbox depends on them.
5. **Usage limits are read but not enforced on send.** The counter exists; the
   block at the limit does not.
6. **No password reset, no email verification.** A locked-out customer today
   needs you to reset them by hand.
7. **No rate limiting** on login — brute force is only slowed by PBKDF2.
8. **No CSRF tokens.** SameSite=Lax covers the common case, not all of it.
9. **SEO and legal** (section 11) entirely outstanding.
10. **Mobile** not re-verified since the layout changed.
11. **`ADMIN_EMAIL`/`ADMIN_PASSWORD` must be set** before first boot on a fresh
    database, or there will be no way in.

## 18. External Meta/Instagram limitations

These are platform rules, not bugs, and no amount of code removes them:

- **750 private replies per hour** per Instagram account. A viral reel exceeding
  that will queue; we do not yet choose who to answer first.
- **One private reply per commenter**, within **7 days** of the comment.
- **24-hour messaging window.** After it closes, the person must message first.
- **Advanced Access via App Review** is required for `instagram_manage_comments`
  and the Human Agent feature before any of this works for customers who are not
  you.
- **Business or Creator accounts only.** Personal accounts cannot receive
  automated DMs.
- **One-click connect is currently off** because `app_id` and `app_secret` are
  blank in platform settings. No customer can self-connect until you fill them.

---

## What you need to do

1. Railway → New → Database → **PostgreSQL**, copy `DATABASE_URL` into the app's
   variables.
2. Set `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and `COOKIE_SECURE=1`.
3. Run `python migrate_to_postgres.py --write` once.
4. Admin → Instagram API: paste the Meta **app id** and **app secret**.

Until step 1, the app runs on JSON files exactly as before — nothing breaks.

---

# Addendum — 1 Oct 2026, evening

## Instagram is live

@satnamwebservices is connected on the deployed app: 301 followers, 14 posts,
real thumbnails. Comment → DM is reading real media through the existing
integration. The chain works end to end.

## Competitor name removed from the product

36 references, including:

- `MANYCHAT-STYLE VISUAL AUTOMATION STUDIO` in the flow builder header
- the `mc-` CSS prefix across **139 rules** and all the markup — now `fx-`
- `verify_token = "manychat_secret_token_123"`, which was both a brand leak and
  a guessable webhook secret; now `DEFAULT_VERIFY_TOKEN` from the environment
- the GitHub README title, which is the repo's public front page
- `"ManyChat Flow"` saved as a tag on live automation data

Strategy documents still name competitors, which is correct — that is what they
are for. Nothing a customer can see does.

## Claims we removed because we cannot stand behind them

| Was on screen | Why it went |
|---|---|
| "Official Meta Graph API v21.0 **Certified**" | Meta does not certify apps. Asserting a compliance status we were never granted is the kind of claim that costs an app its API access. |
| "**100%** Anti-Spam Spintax Protection" | No tool can promise 100%. Spintax varies the text; Instagram still decides. |
| "**0.5-second** automated response" | Never measured. The node now reads "Live". |

Replacements say what is true: *"Built on the official Instagram Messaging API ·
Replies in seconds · message variations so no two DMs are identical."*

## The follow-gate, and the bug that would have blocked your own followers

The gate was wired to `check_user_follows()`, which returns a plain **bool**.
A bool cannot distinguish *"they do not follow"* from *"Instagram would not
tell us"* — and those need opposite behaviour.

Meta's user-profile documentation states that profile access requires consent,
and that consent *"occurs only when a person messages the business"*. At the
moment a **comment** webhook fires, the commenter has not messaged you yet, so
the lookup can come back empty. Read as `False`, that **withholds the link from
people who do follow you** — every merchant would conclude the product is
broken.

`core/follow_gate.py` makes it three states:

| State | What happens |
|---|---|
| `FOLLOWS` | Send the real message and the link. |
| `NOT_FOLLOWING` | Send the follow prompt, hold the link. |
| `UNKNOWN` | Send a prompt that does **not** accuse them of not following, and let their reply open the conversation so the next pass can read the truth. |

Verified: a bad token returns `unknown`, never `not_following`.

`meta_api.py` was not modified — it stays the locked integration.

## Two multi-tenant bugs fixed alongside it

1. **The follow prompt named a hard-coded account.** `account_name = rule.get(...)
   or "satnamwebservices"` meant another merchant's follow-gate would send
   *their* audience to *your* Instagram. It now reads the rule owner's own handle,
   and falls back to empty rather than to anyone else's account.
2. **DM-keyword replies sent with no workspace token**, so they went out on
   whichever connection the global config happened to hold. Now always the rule
   owner's own.

The four message templates shipped with that handle written into them too; they
now carry `{handle}`, resolved to whichever account is connected.

## UI

- **The giant profile picture.** Two `.ig-avatar` rules existed; the second
  dropped `flex: none`, and `img.ig-avatar` (specificity 0,1,1) beat
  `.ig-avatar` (0,1,0) with `width: 100%` — so the avatar sized itself to the
  whole page. One rule now, 56px, and it wins because it is last.
- **Every node was clipped.** The canvas is a flex column in a fixed-height
  modal, so each node shrank (`flex-shrink` defaults to 1) and `overflow: hidden`
  sliced off the keyword chips, the gate toggle and the template row. Children
  keep their natural height; the canvas scrolls.
- **`&rarr;` printed literally** in three places — `textContent` does not decode
  HTML entities. Now a real `→`.
- **The studio was the only coloured surface left**: green, violet and blue on
  `.is-trigger` / `.is-condition` / `.is-action` modifiers that outranked the ink
  layer. The whole studio is monochrome now; the single red survives only on the
  blocked branch, where "this stops here" is the meaning.

Verified in a browser: zero clipped nodes, zero JS errors, and the only non-grey
values left anywhere in `style.css` are the three danger tones.
