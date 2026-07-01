# Salmor — Go-Live Runbook

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
2. **WhatsApp** — go live in **days, not weeks** (see `docs/WHATSAPP_PROVIDERS.md`):
   - **Fastest:** use a **BSP middleware** (`WHATSAPP_PROVIDER=bsp`). The BSP is the Meta
     Tech Provider, so their Embedded Signup provisions the number in hours/days — no app
     review on our side. **Green-tick is NOT required** to start (unverified WABA sends
     immediately; Meta *Business* verification — fast — lifts limits). Set `BSP_*`,
     `MOCK_WHATSAPP=false`; point the provider webhook at
     `https://<webhook-intake>/webhooks/whatsapp`; add a `wa_routes` row per number.
   - **Cheapest at scale:** migrate to `WHATSAPP_PROVIDER=cloud` (Cloud API direct, no BSP
     markup) once you hold Tech Provider access — same adapter interface.
   - **CTWA 72h free window** means the Closer qualification costs ≈ ₹0 variable.
   - **Even faster, no WABA (PRD §6.1.3):** CTWA-to-app sends leads to the owner's existing
     WhatsApp app number — use it to prove ad economics while the BSP number provisions
     (the AI Closer can't run on this path, since messages don't reach our API).

## Stage 4 — Data residency (DPDP) — founder/legal sign-off
Railway has no guaranteed India region. Decide:
- (a) Run compute in Singapore with PII redaction + encrypted tokens + an R2 bucket in a
  chosen jurisdiction, and migrate the data tier to an India-region managed Postgres
  (Neon/RDS `ap-south-1`) when ratified — the data layer is `DATABASE_URL`-portable; **or**
- (b) Stand up the India-region Postgres first and point `DATABASE_URL` at it now.
Do not onboard real-PII accounts until this is signed off.

## Stage 5 — Production hardening (recommended before scale)
Built and tested (just supply the secret / flip the flag):
- **Real OTP** (MSG91) + `auth_otps` — set `MSG91_API_KEY`, `MOCK_OTP=false`.
- **Razorpay webhook** → subscription ACTIVE + GST invoice on charge, PAST_DUE on failure
  (`/webhooks/razorpay`, signature-verified).
- **Meta lead-form webhook** → Instant-Form leads flow into the inbox (`/webhooks/meta/leadgen`).
- **Token encryption at rest** (Meta system-user tokens, Fernet).
- **Health/readiness** (`/health`, `/ready` check DB+Redis) for Railway probes.
- **Sentry** — set `SENTRY_DSN` and `pip install sentry-sdk` (optional, auto-detected).
- **Deploy hardening (built):** bare `postgresql://` auto-uses the psycopg driver;
  `tenant_session` fails closed in prod without `APP_TENANT_DB_ROLE` (RLS never silently
  off); Celery runs the same secret guard at boot and resets its DB pool per prefork child;
  behind a proxy set `TRUST_PROXY=true` so per-IP rate limits/audit see real client IPs;
  size the pool via `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` and front Postgres with PgBouncer
  (`DATABASE_URL_POOLED`) so replicas don't exhaust `max_connections`.

Still recommended follow-ups: enable PgBouncer; raise `closer-worker` warm replicas;
move owner-initiated pipeline triggers in `bff/routers/agents.py` to enqueue at scale;
Razorpay invoice-PDF generation; CSV export + wallet (Pro); Meta Embedded-Signup OAuth
callback (replaces manual token entry on `/onboarding/meta/connect`).

## Definition of "ready for first paying pilot"
Stages 0–2 done + Stage 3 via the **CTWA-to-app shortcut** (no WABA needed) + Stage 4
sign-off. Full bot tier (Cloud API Closer) follows once WABA + templates clear.
