# LeadPilot — "Saathi"

Autonomous AI ad-running & lead-generation agent for Indian Tier-2 SMBs.
Give it ₹500/day and a 10-minute setup; it researches the business, writes
vernacular ads, launches & optimizes Click-to-WhatsApp (CTWA) campaigns on Meta,
and runs a 24/7 WhatsApp qualifier bot that turns clicks into **qualified** leads.

> This repository is the implementation of `LeadPilot_PRD_v1`. It is built to be
> hosted on **Railway**. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the
> full architecture and the phased build plan.

## What's built (Phase 0 + 1 + the autonomous ad pipeline)

All with **mocked Meta/WhatsApp/Razorpay transport behind real interfaces** — flip a
`MOCK_*` env flag to go live with no code change.

**Lead loop (Closer):**
```
inbound WhatsApp (CTWA) → /webhooks/whatsapp (verify + idempotent persist + enqueue)
  → closer-worker → Saathi Orchestrator (CLOSER trigger)
  → Closer sub-agent qualifies (GREET→…→SCORE) through the Guardrail scope gate
  → persist lead + transcript + qualification (HOT/WARM/COLD) under RLS
  → enqueue owner notification → owner sees the HOT lead in the Next.js inbox
```

**Autonomous ad pipeline** (what the competitors don't have — see `docs/COMPETITIVE.md`):
```
onboard → Scout (research → brief + ≥8 angles) → Maker (vernacular copy + image,
compliance-screened) → Buyer (CTWA campaign: 70/20/10 ad sets) → Optimizer (CPL→CPQL,
pause/scale/fatigue within hard bounds) → Reporter (daily vernacular summary)
```
Drives an account `ONBOARDING → RESEARCHED → CREATIVE_GENERATED → LIVE → OPTIMIZING`,
with Razorpay UPI-Autopay subscriptions (+18% GST). All exercised by `tests/`.

Every external effect (WhatsApp send, future Meta edit) flows through a Postgres
**transactional outbox + idempotency keys** → exactly-once *effect*, no double-spend,
without Temporal.

## Architecture at a glance

`saathi_core` is **one importable Python library** — a deterministic Orchestrator
dispatching six Pydantic-contracted sub-agents (Scout/Maker/Buyer/Optimizer/Closer/
Reporter) through a synchronous Guardrail Engine. The same agent code runs identically
whether triggered by a webhook, a cron, or an owner action.

### Railway services (one repo, one image, different start commands)

| Service | Kind | Start command |
|---|---|---|
| `bff-api` | web | `gunicorn leadpilot.bff.app:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT` |
| `webhook-intake` | web | `gunicorn leadpilot.webhook.app:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT` |
| `closer-worker` | worker | `celery -A leadpilot.worker.celery_app worker -Q closer -c 4` |
| `agent-worker` | worker | `celery -A leadpilot.worker.celery_app worker -Q agent,optimizer,launch,fatigue -c 4` |
| `cron-dispatch` | cron | `celery -A leadpilot.worker.celery_app beat` |
| `web-next` | web | `npm run start` (root `web/`, Node service) |
| Postgres 16 + pgvector, Redis, PgBouncer, Cloudflare R2 | data | managed |

## Local development

```bash
# 1. Python deps
python -m venv .venv && source .venv/bin/activate
pip install -e ".[llm,storage,dev]"

# 2. Postgres + Redis (docker compose for local convenience)
docker compose -f docker-compose.dev.yml up -d

# 3. Migrate
cp .env.example .env
alembic upgrade head
python -m leadpilot.scripts.seed_demo     # seeds a demo coaching-center account

# 4. Run services (separate terminals)
uvicorn leadpilot.bff.app:app --reload --port 8000
uvicorn leadpilot.webhook.app:app --reload --port 8001
celery -A leadpilot.worker.celery_app worker -Q closer,agent,optimizer,launch,fatigue -c 2

# 5. Web
cd web && npm install && npm run dev      # http://localhost:3000

# 6. Simulate an inbound CTWA lead end-to-end
python -m leadpilot.scripts.simulate_inbound --text "kya aap NEET ki coaching karate ho?"
```

## Tests

```bash
pytest          # webhook idempotency, RLS isolation, outbox exactly-once, Closer state machine, paise
```

## Pinned external API versions

| API | Version | Notes |
|---|---|---|
| Meta Graph / Marketing | `v21.0` | pin at build start; Meta deprecates ~quarterly |
| WhatsApp Cloud API | Graph `v21.0` | 24h/72h window rules enforced |
| Razorpay | current | Subscriptions + UPI Autopay + GST |

## License

Proprietary. © LeadPilot.
