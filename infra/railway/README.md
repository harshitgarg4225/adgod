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
Create a shared variable group (see `.env.production.example` for the full list). Minimum
for a mocked deploy:
```
ENVIRONMENT=production
DATABASE_URL=${{Postgres.DATABASE_URL}}      # bare postgresql:// is auto-normalised to +psycopg
DATABASE_URL_POOLED=${{PgBouncer.DATABASE_URL}}   # transaction-pool URL (recommended from day 1)
APP_TENANT_DB_ROLE=leadpilot_app             # RLS-bound role the app runs as
APP_PLATFORM_DB_ROLE=leadpilot_platform      # BYPASSRLS role for webhooks/admin/cron (migration 0005)
DB_POOL_SIZE=3
DB_MAX_OVERFLOW=7
TRUST_PROXY=true                             # Railway terminates TLS at a proxy → read X-Forwarded-For
REDIS_URL=${{Redis.REDIS_URL}}
JWT_SECRET=<32+ random bytes>                # app REFUSES to boot on the dev default in production
TOKEN_ENCRYPTION_KEY=<32 bytes>
MOCK_META=true
MOCK_WHATSAPP=true
MOCK_RAZORPAY=true
MOCK_LLM=true
MOCK_OTP=true
```
> **DB driver:** the app forces the psycopg (v3) driver, so a bare
> `postgresql://…`/`postgres://…` from `${{Postgres.DATABASE_URL}}` works as-is — no need
> to hand-edit the prefix.
> **Connection budget:** each replica opens up to `DB_POOL_SIZE + DB_MAX_OVERFLOW` server
> connections. With PgBouncer (transaction mode) in front, hundreds of workers share a small
> Postgres `max_connections`. Point `DATABASE_URL_POOLED` at PgBouncer and keep
> `DATABASE_MIGRATION_URL`/`DATABASE_URL` on the **direct** Postgres (migrations need a
> session, not a transaction pool).
> **`APP_PLATFORM_DB_ROLE`:** must be a real BYPASSRLS role. Migration `0005` creates
> `leadpilot_platform` when the migration role is a superuser (Railway's is). Leave it empty
> only if you provisioned that role out of band; in production the app fails closed without
> `APP_TENANT_DB_ROLE`, so RLS can never silently be skipped.

## 3. Run migrations
Add `alembic upgrade head` as a **pre-deploy / release command** on `bff-api` (or run it
once via `railway run alembic upgrade head`). Optionally seed a demo account:
`railway run python -m leadpilot.scripts.seed_demo`.

## 4. Services (all deploy this repo with the shared Dockerfile)
Every service is **config-as-code** — create the service from the repo, then point it at
its config file (Settings → Config-as-code → path). No hand-typed start commands:

| Service | Config file | Health |
|---|---|---|
| `bff-api` | `railway.toml` (repo root — the default) | `/health` |
| `webhook-intake` | `infra/railway/webhook-intake.toml` | `/health` |
| `closer-worker` | `infra/railway/closer-worker.toml` | — |
| `agent-worker` | `infra/railway/agent-worker.toml` | — |
| `cron-dispatch` | `infra/railway/cron-dispatch.toml` (**exactly 1 replica** — it's the scheduler) | — |

The web frontend is a **separate Node service** rooted at `web/` — it ships its own
`web/railway.toml` pinning the Dockerfile builder (Next.js `standalone` → `node server.js`):
| `web-next` | `node server.js` (root dir `web/`, builder = Dockerfile) | `NEXT_PUBLIC_API_BASE` as a **build** variable |

> `NEXT_PUBLIC_API_BASE` is inlined into the client bundle at **build** time — set it as a
> *build* variable, not a runtime one, pointing at the public `bff-api` URL
> (`https://<bff-api>/api/v1`). Give `bff-api` a stable custom domain first so the URL is
> known at web build time.

## 5. Webhooks (when going live, Phase 2+)
Point Meta WhatsApp + Lead Ads + Razorpay webhooks at the public `webhook-intake` URL.
Both Meta callbacks answer the **GET verification handshake** with their verify token, so
you can "Verify and Save" in the Meta dashboard:
- `GET/POST https://<webhook-intake>/webhooks/whatsapp` (verify token = `WHATSAPP_WEBHOOK_VERIFY_TOKEN`)
- `GET/POST https://<webhook-intake>/webhooks/meta/leadgen` (verify token = `META_WEBHOOK_VERIFY_TOKEN`, falls back to the WhatsApp one)
- `POST https://<webhook-intake>/webhooks/razorpay` (HMAC-signed, `RAZORPAY_WEBHOOK_SECRET`)

For each connected business number, insert a `wa_routes` row mapping its
`phone_number_id` → `(tenant_id, account_id)` so intake can resolve the tenant. In
own-number (`APP_DESTINATION`) mode there is no inbound WhatsApp webhook — leads arrive via
CTWA into the client's own app, so only the Meta ads/leadgen side applies.

## 6. Going from mock → live
Flip the relevant `MOCK_*` flag to `false` and fill the matching credentials. No code
change — the adapter interface is identical. Recommended order: `MOCK_LLM` →
`MOCK_OTP` → `MOCK_WHATSAPP` → `MOCK_META` → `MOCK_RAZORPAY`.

## 7. Notes
- `railway.toml` (root) + `infra/railway/*.toml` are the canonical per-service configs.
- `docker/python.Dockerfile` is the shared image for all Python services.
- Scale `closer-worker` replicas independently to protect the inbound p95.
