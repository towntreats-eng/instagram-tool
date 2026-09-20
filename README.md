# ManyChat for Instagram — Full Automation & Chatbot Suite 🚀

An Instagram Marketing Automation platform modeled after **ManyChat**, featuring **Comment-to-DM Growth Tools**, **DM Keyword Auto-Responders**, **Visual Flow Builder**, an **Interactive Mobile Flow Simulator**, **Contacts & Lead CRM**, and an **Outreach Broadcast Engine** with anti-ban protection.

---

## 🌟 ManyChat Features Included

### 1. 💬 Comment-to-DM (Comment Growth Tool)
- Automatically triggers when followers comment on your Reels or Posts.
- Filters by specific keywords (e.g. `LINK`, `GUIDE`, `PRICE`, `EBOOK`) or wildcard `*` (Any comment).
- **Public Comment Reply**: Rotates humanized responses via Spintax (`"{Sent you a DM! 🚀|Check your inbox! 📩}"`).
- **Instant Private DM**: Automatically dispatches the promised link/lead magnet directly to their DMs.

### 2. ✉️ DM Keyword Auto-Responder
- When a user DMs you a trigger keyword (e.g. `"PRICE"`, `"START"`, `"SUPPORT"`), the bot automatically sends interactive response menus and links.

### 3. 📱 Interactive Mobile Phone Simulator
- Virtual smartphone preview right inside your dashboard.
- Test your chatbot triggers as a Comment or Direct Message.
- Live chat bubbles show what the user sent, the bot's public reply, the private DM delivered, and the CRM tags assigned!

### 4. 👥 Contacts & Lead CRM
- Automatically tracks and logs every follower who interacts with your automations.
- Captures handle, display name, interaction source, message count, and customizable tags (`Hot Lead`, `Reel Comment`, `Ebook Downloaded`).
- Searchable and downloadable as CSV.

### 5. 📢 Broadcast / Outbound Outreach Engine
- Cold lead list outreach runner with anti-ban randomized delays (45s–90s) and daily safety cap.
- Spintax message builder with dynamic placeholders (`{username}`, `{name}`, `{first_name}`).
- Real-time terminal console with Server-Sent Events (SSE).

---

## 🚀 How to Run

### Quick 1-Click Launch (Windows)
Double-click:
```
start.bat
```
Or via terminal:
```powershell
python run.py
```
Your browser will open `http://localhost:8000` with the ManyChat dashboard!

---

## 🧭 Navigation Guide

- ⚡ **Automations**: View, edit, activate/deactivate, or create new Comment-to-DM and Keyword rules.
- 📱 **Flow Simulator**: Type keywords into the virtual phone to test how your bot replies.
- 📢 **Outreach / Broadcast**: Load target leads via CSV or manual paste to send personalized DM campaigns.
- 👥 **Contacts & CRM**: Browse captured leads, inspect tags, and export CSV reports.
- ⚙️ **Account & Settings**: Connect your Instagram account via persistent browser session and configure live watcher intervals.

---

## 🗺️ Routes (v3 — full SaaS shell)

| URL | What it is |
|-----|------------|
| `/` | Marketing landing page (hero, features, how-it-works, pricing, testimonials, FAQ) |
| `/pricing` | Detailed pricing + comparison table + billing FAQ |
| `/signup` | Create a workspace — writes a real user into `data/users.json` |
| `/login` | Sign in (demo: `hello@umangsatnam.in` / `converflow123`) |
| `/app` | The product dashboard (was `/` before) |
| `/admin` | Admin console — users, subscriptions, revenue, health, announcements |

## 🛠️ Admin console

- **Overview** — MRR, lifetime revenue, workspaces, trial→Pro conversion, DM volume, revenue & signup charts, plan-mix donut, recent payments.
- **Users** — search/filter by plan and status, make Pro, downgrade, +7 trial days, suspend, delete, per-workspace drawer with payment history.
- **Revenue** — MRR / ARR / ARPU and the full payment ledger.
- **System health** — platform event log with level filters.
- **Announcements** — publish an in-app notice (served at `/api/auth/announcement`).
- **Plan settings** — pricing constants and CSV exports.

## 🧱 Data model

`data/users.json` holds every workspace: plan (`trial` / `pro` / `expired`), status, usage stats and payment history.
Pricing constants live in `core/user_manager.py` (`PRO_PRICE_INR`, `TRIAL_DAYS`).
Payments are recorded manually for now — swap `set_plan()` for a Razorpay verify callback when you go live.

---

## 💸 Pricing (v3 — configurable from the admin panel)

| Plan | Price | Automations | Contacts | DMs / month | Highlights |
|------|-------|-------------|----------|-------------|------------|
| Free | ₹0 | 1 | 100 | 200 | Comment-to-DM + keyword replies, CSV export |
| Starter | ₹399 | 3 | 1,000 | 2,000 | Wildcard trigger, no branding |
| **Growth** | **₹799** | Unlimited | 5,000 | 15,000 | Story mentions, broadcast, AI assist, analytics, 15-day trial |
| Agency | ₹1,999 | Unlimited | 25,000 | Unlimited | 3 IG accounts, 5 seats, white-label |

Benchmark (Sept 2026): ManyChat Essential ≈ ₹1,245/mo for 250 contacts, ManyChat Pro ≈ ₹3,735/mo for 2,500.
Indian rivals sit at ₹99–₹799 flat. Growth undercuts ManyChat Pro ~4.7× while leaving headroom above Starter.

Prices, limits and features are **data**, not code — edit them in Admin → Plans & pricing and the website,
signup and every limit check update instantly.

## 📸 Instagram connect (one Meta app, every customer)

1. Admin → Instagram API → paste App ID, App Secret, Redirect URI, verify token → **Test connection**
2. Customers open Settings → **Connect Instagram** → Facebook consent → done

Tokens are exchanged for long-lived ones and stored per workspace. No customer ever sees an App ID.
Webhook subscription for `comments`, `messages` and `mentions` happens automatically on connect.

## 🧩 What the admin panel controls

| Section | What you can do |
|---------|-----------------|
| Overview | MRR, lifetime revenue, workspaces, conversion, revenue & signup charts, plan mix |
| Users | Search/filter, change plan, extend trial, suspend, delete, per-workspace drawer |
| Revenue | MRR / ARR / ARPU and the full payment ledger |
| Plans & pricing | Build the ladder — prices, limits, features, badges, trial length, new plans |
| Offers & coupons | % off, flat ₹ off, free months, trial extensions; scope by plan, cap redemptions |
| Instagram API | Meta app credentials, test connection, see every connected account |
| System health | Platform event log with level filters |
| Announcements | In-app notices broadcast to users |
| Email templates | Welcome, IG connected, trial ending/expired, payment, suspended |
| Platform settings | Brand, billing/GST/Razorpay, safety defaults, feature switches, CSV exports |

## 🖥️ Dashboard pages

Home · Contacts · Automation · AI Assist · Inbox · Flow Tester · **Broadcast** · **Analytics** · **Plan & billing** · Settings

New in v3: the Broadcast runner, an Analytics page, a Plan & billing page with live usage meters and
in-app plan switching, and a Connect Instagram card in Settings.
