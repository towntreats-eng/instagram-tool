# ConverFlow — Competitive Strategy
**Where ManyChat and every rival leaks, and exactly what we build instead**

Prepared: 20 September 2026 · Owner: Umang · Status: this is the build spec for the dashboard redesign

---

## 0. The one-line thesis

> ManyChat is a **messaging platform that bills you for growing**.
> ConverFlow is a **revenue tool that bills you a flat fee and shows you the money**.

Everything below is evidence for why that wins, and what it forces us to build.

---

## 1. The market, priced honestly

| Tool | Real monthly cost (INR) | Billing model | India-ready? |
|---|---|---|---|
| ManyChat Free | ₹0 | **25 contacts** (capped Mar 2026) | ✗ |
| ManyChat Essential | ~₹1,245 | 250 contacts, then ₹9/contact | ✗ USD, no GST |
| ManyChat Pro | ~₹3,735 | 2,500 contacts, then ₹4.5/contact | ✗ USD, no GST |
| ManyChat Business | ~₹5,900 | 7,500 contacts | ✗ |
| Chatfuel / Landbot | ₹2,000–4,000 | contact or session tiers | ✗ |
| LinkDM | ~₹1,577 | flat | ✗ no UPI |
| CreatorFlow | ~₹1,245 | flat | ✗ no UPI |
| InstantDM | ~₹747 | flat | ✗ no UPI |
| Hypello | ~₹408 | flat | ✗ no UPI |
| QuickDM | ₹399 | flat, 185 DM/hr | ✓ UPI |
| ReplyKaro | ₹99 | flat, basic | ✓ UPI |
| UnlockDM | ₹299–1,499 | **per campaign** | ✓ UPI |
| **ConverFlow** | **₹0 / 399 / 799 / 1,999** | **flat, contacts included** | **✓ UPI + GST + INR** |

Add to every USD tool: **2–3.5% forex markup + 18% GST**, and currency-conversion spreads reported up to 15%.
ManyChat Pro's real landed cost for an Indian buyer is closer to **₹4,400/month**.

**Our position:** Growth (₹799) is ~5.5× cheaper than ManyChat Pro's landed cost, and we sit above the
₹99–₹399 bottom feeders on capability. We are not the cheapest and we should never try to be —
ReplyKaro owns that and it's a bad neighbourhood. We are *the one that pays for itself*.

---

## 2. Where they leak — six wounds, all confirmed

### LEAK 1 — Active-contacts billing punishes success
This is the biggest single wound in the category.

ManyChat charges for "anyone who interacted with an automation in the last 30 days." A reel goes viral,
contacts jump 800 → 4,600, and the creator gets **$29 base + $40 overage** with a prompt to upgrade to
$69. At 10,000 contacts it's $114/month against flat-rate rivals at $24 — a **$1,080/year gap**.

Documented complaint patterns: *viral-post shock*, *unused-channel tax* (paying for WhatsApp/Messenger
they never touch), *free-tier eviction* (the 25-contact cap from March 2026), *overage creep*.

> The emotional damage matters more than the money: **their best day becomes a bill.**

**We build:** flat plans, contacts included, and a Plan page that says *"a viral reel will not change your
bill"* in plain words. No per-contact line item exists anywhere in our product. Ever.

---

### LEAK 2 — Connecting the account is where users die
ManyChat's own community is full of connection failures. The pattern from a live thread:

> "No pop-up window appears. No error message appears. No new screen loads."

- Silent failure with zero diagnostics
- **Order-sensitive**: you must connect Facebook *before* Instagram, and nothing tells you that
- Prerequisites buried in Meta Business Manager: Professional account, linked Page, asset permissions
- Community moderators can't fix it — everything escalates to a support ticket
- Support is rated "nonexistent", "slow replies, difficulty reaching a human"

This is the single highest-leverage thing we can beat them on, because it's the **first five minutes**
of the product. Every user hits it; most competitors lose people right here.

