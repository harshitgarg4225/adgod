# Deploying Salmor on Railway

One repository, one Python image, **six services** + managed Postgres & Redis + an
external Cloudflare R2 bucket. Provision in this order.

## 0. Prerequisites
- Railway project (pick the region nearest India — e.g. Singapore; see the
  data-residency note in `docs/ARCHITECTURE.md`).
- Cloudflare R2 bucket + API token (for creative assets / invoice PDFs).
- API keys as you enable real integrations: Anthropic, Gemini, Meta app, WhatsApp Cloud,
  Razorpay, MSG91. **For the walking skeleton none are required** — keep the `MOCK_*`
  flags `true`.

## 1. Datastores
1. Add the **PostgreSQL** plugin. Then enable pgvector once:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
   (Migration `0001` also runs this, and creates the non-superuser `leadpilot_app` role +
   RLS policies. The connecting role must be able to `GRANT`/`SET ROLE` — the Railway
   superuser is fine.)
2. Add the **Redis** plugin.
3. (Recommended from day one) add a **PgBouncer** service in transaction-pool mode and
   point `DATABASE_URL_POOLED` at it.

## 2. Shared variables
Create a shared variable group (see `.env.example` for the full list). Minimum for a
mocked deploy:
```
ENVIRONMENT=production
DATABASE_URL=${{Postgres.DATABASE_URL}}      # use the +psycopg driver form
REDIS_URL=${{Redis.REDIS_URL}}
JWT_SECRET=<32+ random bytes>
TOKEN_ENCRYPTION_KEY=<32 bytes>
MOCK_META=true
MOCK_WHATSAPP=true
MOCK_RAZORPAY=true
MOCK_LLM=true
MOCK_OTP=true
```
> Ensure `DATABASE_URL` uses `postgresql+psycopg://…`. If Railway gives `postgresql://…`,
> add the `+psycopg` driver prefix.

## 3. Run migrations
Add `alembic upgrade head` as a **pre-deploy / release command** on `bff-api` (or run it
once via `railway run alembic upgrade head`). Optionally seed a demo account:
`railway run python -m leadpilot.scripts.seed_demo`.

## 4. Services (all deploy this repo with the shared Dockerfile)
Set each service's **Custom Start Command**:

| Service | Start command | Health |
|---|---|---|
| `bff-api` | `gunicorn leadpilot.bff.app:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT` | `/health` |
| `webhook-intake` | `gunicorn leadpilot.webhook.app:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT` | `/health` |
| `closer-worker` | `celery -A leadpilot.worker.celery_app worker -Q closer -c 4 -n closer@%h` | — |
| `agent-worker` | `celery -A leadpilot.worker.celery_app worker -Q agent,optimizer,launch -c 4 -n agent@%h` | — |
| `cron-dispatch` | `celery -A leadpilot.worker.celery_app beat` | — |

The web frontend is a **separate Node service** rooted at `web/`:
| `web-next` | `npm run start` (build: `npm ci && npm run build`) | set `NEXT_PUBLIC_API_BASE` to the public `bff-api` URL |

## 5. Webhooks (when going live, Phase 2+)
Point Meta WhatsApp + Lead Ads + Razorpay webhooks at the public `webhook-intake` URL:
- `POST https://<webhook-intake>/webhooks/whatsapp` (verify token = `WHATSAPP_WEBHOOK_VERIFY_TOKEN`)
- `POST https://<webhook-intake>/webhooks/meta/leadgen`
- `POST https://<webhook-intake>/webhooks/razorpay`
For each connected business number, insert a `wa_routes` row mapping its
`phone_number_id` → `(tenant_id, account_id)` so intake can resolve the tenant.

## 6. Going from mock → live
Flip the relevant `MOCK_*` flag to `false` and fill the matching credentials. No code
change — the adapter interface is identical. Recommended order: `MOCK_LLM` →
`MOCK_OTP` → `MOCK_WHATSAPP` → `MOCK_META` → `MOCK_RAZORPAY`.

## 7. Notes
- `railway.toml` documents the canonical start commands.
- `docker/python.Dockerfile` is the shared image for all Python services.
- Scale `closer-worker` replicas independently to protect the inbound p95.
