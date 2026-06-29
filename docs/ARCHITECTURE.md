# LeadPilot — Architecture & Build Plan (Railway)

This is the implementation architecture for `LeadPilot_PRD_v1`, adapted to run on
**Railway**. It records the decisions, the service topology, the agent design, the
data model, and the phased build plan. The PRD is the product spec; this is how we
build it.

---

## 1. Thesis

`saathi_core` is **one importable Python library** — a deterministic Orchestrator
that dispatches six scoped sub-agents (Scout, Maker, Buyer, Optimizer, Closer,
Reporter) through a **synchronous Guardrail Engine**. Sub-agents never free-form into
side effects; they return JSON validated against Pydantic contracts (`saathi/contracts.py`).
The same Orchestrator runs identically whether triggered by a **webhook**, a **cron**,
or an **owner action** — only the trigger source differs.

Everything heavy in the PRD (Kubernetes, Temporal, n8n, ClickHouse, native S3, an
Expo mobile app) is mapped to a Railway-native reality, each behind a **stable
interface** so adopting the heavy version later is a migration, not a rewrite.

---

## 2. Stack decisions (PRD → Railway)

| Area | PRD | Decision | Why |
|---|---|---|---|
| Orchestration | K8s/ECS | Railway services from one repo/image, different start commands | Per-service deploys, private networking, zero-config TLS without K8s ops |
| Durable workflows | Temporal | **Postgres transactional outbox + idempotency keys + read-modify-write reconciliation** + Celery + cron reaper | "No double-spend" via *exactly-once effect*, no Temporal cluster to run. Temporal stays a drop-in behind `WorkflowRunner`. |
| Connectors/cron | n8n | Typed Python adapters + Railway cron + webhook-intake | Reasoning/guardrails/idempotency belong in versioned, tested code |
| Analytics | ClickHouse | Partitioned Postgres rollups | Fine at v1 volume; behind a reporting interface |
| Object storage | S3 | **Cloudflare R2** (S3 API) via an `AssetStore` abstraction | Railway has no blob store; R2 is zero-egress and jurisdiction-configurable |
| Data residency (DPDP) | India region | **Founder/legal sign-off gate.** v1 in Railway's nearest region + PII redaction + encrypted tokens + a portable data layer | Railway can't guarantee an India region — owned as a product decision, not silently deferred |
| Mobile | Expo (primary) | **Web-first** (Next.js PWA); BFF built mobile-ready | Railway hosts web, not app binaries; Expo bolts on later via EAS with no backend change |
| LLM | Claude + Gemini | `LLMProvider` router: Claude reasoning (Optimizer/Scout), Gemini creative + Closer; per-account cost cap | Centralizes routing/caps/cost-logging; model swap is config |

---

## 3. Railway topology (v1)

```
                 Internet
                    │
        ┌───────────┼───────────────┐
        ▼           ▼               ▼
   ┌─────────┐ ┌──────────────┐ ┌──────────┐
   │ web-next│ │   bff-api    │ │ webhook- │  (web services)
   │ (Next)  │→│  (FastAPI)   │ │ intake   │
   └─────────┘ └──────┬───────┘ └────┬─────┘
                      │   enqueue     │ verify+persist+enqueue
                      ▼               ▼
                 ┌──────────────── Redis ────────────────┐
                 │  queues: closer / agent / optimizer …  │
                 └───────┬───────────────────┬────────────┘
                         ▼                   ▼
                 ┌──────────────┐    ┌──────────────────┐
                 │ closer-worker│    │   agent-worker   │  (workers)
                 │  (Q=closer)  │    │ Q=agent,optimizer│
                 └──────┬───────┘    └────────┬─────────┘
                        └─────────┬───────────┘
                                  ▼
                       ┌──────────────────────┐    ┌──────────┐
                       │  Postgres 16 + pgvec  │    │   R2     │
                       │  (+ PgBouncer)        │    │ (assets) │
                       └──────────────────────┘    └──────────┘
        cron-dispatch (beat): optimizer hourly · reporter daily · reaper
```

| Service | Kind | Start command |
|---|---|---|
| `bff-api` | web | `gunicorn leadpilot.bff.app:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT` |
| `webhook-intake` | web | `gunicorn leadpilot.webhook.app:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT` |
| `web-next` | web (Node) | `npm run start` (root `web/`) |
| `closer-worker` | worker | `celery -A leadpilot.worker.celery_app worker -Q closer -c 4` |
| `agent-worker` | worker | `celery -A leadpilot.worker.celery_app worker -Q agent,optimizer,launch,fatigue -c 4` |
| `cron-dispatch` | cron | `celery -A leadpilot.worker.celery_app beat` |
| Postgres 16 + pgvector | plugin | managed |
| Redis | plugin | managed |

`closer-worker` is isolated on its own queue with warm replicas so Optimizer load can
never breach the inbound Closer **p95 < 5s** SLO.

---

## 4. Agent design

- **Orchestrator** (`saathi/orchestrator.py`) — plain deterministic code: load account
  state → determine phase → route trigger → sub-agent → **Guardrail gate** → persist +
  audit → notify. v1 implements the **CLOSER** (inbound WhatsApp) path end to end.
- **Sub-agents** (`saathi/agents/`) — each a class with a fixed system prompt, a
  tenant-scoped tool subset, and a Pydantic output contract. Invalid JSON ⇒ run marked
  FAILED (no free-form side effects). Every run is recorded to `agent_runs`
  (model/tokens/latency/cost).