**We build:** a connection flow that is physically incapable of failing silently —
a 5-step checklist with live per-step status, a named reason for every failure, and a one-line fix
next to it. See §4 "Connection Doctor".

---

### LEAK 3 — Nobody shows you the safety margin
Instagram enforces roughly **200 messages/hour** and **1,000/day**. Break them and you get
"Action Blocked", "Try Again Later", or — worst — **silent failures where nothing happens and nothing
is reported**. Tools don't tell users these limits exist, don't show how close they are, and don't
explain official-API vs unofficial.

Fear of a ban is the #1 reason Indian creators *don't* buy an automation tool. Every competitor treats
it as a footnote in a blog post.

**We build:** a live **Safety cockpit** — hourly and daily headroom as a meter, the exact numbers, and
an honest status line. Turn the category's biggest fear into our most visible trust signal.

---

### LEAK 4 — The analytics stop exactly where the money starts
Confirmed gap across the category:

- Instagram Insights **does not track link clicks inside DMs** at all
- CreatorFlow has no multi-touch attribution or funnel visualisation
- LinkDM offers "basic click tracking" only; you're pushed to set up GA4 yourself
- Tools measure *DM-layer* metrics; creators need *revenue* metrics

What creators actually want and nobody ships:
**revenue per automation**, **cost per lead by trigger type**, **conversion by content format**
(Reel vs Carousel vs Story), **drop-off by funnel stage**, **click-to-sale rate**.

One more finding worth building a whole feature around: **sub-60-second replies convert ~21× better.**
No competitor surfaces median response time as a metric.

**We build:** an Analytics page organised as a funnel — Comments → DMs sent → Links clicked → Orders —
with per-keyword revenue, and a Speed tile showing median reply time against the 60-second line.

---

### LEAK 5 — India is an afterthought everywhere
Universal across USD tools: no UPI, no GST-compliant invoice, no INR pricing, no local support hours,
no Hinglish. Indian creators eat a 15% cost penalty before the product does anything.

**We build:** ₹ everywhere, UPI-first checkout, a GST invoice auto-generated per payment,
WhatsApp support (not a ticket queue), Hinglish copy where it helps.

---

### LEAK 6 — Reliability and support rot at the edges
From reviews: platform instability, "occasional sending errors and glitches" on SMS and Instagram,
an Instagram comment-reply implementation described as "strange", follow-to-DM that doesn't work
consistently, billing that continues after cancellation requests go unanswered.

**We build:** a visible health strip — last webhook received, watcher status, delivery success rate —
so the user knows the machine is alive without asking support. And cancellation that is one button,
self-serve, no email.

---

## 3. What we deliberately do NOT copy

| ManyChat has | We skip it | Why |
|---|---|---|
| WhatsApp + Messenger + SMS + TikTok | Instagram only, done properly | Their breadth is the "unused-channel tax" users resent. Depth beats breadth for a ₹799 tool. |
| A 40-node visual flow builder | 4-step guided builder + advanced mode | Their own reviews cite a learning curve. Most creators build one flow: comment → reply → DM → link. |
| AI agent marketplace | One AI that writes the flow | Reviews say "limited AI options" — but nobody asked for an agent zoo. |
| Contact-based tiers | Flat plans | It's the wound. Don't reopen it on ourselves. |

Breadth is how they justify $29. Our answer is not more features — it's **the same job, finished**.

---

## 4. What this forces into the product

Six features, each aimed at a named leak. This is the redesign brief.

| # | Feature | Kills leak | What it is |
|---|---|---|---|
| 1 | **Connection Doctor** | 2 | 5-step connect with live status per step, named failure reason, one-line fix. Never a silent fail. |
| 2 | **Safety cockpit** | 3 | Live hourly/daily send headroom, honest limits, pause-before-block. |
| 3 | **Revenue funnel** | 4 | Comments → DMs → Clicks → Orders, with revenue per keyword. |
| 4 | **Speed tile** | 4 | Median response time vs the 60-second line. |
| 5 | **Flat-bill promise** | 1 | Usage meters that reassure instead of threaten. "A viral reel will not change your bill." |
| 6 | **India rail** | 5 | ₹, UPI, GST invoice, WhatsApp support. |

