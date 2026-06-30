# WhatsApp transport: go live sooner, cheapest in India

Our `WhatsAppAdapter` interface means the transport is a **config choice**, not a code
change. Set `WHATSAPP_PROVIDER` and flip `MOCK_WHATSAPP=false`. Three options:

| `WHATSAPP_PROVIDER` | What it is | Onboarding speed | Cost |
|---|---|---|---|
| `bsp` | An aggregator that is a Meta **Tech Provider** | **Hours–days** (their Embedded Signup) | Their platform fee + small per-msg markup |
| `cloud` | Meta **Cloud API direct** | Weeks (you become a Tech Provider, app review for multi-tenant) | **No markup** — cheapest at scale |
| `mock` | In-memory (dev/CI) | instant | free |

## Two facts that make "sooner" real (verified, 2026)
1. **No green-tick needed to launch.** An *unverified* WABA sends immediately (250
   msgs/day). Meta *Business* verification (fast — not the 4–8-week green-tick) lifts it
   to 1,000/day, then quality-based tiers scale to 10k/100k/unlimited. Green-tick is
   cosmetic. → Skip it for the pilot.
2. **CTWA 72-hour free-entry window.** When a lead enters via a Click-to-WhatsApp ad and
   you reply within 24h, **all** messages (including templates) are **free for 72h**. Our
   Closer qualifies inside this window → the AI conversation costs ≈ **₹0 variable**. The
   only paid messaging is re-engagement *outside* the window (marketing template
   ₹0.8631 + 18% GST as of Jan 2026; utility ₹0.115; 1,000 free service convos/month).

## Recommendation (cheapest by stage)
- **Pilot / lowest volume:** a **pay-per-message, ₹0-monthly BSP** (e.g. PayPerWA-style)
  or Cloud-API-direct. With the 72h free window the per-lead messaging bill is near zero;
  you avoid any fixed platform fee.
- **Scaling / CTWA-heavy:** a BSP with **built-in CTWA + Ads-Manager integration and a
  low platform fee** (e.g. AiSensy-tier) — cheapest *at scale* with ads bundled. (These
  are our PRD competitors as *products*; here they're just our messaging *infrastructure*
  — we keep the ad-running + AI-qualification moat.)
- **Steady-state cheapest:** migrate to **`cloud` (Cloud API direct)** once we hold our
  own Tech Provider access — no BSP markup, and the adapter already exists.

> Pricing and the cheapest specific provider shift often — confirm current rates before
> committing. The architecture lets you switch providers with one env var, so you are
> never locked in.

## Configure a BSP (generic)
Most Indian BSPs expose a Meta-compatible REST send endpoint and forward inbound in
Meta's webhook JSON (so our `parse_inbound` works unchanged). Set:
```
MOCK_WHATSAPP=false
WHATSAPP_PROVIDER=bsp
BSP_BASE_URL=https://<provider-api-base>
BSP_API_KEY=<key>
BSP_SEND_PATH=/messages          # provider's send path
BSP_AUTH_HEADER=Authorization    # or e.g. "x-api-key"
BSP_AUTH_SCHEME=Bearer           # or "" if the header takes the bare key
```
Point the provider's inbound webhook at `https://<webhook-intake>/webhooks/whatsapp`
and add a `wa_routes` row mapping the business `phone_number_id → (tenant_id, account_id)`.
If a provider uses a non-Meta payload shape, override `build_payload` /
`parse_inbound` in a thin subclass — that's the only provider-specific code.

## The very fastest path (days, before any WABA)
PRD §6.1.3 **CTWA-to-app**: the ad's destination is the owner's *existing* WhatsApp app
number — no API at all. Run CTWA ads (manually in Ads Manager or via a BSP), leads land
in the owner's WhatsApp, and our app handles onboarding/reporting/billing. Trade-off: the
**AI Closer can't run** on this path (messages don't reach our API), so use it only to
prove ad economics while a BSP number is being provisioned in parallel.