- **Guardrail Engine** (`saathi/guardrails/`) — synchronous gate. The **scope guard**
  (the v1-critical, Meta-compliance gate) blocks any Closer reply that escapes
  qualification; **spend** clamps budget edits to ≤ daily budget and ≤ +20%/day;
  **compliance** pre-screens creative copy. Blocks are persisted to `guardrail_events`.
- **Durability** (`saathi/workflow/` + `core/outbox.py`) — every external effect
  (WhatsApp send; later Meta/Razorpay writes) is an outbox row committed in the same
  transaction as state, keyed by `(account_id, step_id)`. The `WorkflowRunner` drains
  it; handlers are idempotent (read-modify-write) so a redelivery is a no-op. A cron
  reaper re-queues orphans; exhaustion → `dlq`.
- **Providers** (`saathi/providers/`) — `LLMProvider` router (mock + Claude/Gemini),
  `AssetStore` (R2 + local), all mockable via `MOCK_*` flags.

### Trigger model on Railway
1. **EVENT (hot path):** `webhook-intake` verifies `X-Hub-Signature-256` → idempotent
   `inbound_events` (on `wa_message_id`) → enqueue `closer` queue → `closer-worker` runs
   the CLOSER flow → guarded reply → outbox send → persist lead/transcript → hot-lead notify.
2. **CRON:** `cron-dispatch` enqueues idempotent per-account jobs (sharded by
   `account_id % OPTIMIZER_SHARD_COUNT`). Cron does zero reasoning.
3. **USER/CHAIN:** `bff-api` enqueues owner-initiated jobs; sub-agents enqueue follow-ons.

---

## 5. Data design

Single Railway Postgres 16 + pgvector as system-of-record **and** Saathi memory.

- **Migrations:** Alembic; run as a Railway pre-deploy step (`alembic upgrade head`).
- **Multi-tenancy:** every private table has **RLS FORCED** with
  `USING (tenant_id = current_setting('app.tenant_id', true)::uuid)`. `tenant_session()`
  switches to the non-superuser app role (`SET LOCAL ROLE`) and sets the GUC, so a
  forgotten `WHERE` cannot leak across tenants — and RLS applies even when the base
  connection is a superuser. Routing/infra tables (`wa_routes`, `inbound_events`,
  `outbox`, `jobs`, `dlq`, `users`) are intentionally non-RLS (pre-tenant lookups / no
  lead PII).
- **Money:** integer **paise** everywhere (`core/money.py`); no float ever touches money.
- **Memory:** structured (relational ledgers + `creatives.perf`) and semantic
  (`creatives.embedding vector(1536)`, PII-redacted) — retrieved scoped by `tenant_id`
  or k-anon (k ≥ 20) vertical+city priors (Phase 4).
- **PII (DPDP):** redacted in logs and in `messages.redacted_body` before anything enters
  memory; Meta tokens encrypted at rest.

---

## 6. Build plan

| Phase | Goal | Status |
|---|---|---|
| **0 — Skeleton + contracts** | Topology deploys; agent-core seams frozen | ✅ done |
| **1 — Walking skeleton (v1 slice)** | inbound → Closer qualifies → owner sees HOT lead, mocked Meta/WhatsApp, real interfaces | ✅ done |
| **2 — Self-serve onboarding + ad launch** | OTP, 5-q wizard, Meta Embedded Signup, Scout/Maker/Buyer launch CTWA, Razorpay, daily Reporter | ⏳ next |
| **3 — Autonomy + durability at scale** | Optimizer CPL→CPQL hourly, fatigue refresh, full guardrails, load-tested outbox, Cloud-API Closer | planned |
| **4 — Scale, memory, distribution** | k-anon priors, wallet, partner/admin consoles, video, Expo, **execute India-residency decision**, multi-language | planned |

### What v1 ships (this repo)
The core loop end to end with the least external-dependency friction:
seeded coaching-center account → simulated inbound CTWA WhatsApp → `webhook-intake`
(signature + idempotent persist) → `closer-worker` → Closer qualifies in Hindi
(GREET→…→SCORE) through the scope guard → `lead_qualifications` (HOT) + `lead.status`
under RLS → outbox WhatsApp send (exactly-once) → hot-lead notification → owner opens
the Next.js inbox, sees the HOT lead, reads the transcript, taps WhatsApp/Call/Won-Lost.
`MOCK_META`/`MOCK_WHATSAPP` keep transport fake while interfaces stay real.

### v1 acceptance (all covered by tests)
`tests/` proves: idempotent + signature-verified webhook intake; RLS isolation
(non-superuser role); exactly-once outbox effect + DLQ; full Hindi qualification → HOT;
scope-guard block (recorded, not sent); paise integer money; owner HTTP surface
(login → see HOT lead → transcript → mark Won); inbound p95 < 5s over 50 messages.

---

## 7. Open product decisions (PRD §19.4)

1. **India data residency** — accept Singapore-now + portable data layer until legal
   sign-off, or treat an India-region data tier as a hard blocker now. *(The one item no
   Railway architecture fully solves.)*
2. **Real vs mock Meta/WhatsApp** for Phase 2 — when a real seeded Meta ad account +
   WhatsApp number become available (Embedded Signup/WABA onboarding takes weeks).
3. **Beachhead** — default: coaching centers, Indore, Hindi.
4. **LLM mix / cost ceiling** — default: Claude reasoning + Gemini creative/Closer.
5. **Pricing tiers + trial** — needed before Phase 2 billing.
