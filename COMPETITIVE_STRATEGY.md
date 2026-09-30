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

## Appendix B — The ink system, and becoming a real SaaS

### Why we stopped looking like a copy

The root cause was in the CSS, not in the layout. Our design tokens read:

```css
--mc-green: #00824b;   /* mc = ManyChat. That hex IS their brand green. */
```

Every card, every button, every active nav pill inherited a competitor's
brand colour. No amount of rearranging components fixes that.

So the palette is now a single ink scale — `--ink-000` through `--ink-950`
— and exactly one hue survives, `--danger: #b42318`, reserved for
destructive actions and failures. Across all three stylesheets the only
non-grey values that remain are that red and its two tints. That is
checkable in one command, and it should stay checkable:

```bash
grep -oE '#[0-9a-fA-F]{6}' static/css/*.css | # any new colour shows up here
```

The old `--mc-*` names are kept as aliases pointing at the ink scale, so
roughly 4,600 lines of existing rules re-skinned without touching markup.
They should be retired as files are next edited, not in one sweep.

### Three rules the new system runs on

1. **Structure by hairline, not by shadow.** Cards are ruled, not floating.
   Only things that genuinely sit above the page — menus, modals, toasts —
   get a shadow. This is the cheapest and largest visual difference from
   every green-on-white automation tool.
2. **Hierarchy by type and space**, because there is no hue left to carry it.
   Uppercase micro-labels, tabular figures, tight tracking on display sizes.
3. **State by form, not by colour.** Filled dot = live, ring = paused,
   hatched = not measured, red = failed. This survives a colour-blind user,
   a bad monitor, and a printout — and it is why the "Ordered" funnel stage
   reads as *unmeasured* rather than as *zero*.

The left rail is ink and the canvas is white. That single inversion is what
makes the product recognisable at a glance as ours.

### The flow, instead of scattered settings

The sidebar was ten flat destinations. It is now eight in three named groups:

| Group | Items | The question it answers |
|---|---|---|
| **Run** | Home, Automation, Inbox | What is happening right now? |
| **Grow** | Broadcast, Contacts, Analytics | How do I make it bigger? |
| **Account** | Plan & billing, Settings | What am I paying, and is it connected? |

Two entries were removed from the rail. *AI Assist* was a separate
destination for something that belongs inside the composer. *Flow Tester*
is a step in building an automation, not a place you visit — it is still
reachable from the automation itself. Mobile carries five.

### Payments

Razorpay, over plain REST, in `core/razorpay_client.py`. No SDK: the three
calls we make are short enough that anyone can audit the money path in one
file.

Three rules the code keeps:

1. **The browser never names a price.** It sends a plan id; the server
   prices it from the live catalogue and applies the coupon. A merchant
   cannot type themselves onto Agency from the console.
2. **A plan changes only after the signature verifies** against our secret,
   server-side. `POST /api/billing/verify` recomputes the HMAC and refuses
   anything that does not match, with a message that tells the customer
   plainly that nothing has been charged.
3. **The webhook and the browser callback are both idempotent.** Whichever
   arrives second finds the payment id already recorded and does nothing.
   The webhook exists for the case that actually loses money: a customer
   who paid and then closed the tab.

Without keys configured, checkout returns `manual_fallback: true` and the
UI drops back to the manual upgrade path, so the product still works while
the gateway is being set up.

**What Umang still has to do:** paste live keys into Admin → Platform
settings → Billing, press *Test keys* (it opens a ₹1 order and throws it
away), then add the webhook URL shown on that screen to Razorpay and
subscribe it to `payment.captured` and `order.paid`.

### Bugs this pass surfaced

- **The Automations KPI strip was three-quarters fiction.** "Reels Protected
  1 / 1 · Free Tier", "142 DMs · 99.8%", "28.4% Avg Conversion" were literal
  HTML, shown to an Agency workspace with unlimited automations, directly
  contradicting the "2 / ∞" chip on the same screen. All four cards now come
  from `/api/billing/status` and `/api/insights`, and where a thing is not
  measurable they say so rather than printing a flattering guess.
- **`BillingManager` was still gating activation** with a ₹299 plan that no
  longer exists, so the one-step publish button was dead for paying
  customers. Both gates now go through `user_manager.can_activate_automation()`;
  the class is retired.
- **"1 active automations"** on the Free plan, in two separate renderers.
- **The "MOST POPULAR" badge wrapped to two lines** and crashed into the plan
  name on the pricing grid.
- **`.hint` and `.btn-ghost` had no CSS rules at all** — the admin billing
  panel rendered helper text at body size with a chromeless button.

### What is still open

- `dm_engine` has no `replied_at` stamp, so reply speed is still an estimate
  flagged `estimated: true`. Until that lands we should not claim a measured
  median anywhere.
- The Inbox ships with demo threads. Real inbox data or an honest empty
  state, before anyone pays.
- The admin "Signups per month" axis repeats tick labels on small integer
  ranges.
