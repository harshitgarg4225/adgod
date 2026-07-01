# How Salmor beats the field

The competitors in the PRD (§2.3) and the OSS references (§17.6) are **messaging tools**
or **disconnected scripts**. Salmor is the only one that closes the full loop —
*generate the lead, qualify it, optimize the spend* — as one autonomous agent. This doc
maps each rival's gap to a capability that is **already implemented and tested** in this
repo (mock transport, real interfaces) or scheduled in the build plan.

## 1. vs WhatsApp BSPs — AiSensy, WATI, Interakt, Gupshup

They are broadcast/CRM platforms: you bring the leads, they help you message. None *run
ads* or *optimize spend*. WhatsApp is their product; for us it's the capture layer.

| Capability | AiSensy / WATI / Interakt / Gupshup | Salmor | Status in repo |
|---|---|---|---|
| **Generates leads** (runs CTWA ads) | ❌ you bring leads | ✅ Buyer launches CTWA campaigns on Meta | `saathi/pipeline.py::launch_campaigns` + `integrations/meta` |
| **Autonomous optimization** toward cost/qualified-lead | ❌ | ✅ Optimizer CPL→CPQL, pause/scale/fatigue within hard bounds | `pipeline.py::run_optimization`, `guardrails/spend.py` |
| **AI qualification** in the owner's language | ⚠️ generic bot builders | ✅ scoped Closer state machine, Meta-compliant, p95<5s | `saathi/agents/closer.py`, `guardrails/scope.py` |
| **Vernacular creative generation** | ❌ | ✅ Maker writes Hindi copy + images, compliance-screened | `pipeline.py::run_creative`, `guardrails/compliance.py` |
| **Zero-dashboard owner UX** | ❌ Ads-Manager-style complexity | ✅ status-over-detail; "Active / In review / Paused" only | `bff/routers/agents.py` (owner-simple), `web/` |
| **CPQL as the optimization target** | ❌ (CPL at best) | ✅ qualified-lead signal from Closer feeds the Optimizer | `ad_insights.cpql_paise`, joined from the lead stream |
| **₹500/day, UPI auto-debit** | ⚠️ seat/message pricing | ✅ flat tiers + Razorpay UPI Autopay + GST | `integrations/razorpay`, `bff/routers/billing.py` |

**One-line moat:** they make you *operate* marketing; Saathi *is* the marketer. The
account-memory + cross-account k-anon priors (Phase 4) compound per vertical+city and are
not transferable to a BSP whose data is just chat logs.

## 2. vs Western ad-automation — Smartly, Revealbot, "Crush"-style tools

ROAS dashboards for skilled media buyers on desktop, English-first, e-commerce-shaped.

- **We need no operator.** Their value is faster knobs for an expert; ours is *no expert
  required*. The Orchestrator drives the loop; the owner answers 5 questions.
- **CTWA-native, not pixel/catalog-native.** Our optimization target is qualified WhatsApp
  enquiries (CPQL), not website ROAS — the right metric for Tier-2 services.
- **Vernacular + mobile-first + ₹-in/₹-out transparency** vs English ROAS charts.

## 3. vs local agencies / "the digital guy"

10× cheaper, 24/7, consistent, and auditable (every decision has a `reason_code` in
`optimization_decisions`; every action is guardrailed and audit-logged). The partner
console (Phase 4) *enables* these freelancers as a distribution channel instead of
competing with them.

## 4. We supersede the OSS references (§17.6) — port, don't depend

The PRD seeds from n8n workflows and scripts. We read them as **reference logic** and
re-implemented the behavior in versioned, tested Python so reasoning, guardrails, and
idempotency live in code — not in visual nodes that drift across tenants.

| OSS reference | What we took | Where it lives — better |
|---|---|---|
| `nikD305/Meta-Ads-Automation-n8n` (launch/monitor) | campaign launch + insight pull shape | `pipeline.launch_campaigns` / `run_optimization` — typed, tenant-scoped, outbox-durable |
| `luukalleman/meta-ads-system` (kill-losers/scale-winners, hourly loop) | the full refresh-and-reallocate loop | `pipeline._decide` + `run_optimization`: kill zero-conv / CPL>3× / fatigue(freq>4)→refresh; scale winners (+20%/day cap); **reallocate freed budget to winners**; **promote test winners** to prospecting; emergency day-cap stop; 3-tier PROSPECTING/RETARGETING/TESTING split. Repointed CPL→**CPQL**; every move bounded by `guardrails/spend.py` |
| `kaansrc/performance-marketer` (creative brain) | site-scrape → competitor counter-positioning → image + **UGC video** → 3-campaign structure → daily optimize | `integrations/scrape.py` → `Scout` (counter-positioning); `CreativeProvider.generate_video` (image + VIDEO_9_16 per angle); 3-tier launch; `run_optimization` |
| `renthelautomations/competitor-product-intelligence-meta-ads` | Ad Library scouting | `MetaAdapter.search_ad_library` feeding `Scout` |
| `pypesdev/meta-daily-adspend-update-sheet` | daily reporting | `pipeline.run_report` + `Reporter` (vernacular WhatsApp, not a sheet) |
| `*/whatsapp-...-booking-bot` (n8n + Cloud API) | qualification/booking flow | `Closer` state machine — **scoped & Meta-compliant** (a guard blocks general-purpose replies, which the OSS bots don't) |
| `oliverames/meta-mcp-server`, `attainmentlabs/meta-ads-cli` | tool-call surface for Meta | `integrations/meta` `ChannelAdapter` — mockable, retryable, behind the durability seam |

Why this wins over running the n8n stack directly: **multi-tenant RLS isolation, exactly-once
money-moving Meta edits (transactional outbox), per-account spend & compliance guardrails,
and CPQL optimization** — none of which a pile of single-tenant workflows provide.

## 5. Scoreboard (what's proven today vs build plan)

✅ implemented + tested in this repo (mock transport): Closer qualification loop, Scout
research, Maker creative, Buyer launch, Optimizer (CPL→CPQL) with bounds, Reporter,
onboarding, Razorpay billing with GST, RLS, outbox durability.
⏳ next: real Meta/WhatsApp/Razorpay credentials wired (flip `MOCK_*`), onboarding UI +
creative-review UI, account memory (pgvector priors), partner/admin consoles, Expo app.
⛔ external gates (weeks): Meta app review, WhatsApp WABA + green-tick, DPDP residency
sign-off.