---

## 5. Design principles for the dashboard

1. **Answer the money question on every screen.** Every page shows what it earned or what it cost.
   ManyChat shows sends; we show rupees.
2. **Never fail silently.** Every failure state has a cause and a fix on screen. This is our whole
   differentiation on onboarding.
3. **Show the margin, not just the meter.** "34 of ~200 this hour — you're safe" beats a naked number.
4. **One primary action per page.** Their learning-curve complaints come from screens with no obvious
   next move.
5. **Reassure on limits, don't threaten.** Their meters exist to upsell. Ours exist to calm.
6. **Speak like a person.** "Your reel got 412 comments — term 'PRICE' made ₹18,400" not
   "Engagement metrics dashboard".

---

## 6. Honest counter-case

I should state where this argument is weak, because pricing strategy built only on a competitor's
flaws is fragile:

- **Flat pricing has a floor.** A user with 50,000 contacts costs us real compute and Meta API calls.
  Our Agency tier caps at 25,000 for a reason — past that we need a custom price, not a bug.
- **ManyChat's breadth is a real moat for agencies** managing WhatsApp + Messenger + IG for clients.
  We lose those deals. That's an acceptable loss; they are not our buyer.
- **"Better analytics" is easy to say and hard to ship.** Revenue attribution needs the user to tag
  their links or connect Shopify. If we promise revenue numbers and show zeros, we're worse than
  ManyChat, not better. Ship the funnel first, revenue second, and only for users who connect a store.
- **Their support being bad is not a durable advantage.** They can fix it with money. Our durable
  advantages are the flat bill, the connection flow, and India-native billing — all structural.

---

## 7. What ships in this redesign

Every dashboard page rebuilt against §5, with §4's six features placed:

