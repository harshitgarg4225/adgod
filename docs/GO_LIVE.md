# LeadPilot — Go-Live Runbook

Everything in the codebase is built and tested in **mock mode** (real interfaces behind
`MOCK_*`). This runbook takes it from "runs locally" to "serving a real paying pilot."
It separates **what's a config flip** (minutes) from **what's an external approval**
(days–weeks, owned by you, not code).

> Recommended beachhead: coaching centers in **one** city (Indore/Jaipur), Hindi-first.

## Stage 0 — Deploy the mock build (today, no external accounts)
1. Provision on Railway per `infra/railway/README.md`: Postgres (+pgvector), Redis,
   PgBouncer, and the services (`bff-api`, `webhook-intake`, `web-next`,
   `closer-worker`, `agent-worker`, `cron-dispatch`).
2. Shared variables: copy `.env.production.example`, keep **all `MOCK_*=true`** for now.
3. Release command on `bff-api`: `alembic upgrade head`. Optionally
   `python -m leadpilot.scripts.seed_demo`.
4. Set the web service to build `web/Dockerfile` with build var
   `NEXT_PUBLIC_API_BASE=https://<bff-api>/api/v1`.
5. ✅ You can now click the whole product live (mock data): onboarding → research →
   creatives → launch → optimize → reports → billing, plus partner/admin consoles.

## Stage 1 — Turn on the AI (config flip, ~minutes)
- Fill `ANTHROPIC_API_KEY` + `GEMINI_API_KEY`, set `MOCK_LLM=false`.
- Now Scout/Maker/Closer/Reporter use real models; image-gen uses Gemini Imagen.
- Watch `LLM_DAILY_BUDGET_PER_ACCOUNT_PAISE` (per-account cost cap is enforced in the router).

## Stage 2 — Turn on OTP + billing (config flip once accounts exist)
- **MSG91**: add `MSG91_API_KEY`, set `MOCK_OTP=false`. (Wire real send + `auth_otps` —
  the interface is ready; current mock accepts dev code `000000`.)
- **Razorpay**: activate account + UPI Autopay + GST; create per-tier Plans; add
  `RAZORPAY_KEY_ID/SECRET/WEBHOOK_SECRET`, map plan ids, set `MOCK_RAZORPAY=false`.
  Point the Razorpay webhook at `https://<webhook-intake>/webhooks/razorpay`.

## Stage 3 — Meta + WhatsApp (the long poles — start these FIRST, in parallel)
These gate real ads/leads and take **days–weeks**; they are approvals, not code.
1. **Meta**: Business verification; create/verify the App; request Marketing API + ads
   permissions (App Review); connect an aged ad account + Page. Fill `META_APP_ID/SECRET`,
   `META_WEBHOOK_VERIFY_TOKEN`; set `MOCK_META=false`. Subscribe the leadgen webhook to
   `https://<webhook-intake>/webhooks/meta/leadgen`.
2. **WhatsApp Cloud API**: WABA onboarding (~5–15 days), phone number, **template
   approval** (~20–30% first-time rejection — pre-validate), green-tick (GST + ~4–8 wks).
   Fill `WHATSAPP_*`; set `MOCK_WHATSAPP=false`. Configure the webhook + verify token at
   `https://<webhook-intake>/webhooks/whatsapp`. For each business number, insert a
   `wa_routes` row (`phone_number_id → tenant_id, account_id`).
   - **v1 shortcut (PRD §6.1.3):** the CTWA-to-app path needs *no* WABA — ads send leads to
     the owner's existing WhatsApp app number. Use this to launch while the bot tier's
     WABA approval is pending.

## Stage 4 — Data residency (DPDP) — founder/legal sign-off
Railway has no guaranteed India region. Decide:
- (a) Run compute in Singapore with PII redaction + encrypted tokens + an R2 bucket in a
  chosen jurisdiction, and migrate the data tier to an India-region managed Postgres
  (Neon/RDS `ap-south-1`) when ratified — the data layer is `DATABASE_URL`-portable; **or**
- (b) Stand up the India-region Postgres first and point `DATABASE_URL` at it now.
Do not onboard real-PII accounts until this is signed off.

## Stage 5 — Production hardening (recommended before scale)
- Set `Sentry`/OTel DSNs; enable PgBouncer; raise `closer-worker` warm replicas.
- Replace the in-request pipeline triggers in `bff/routers/agents.py` with enqueue
  (worker tasks already exist) for owner-initiated research/creative/launch at scale.
- Wire MSG91 real OTP + `auth_otps`; add Razorpay invoice PDF generation; CSV export +
  wallet (Pro). These are marked in code as Phase-2/3 follow-ups.

## Definition of "ready for first paying pilot"
Stages 0–2 done + Stage 3 via the **CTWA-to-app shortcut** (no WABA needed) + Stage 4
sign-off. Full bot tier (Cloud API Closer) follows once WABA + templates clear.
