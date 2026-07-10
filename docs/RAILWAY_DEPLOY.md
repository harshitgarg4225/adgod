# Deploy Salmor to Railway — the fast path (a live URL you can click)

Goal: a **public URL** running the full product in **mock mode** — no AI/Meta/SMS keys, no
per-lead cost, just Railway's small infra. You click through onboarding → ad creation →
dashboard → reports exactly like a real client would. ~30–40 min, mostly waiting on builds.

The repo is pre-configured so each service **self-configures** — you mostly paste, not think.

For the fast path you deploy **2 services + 2 databases** (not the full 6). The three
background workers are only needed once you want the *autonomous* optimise/lead loop; the
demo runs the pipeline inline inside the API. Add workers later (Appendix B).

---

## 0. Prerequisite (only thing that's truly yours)
A **Railway account** (railway.app) with a trial/payment method. That's the irreducible
part — it's your infrastructure and your billing.

## 1. Databases
1. New Project → **Add PostgreSQL**. Open its **Data** tab → run once:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
2. **Add Redis**.

## 2. `bff-api` (the backend) — self-configuring
1. **New Service → GitHub Repo → `harshitgarg4225/adgod`.** Railway reads `railway.toml`
   at the repo root and configures itself: builds the Python image, runs
   `alembic upgrade head` before each deploy (this creates the `leadpilot_app` /
   `leadpilot_platform` DB roles automatically), starts the API, health-checks `/health`.
2. **Settings → Networking → Generate Domain.** Note it, e.g. `https://bff-api-xxxx.up.railway.app`.
3. Don't deploy yet — set the env in step 4 first.

## 3. `web-next` (the app UI) — separate Node service
1. **New Service → same GitHub Repo.** Settings → **Root Directory = `web`**,
   **Builder = Dockerfile** (it reads `web/railway.toml`).
2. **Generate Domain** → note it, e.g. `https://web-next-xxxx.up.railway.app`.
3. Add a **build** variable (Variables → New Variable):
   `NEXT_PUBLIC_API_BASE = https://bff-api-xxxx.up.railway.app/api/v1`
   (the bff-api domain from step 2 + `/api/v1`). This is baked in at build time.

## 4. Shared variables on `bff-api`
Paste this block into `bff-api` → Variables (Raw Editor). Fill the two domains from
steps 2–3 and your two generated secrets (commands below).

```
ENVIRONMENT=production
PIPELINE_INLINE=true
TRUST_PROXY=true

DATABASE_URL=${{Postgres.DATABASE_URL}}
DATABASE_URL_POOLED=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
APP_TENANT_DB_ROLE=leadpilot_app
APP_PLATFORM_DB_ROLE=leadpilot_platform
DB_POOL_SIZE=3
DB_MAX_OVERFLOW=7

JWT_SECRET=<paste generated secret #1>
TOKEN_ENCRYPTION_KEY=<paste generated secret #2>

APP_BASE_URL=https://bff-api-xxxx.up.railway.app
WEB_BASE_URL=https://web-next-xxxx.up.railway.app
CORS_ALLOWED_ORIGINS=https://web-next-xxxx.up.railway.app

MOCK_LLM=true
MOCK_META=true
MOCK_WHATSAPP=true
MOCK_RAZORPAY=true
MOCK_OTP=true
```

> `PIPELINE_INLINE=true` is what lets the demo work with **no workers** — the API runs
> research/creative/launch inline. Railway will log one harmless "PIPELINE_INLINE=true in
> production" warning; ignore it for the demo. `CORS_ALLOWED_ORIGINS` **must** be the
> `web-next` domain or the browser can't call the API.

Generate the two secrets (run anywhere with Python):
```
python -c "import secrets; print(secrets.token_urlsafe(48))"   # JWT_SECRET
python -c "import secrets; print(secrets.token_urlsafe(48))"   # TOKEN_ENCRYPTION_KEY
```

## 5. Deploy + see it
1. Deploy `bff-api`, then `web-next` (Railway auto-deploys on save; redeploy if needed).
2. Optional demo data: `bff-api` → open a shell (or Railway CLI) →
   `python -m leadpilot.scripts.seed_demo`.
3. Open the **`web-next` URL**. Log in — in mock mode the OTP appears on screen (or use the
   demo owner `+91 98765 00000`, code `000000` if you seeded).
4. Walk onboarding → ad-style picker → dashboard → reports. All in English/Hindi/Punjabi.

That's the live product. Nothing here spends ad money — everything external is mocked.

---

## Appendix A — order matters (avoids a rebuild dance)
Generate **both** domains (steps 2.2 and 3.2) **before** setting `NEXT_PUBLIC_API_BASE`
(step 3.3) and `CORS_ALLOWED_ORIGINS` (step 4), so each cross-reference is right on the
first build and you don't have to rebuild.

## Appendix B — from demo → live (later)
1. **Turn on AI:** add `ANTHROPIC_API_KEY` (+ `GEMINI_API_KEY` for images, `FAL_API_KEY`
   for video) and `R2_*` (creative hosting), set `MOCK_LLM=false`.
2. **Turn on real ads:** add `META_SYSTEM_USER_TOKEN` + `META_APP_ID/SECRET`, set
   `MOCK_META=false`, and share each client's ad account + Page under your Business Manager.
3. **Add the 3 workers** (so the autonomous loop runs) — new services on the same repo, and
   flip `PIPELINE_INLINE=false`:
   - `agent-worker` → `celery -A leadpilot.worker.celery_app worker -Q agent,optimizer,launch -c 4 -n agent@%h`
   - `closer-worker` → `celery -A leadpilot.worker.celery_app worker -Q closer -c 4 -n closer@%h`
   - `cron-dispatch` → `celery -A leadpilot.worker.celery_app beat`
4. **Billing:** add `RAZORPAY_*`, set `MOCK_RAZORPAY=false` (until then: manual UPI +
   admin "Mark paid").

Full stage-by-stage detail: `docs/GO_LIVE.md` and `infra/railway/README.md`.
