# DM Flow — Meta App Review submission pack

Everything needed to submit the Instagram app for review, in the order Meta
asks for it. Written to be pasted, not re-written.

App: **1087830127189044** · Live: **https://instagram-tool-production-c3f0.up.railway.app**

---

## 0. Blockers — do these before you click Submit

| # | Thing | Why it matters | Status |
|---|---|---|---|
| 1 | **Use the INSTAGRAM app id and secret** | Instagram Login has its own pair, under **App Dashboard → Instagram → API setup with Instagram login**. It is *not* the Facebook pair at the top of the dashboard. Pasting the Facebook pair fails at the token exchange with *"Error validating verification code"* — an error that blames `redirect_uri` and sends you looking in the wrong place. | **Verify this first** |
| 2 | **Reviewer test account** | Meta needs working credentials. Put it on a plan that allows at least one live flow, or the reviewer hits an upgrade wall and fails you. | **Not done** |
| 3 | **Rename the Meta app to "DM Flow"** | The name on the authorisation screen must match the site, the privacy policy and the screencast. | **Not done** |
| 4 | **Configure the webhook on the new app** | Callback URL, verify token and the `comments` field are per app, and the new app has none of it. Connect, then press **Repair** once. | **Not done** |
| 5 | **Remove any Facebook / Pages use case** | `pages_show_list`, `pages_read_engagement` and friends come from a Facebook use case this product never calls. (`public_profile` is granted to every app and cannot be removed — ignore it.) | **Check** |
| 6 | **Set the brand name on production** | Production reads it from Postgres, not the repo. Admin → Branding → Name → `DM Flow`. | **Not done** |
| 7 | App icon | Required field, 1024×1024. | Done — `static/app-icon-1024.png` |
| 8 | Business email | Where the review result is sent. | Set `info@satnamwebservices.in` |
| 9 | Only three permissions requested | The new app has exactly the three this product uses. | Done |

### Switching to the new app, in order

1. Meta app → **Instagram → API setup with Instagram login** → copy the **Instagram App ID** and **Instagram App Secret**.
2. Paste both into **Admin → Instagram API** in DM Flow, save, and press **Test**. It now refuses the Facebook pair instead of showing a green tick.
3. **Disconnect and reconnect** the Instagram account — the old token belongs
   to the old app `874373775643660` and is worthless to the new one.
4. Press **Repair**, then **Read comments now**, and confirm the panel is green.

Do this *before* submitting. A reviewer hitting a signature failure sees a
broken app.

---

## 1. Permissions to request

Request exactly these three. Nothing else.

| Permission | Access level | Why we need it |
|---|---|---|
| `instagram_business_basic` | Advanced | Read the connected account's profile and media so the merchant can pick which post a flow belongs to. |
| `instagram_business_manage_comments` | Advanced | Read comments on the merchant's own posts to detect the trigger keyword, and post the public reply. |
| `instagram_business_manage_messages` | Advanced | Send the private reply (the DM) to the person who commented. |

Advanced Access is required because DM Flow serves many businesses, not one
account we own.

---

## 2. "How your app uses this permission" — paste these

### instagram_business_basic

> DM Flow is a comment-to-DM automation tool for small businesses. After a
> merchant connects their own Instagram professional account, we read their
> profile (username, profile picture, follower count) to confirm the correct
> account is linked, and we list their published posts and reels so they can
> choose which post an automation should apply to. We display this information
> only to the merchant who owns the account, inside their own workspace. We do
> not read or store any other account's profile or media.

### instagram_business_manage_comments

> DM Flow reads comments on the connected merchant's own posts to find the
> keyword the merchant configured — for example "LINK" under a product reel.
> When a comment matches, we optionally post a short public reply to that
> comment on the merchant's behalf, which the merchant writes themselves.
> Comments are used only to decide whether an automation should run and to
> capture the commenter as a lead in the merchant's own CRM. We do not read
> comments on posts that do not belong to the connected account.

### instagram_business_manage_messages

> When a comment matches a merchant's keyword, DM Flow sends a private reply
> to that comment — the message the merchant wrote, usually a product link or a
> discount code the commenter asked for. We send exactly one private reply per
> comment, within Meta's seven-day window, and only in direct response to a
> comment the person left on the merchant's post. Merchants can also require
> the commenter to follow the account before the link is sent; in that case we
> send a single message asking them to follow. We do not send unsolicited
> messages, bulk messages, or messages to people who have not interacted with
> the merchant's content.

---

## 3. Reviewer instructions — paste into "Step-by-step instructions"