- **Home** — one-screen answer: what happened, what it earned, what needs you
- **Automations** — per-automation revenue, not just on/off toggles
- **Flow Tester** — unchanged concept, cleaner execution (this is already better than ManyChat's)
- **Inbox** — response-time surfaced, because 60 seconds is worth 21×
- **Contacts** — value per contact, not a passive list
- **Analytics** — the revenue funnel + speed tile
- **Broadcast** — safety cockpit front and centre
- **Plan & billing** — the flat-bill promise, stated out loud
- **Settings** — Connection Doctor

---

## Sources

- ManyChat pricing & the active-contacts trap — creatorflow.so/blog/manychat-pricing-trap
- ManyChat official pricing — manychat.com/pricing
- ManyChat user reviews, 4.6/5 from 72 reviews, cons — capterra.com/p/206636/ManyChat
- ManyChat community, connection failures — community.manychat.com
- Instagram automation blocks & rate limits — creatorflow.so/blog/instagram-automation-blocked-fix
- DM automation analytics gaps — creatorflow.so/blog/instagram-dm-automation-analytics-guide
- India INR pricing comparison — tryunlockdm.com/blog/instagram-dm-automation-india-2026
- India creator tool problems — creatorlanehq.com/blog/best-instagram-dm-automation-tools-india

---

# Appendix A — Feature audit vs ManyChat (25 Sept 2026)

Run after Instagram connect went live. The question was not "what else can we
build" — it was **"what are we shipping that creates chaos?"**

## A.1 What we found in our own app

Two features were not just noise. They were **not real**, and a customer would
have found out within thirty seconds.

| Feature | What it looked like | What it actually was |
|---|---|---|
| **Inbox** | A full DM inbox with threads from Sarah Jenkins, Mike Ross, Priya Sharma | `const inboxThreadsData = [...]` — a hardcoded array. No inbox API exists. |
| **AI Assist** | "Generate Complete Flow with AI" | A `setTimeout` and an if-else ladder: `if (offer.includes("canva")) mainWord = "CANVA"`. No model, no API call. |

Shipping these to a paying customer is worse than chaos — it is a trust
failure on day one, and it is the *exact* complaint pattern we documented
against ManyChat (LEAK 6: features that don't work consistently).

**Both removed from the navigation.** The code stays in the repo, dormant, so a
real inbox and a real AI step can be built later and switched back on. Nothing
in the product now points at either.

A third was real but misplaced:

| **Flow Tester** | Worked fine | But it was a *destination*. Testing belongs on the automation you are testing — the card already has a "Test it" button. |

## A.2 Navigation: 10 → 7

Before: Home · Contacts · Automation · AI Assist · Inbox · Flow Tester ·
Broadcast · Analytics · Plan & billing · Settings

After: **Home · Contacts · Automations · Broadcast · Analytics · Plan & billing
· Settings**

Ten destinations for a tool whose whole job is "comment → DM" was the chaos.

## A.3 Feature-by-feature against ManyChat

| Capability | ManyChat | ConverFlow | Call |
|---|---|---|---|
| Comment-to-DM | ✓ | ✓ | **Parity — this is the job** |
| DM keyword replies | ✓ | ✓ | Parity |
| Story mention trigger | ✓ | ✓ (Growth+) | Parity |
| Visual flow builder | 40+ node canvas | One-step composer + card view | **Deliberately different** |
| Broadcasts | ✓ | ✓ (Growth+) | Parity |
| Live inbox | ✓ real | ✗ removed | **Gap, honestly marked** |
| AI flow generation | ✓ real | ✗ removed | **Gap, honestly marked** |
| WhatsApp / Messenger / SMS / TikTok | ✓ | ✗ | Won't build — this is their "unused-channel tax" |
| Contacts CRM | ✓ | ✓ | Parity |
| Revenue funnel analytics | ✗ | ✓ | **We win** |
| Reply-speed metric | ✗ | ✓ | **We win** |
| Live send-safety headroom | ✗ | ✓ | **We win** |
| Connection diagnostics | ✗ (silent failures) | ✓ Connection Doctor | **We win** |
| Flat pricing | ✗ per active contact | ✓ | **We win** |
| UPI / INR / GST | ✗ | ✓ | **We win** |

Two honest gaps, six wins, parity on the core. That is a defensible position —
and far better than claiming two features we hadn't built.

## A.4 One step to an auto-DM

The old path was a **4-step wizard** (pick post → keyword → message → publish).
The new path is one screen with every field pre-filled:

1. **When someone comments** — `PRICE`, with one-tap suggestions and "any comment"
2. **Send them this DM** — pre-written, `{name}` merges their Instagram name
3. **Link** — optional
4. **On which post** — "Every reel" is pre-selected; recent reels are one click

Everything else (public reply, tags) sits behind **Advanced**, pre-filled.

> **Shortest working path: open → type one word → press "Turn it on".**
> Verified: 3 automations → 4, live immediately.

The 4-step wizard still exists in the code but nothing points at it.

## A.5 Bugs this audit surfaced

| Bug | Impact |
|---|---|
| `/api/wizard/publish` and the toggle gate still used the retired `BillingManager` | An **Agency (unlimited)** workspace was blocked from creating an automation, with an upsell for **₹299/month — a plan that no longer exists**. The one-step button was dead on arrival. |
| `trigger_scope` was wired to the post picker | Typing `PRICE` silently saved a **catch-all `*` rule**. The user would think they'd set a keyword and every comment would fire. |
| `BillingManager` still imported | Retired entirely so it cannot be wired back in. |

Both gate bugs are the same root cause: a pricing rewrite that left the old
single-plan logic in the enforcement path. Worth remembering — **the gate is
where stale pricing hides**, not the pricing page.
