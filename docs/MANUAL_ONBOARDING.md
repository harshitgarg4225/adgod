# Salmor — Review-free launch for the first few clients

You do **not** need Meta App Review or a WhatsApp WABA/green-tick to run ads and deliver
leads for your first customers. Operate as an **agency** and use the client's **own
WhatsApp number**. This is standard, policy-compliant operation — not an evasion.

## What each "review" is actually for (so you know what you're *not* blocked by)

| Gate | When it's required | How you skip it for the first few |
|---|---|---|
| **Meta App Review** (`ads_management`) | Only for the **self-serve OAuth** flow where strangers log into *your* app | Run ads from **your** Meta Business Manager with a **System User token** on the client's ad account. No App Review. |
| **WhatsApp WABA + green-tick + template approval** | Only for the **automated AI qualifier** (Cloud API) | Use **`APP_DESTINATION`**: the Click-to-WhatsApp ad opens the client's **own** WhatsApp number. No API, no templates. The owner (or you) replies. |
| **Razorpay activation** | Only to auto-charge subscriptions | Bill the first few by hand (your own UPI/link). The product runs ads + leads without it. |

## What you *do* need
- Your **Meta Business Manager** + a **System User token** (System Users → Generate Token,
  with `ads_management`, `business_management`). Add each client's ad account (or create
  one for them under your Business) and their Facebook Page.
- An **LLM key** (`ANTHROPIC_API_KEY` and/or `GEMINI_API_KEY`) and optionally **`FAL_API_KEY`**
  for real image/video creative.
- The client's **WhatsApp number** (for `APP_DESTINATION`).
- A deployed instance with strong `JWT_SECRET` / `TOKEN_ENCRYPTION_KEY`, `MOCK_META=false`,
  `MOCK_LLM=false`, `MOCK_WHATSAPP=true` (own-number mode makes no WhatsApp API calls).

## Provision a client in one command

```bash
python -m leadpilot.scripts.provision_client \
  --business "Verma Dental" --category clinic --city Indore \
  --owner-phone +919812345678 --daily-budget 500 --language hi \
  --autopilot ASSISTED \
  --meta-business <YOUR_BM_ID> --ad-account <CLIENT_AD_ACCT> --page <CLIENT_PAGE> \
  --meta-token "EAAG...<your System User token>"
```

This creates the tenant + owner + account + business profile, stores the Meta connection
(token encrypted at rest), and sets WhatsApp to `APP_DESTINATION` on the client's number.
The owner logs into the app with **phone OTP** (their `--owner-phone`).

## Before you launch: one Meta precondition
Link the client's **WhatsApp number to their Facebook Page** (Page Settings → WhatsApp →
Connect). CTWA ad sets promote the Page with `destination_type=WHATSAPP`; a Page with no
linked WhatsApp number gets the launch rejected by Meta. The wa.me deep link in the ad
uses `--owner-phone`, so make sure it's the number customers should land on.

## What "autopilot" means now (the owner's four wants)
The owner wants ads running, leads on their phone, one daily-budget dial, and silence
otherwise. That is the default behaviour:
- **Autopilot with veto (default):** ASSISTED accounts auto-approve and launch their ads
  **6 hours** after generation unless the owner reviews first (the notification says
  exactly when). `--autopilot MANUAL` = wait for the owner forever; per-account window
  via Settings or `auto_approve_hours`. Owner rejections are never overridden.
- **Destinations:** WhatsApp (default), **phone-call ads** (`--wa-mode CALL` — customers
  tap and dial the owner), or Cloud API (AI closer). Call/own-number modes run the
  optimizer in blind mode (spend/frequency signals only).
- **Lead alerts:** new captured leads SMS the owner instantly via MSG91
  (`MSG91_LEAD_FLOW_ID`, DLT Flow template, capped `SMS_ALERT_DAILY_CAP`/day).
- **Pause = pause:** the owner/admin/trial pause stops the Meta campaign itself; resume
  restores the previous state and reactivates paused ad sets. Paying a lapsed trial
  auto-resumes ads.

## Go live
1. **Autonomous path (hands-off):** pass `--autopilot FULL`. The `progress_accounts` cron
   (every 10 min) drives the account **research → creative (image + video) → launch** with
   no clicks. Ads go live on the client's ad account; clicks open their WhatsApp. Under
   the default **ASSISTED** mode the same cron launches as soon as creatives are approved
   (in the app, or via the API) — approval is the only gate.
2. **Assisted path (you approve):** default. Saathi researches + writes creatives; you (or
   the owner) approve them in the app, then it launches. Trigger phases immediately instead
   of waiting for the cron:
   ```bash
   # inside a python shell / one-off task, per account_id:
   from leadpilot.saathi import pipeline
   from leadpilot.core.db import tenant_session
   with tenant_session(TENANT_ID) as s: pipeline.run_research(s, tenant_id=TENANT_ID, account_id=ACCT_ID)
   with tenant_session(TENANT_ID) as s: pipeline.run_creative(s, tenant_id=TENANT_ID, account_id=ACCT_ID)
   with tenant_session(TENANT_ID) as s: pipeline.launch_campaigns(s, tenant_id=TENANT_ID, account_id=ACCT_ID)
   ```

## When to add the automated AI qualifier (later, per client)
Only if a client wants Saathi to auto-reply on WhatsApp 24×7:
1. Onboard a WhatsApp Cloud API number (directly, or via a BSP that is already an approved
   Meta Tech Provider — you inherit their platform status).
2. Re-provision with `--wa-mode CLOUD_API --phone-number-id <PNID>` (registers the routing
   key), submit the seeded templates for approval, set `MOCK_WHATSAPP=false`.
Everything else stays the same.

## Your operator toolkit (no SMS, no seed data needed)
```bash
# Your own back-office login (fleet view, daily digest, anomaly queue, impersonation):
python -m leadpilot.scripts.create_admin --phone <your phone> --name "You"
# Log any phone in WITHOUT SMS (client at the shop, MSG91 down, whatever) — the client
# taps "I already have a code" on the login screen and types it:
python -m leadpilot.scripts.mint_login --phone +919812345678
```
Then open **/admin** after logging in:
- **Fleet view** — every client's phase, today's spend, leads today, and Meta token
  health in one screen (a dead token shows as `Meta ERROR`).
- **Daily digest** — per-client Hindi summary with a "Copy for WhatsApp" button; forward
  it to each client every evening (this replaces the automated report until clients have
  Cloud API numbers).
- **Open as client** — audited impersonation straight into their dashboard (approve
  creatives on their behalf, check their view).
- **Mark paid** — after collecting UPI/bank payment, mark the subscription ACTIVE so the
  trial sweep never pauses a paying client.

Provision with a hard ceiling per client: `--monthly-cap 15000` (rupees). Owners can also
set it later in Settings; launches are blocked once month-to-date spend crosses it.
Lead visibility on the own-number path: qualification chats happen in the client's
WhatsApp, so log enquiries with the **+ Add lead** button in the app (or POST
`/accounts/{id}/leads`) — that's what makes reports/CPQL real. Instant-Form campaigns are
pulled automatically every 10 minutes via your System User token (no webhook, no review).

## The line we don't cross
Agency operation, own-number CTWA, and client-owned ad accounts are legitimate ways to run
**without** those reviews. We do **not** fake verification status, misrepresent the app to
Meta, or spoof anything to *evade* a policy — that risks account bans and isn't supported.
```