> **Test credentials**
> URL: https://instagram-tool-production-c3f0.up.railway.app/login
> Email: review@satnamwebservices.in
> Password: <set this and fill it in>
>
> **Steps**
>
> 1. Sign in at the URL above with the credentials provided. You land on the
>    Home screen of a merchant workspace.
> 2. If no Instagram account is linked, press **Connect Instagram** and
>    authorise with your own Instagram professional (Business or Creator)
>    account. The account's profile picture, handle and follower count appear.
> 3. Your published posts and reels load below the profile. Tap any post.
> 4. In the panel that opens, set a trigger keyword (for example `LINK`), write
>    the DM that should be sent, optionally add a button and a link, and press
>    **Turn on**. The post is now marked live in the grid.
> 5. From a **different** Instagram account, comment the keyword on that post.
>    (Instagram does not allow an account to message itself, so a comment from
>    the connected account itself is intentionally ignored.)
> 6. In DM Flow press **Read comments now** in the "Is it working?" panel.
>    The comment appears under **Recent events** with the verdict **DM sent**,
>    and the second account receives the private reply.
> 7. Open **Contacts** to see the commenter captured as a lead.
> 8. To see the follow-gate: turn on "Require follow" on the flow and repeat
>    step 5 from an account that does not follow the merchant. The event shows
>    **Follow-gate held it** and that account receives a single message asking
>    them to follow instead of the link.
>
> **Note for the reviewer:** because this app is not yet published, Meta does
> not deliver live `comments` webhooks, so DM Flow reads comments through
> the Graph API every 60 seconds instead. The **Read comments now** button
> performs that read immediately so you do not have to wait.

That last paragraph matters. It explains, before the reviewer wonders, why the
flow is not instant — without it, "I commented and nothing happened for a
minute" reads as a broken app.

---

## 4. Screencast — the shot list

One continuous recording, no cuts, around three minutes, screen plus the phone.
Meta rejects videos that skip the authorisation screen or show mock data.

1. **(0:00)** Browser at the login page. Sign in. — *proves the app is real and reachable.*
2. **(0:15)** Home screen with no account linked. Press **Connect Instagram**.
3. **(0:25)** **Film the whole Instagram authorisation screen**, including the
   permission list, and accept. This is the shot reviewers look for first.
4. **(0:45)** Profile and real posts load. — *`instagram_business_basic`.*
5. **(1:00)** Open a post, set keyword `LINK`, write the DM, add the link
   button, turn the flow on.
6. **(1:30)** Switch to a phone screen recording. A **second** Instagram account
   opens the post and comments `LINK`.
7. **(1:50)** Back to the browser. Press **Read comments now**. The event
   appears: `@account commented "LINK" — and a DM went out`.
   — *`instagram_business_manage_comments`.*
8. **(2:10)** Back to the phone. The second account's inbox shows the DM with
   the button. Open it. — *`instagram_business_manage_messages`.*
9. **(2:30)** Browser → **Contacts**, the commenter is there as a lead.
10. **(2:45)** Turn on **Require follow**, repeat the comment from a
    non-following account, show **Follow-gate held it** and the follow request
    message arriving.

Record it after the secret rotation, so what Meta watches is what Meta will
test.

---

## 5. App settings to fill in

| Field | Value |
|---|---|
| App icon | `static/app-icon-1024.png` |
| Category | Business and pages |
| Privacy Policy URL | `https://instagram-tool-production-c3f0.up.railway.app/privacy` |
| Terms of Service URL | `https://instagram-tool-production-c3f0.up.railway.app/terms` |
| User Data Deletion | **Callback URL** → `https://instagram-tool-production-c3f0.up.railway.app/api/meta/data-deletion` |
| Business email | `info@satnamwebservices.in` |
| App display name | `DM Flow` — must match the site and the screencast |
| OAuth Redirect URI | `https://instagram-tool-production-c3f0.up.railway.app/api/instagram/callback` |
| Webhook Callback URL | `https://instagram-tool-production-c3f0.up.railway.app/api/meta/webhook` |
| Webhook fields | `comments`, `messages`, `messaging_postbacks`, `message_reactions`, `live_comments` |

Configure the webhook **inside the Instagram product**, not on the generic
Webhooks page — Meta's own notice says Instagram-Login webhook configuration is
supported only there.

The deletion callback is now implemented for real: it verifies Meta's
`signed_request` against the app secret, removes the access token, the cached
profile and media, the contacts captured from that account's comments and the
event records naming that workspace, then returns a confirmation code that
resolves on `/deletion?code=…`.

---

## 5b. About the rename

The product is **DM Flow** everywhere a person can read it — site, dashboard,
emails, legal pages, page titles, the post-authorisation screen. Three things
were deliberately left alone, because renaming them breaks a live connection
rather than a label:

- `converflow_webhook_token` — the webhook verify token, which must keep
  matching what is typed into the Meta app. Changing it silences the webhook.
- `converflow123` — the default password in the admin's user-creation path.
- The `User-Agent` the locked Instagram module sends (`ConverFlow/3.0`). It is
  invisible to everyone and the module is under a do-not-touch rule, so the
  bytes it puts on the wire are unchanged.

Meta's branding rules were checked: app names may not contain *Insta*, *Gram*,
*IG*, *Face*, *Book*. "DM Flow" uses none of them.

---

## 6. After approval

1. **Publish the app** (App Review → toggle to Live). Until this, no production
   webhooks are delivered to anyone.
2. Press **Repair** once, then confirm **"This account allows comment events"**
   is green.
3. Watch **Recent events** — entries should start arriving with source
   `webhook` rather than `poll`.
4. Leave polling on for a week as a safety net; the two paths de-duplicate, so
   nobody gets two DMs. Turn it off later with `POLL_ENABLED=0` if you want to.
