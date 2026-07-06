# Salmor — what it does today, and the channel roadmap

Salmor is the one-stop tool an Indian SMB uses to run ads autonomously, keep getting
results, and keep self-learning. This maps the owner's mental model to what's built.

## The owner's promises

| The owner wants… | Status | How |
|---|---|---|
| **Take my money** | ✅ (+ activation) | Subscription plans + GST invoices + wallet; Razorpay auto-charge is code-complete and turns on when the Razorpay account is activated. Until then: manual UPI + admin "Mark paid". **Ad spend is billed by Meta directly to the client's own ad account — Salmor never custodies ad money** (deliberate: avoids money-transmitter regulation). |
| **Figure out what I sell** | ✅ | Scout scrapes the site, reads the profile, pulls competitor ads, writes a brief (offer/audience/USP/objections) + angles. The owner can correct it. |
| **Create ads and verify what works** | ✅ | Copy + AI image + UGC video, compliance-checked, launched in a prospecting/retargeting/testing structure; the optimizer kills losers, scales winners, promotes test winners hourly. |
| **Take a goal and do the rest** | ✅ | The owner sets **max cost per lead** (onboarding + Settings). Every kill/scale/report decision optimises toward it, capped by the daily budget. |
| **Use multiple AI models tomorrow** | ✅ | The LLM router maps agent roles → models by env var, with key-aware routing + cross-vendor fallback (Anthropic + Gemini today; a new vendor is one adapter). |
| **Leads on WhatsApp / calls / messages** | ✅ | Three destinations: own WhatsApp (CTWA), **phone-call ads** (CALL_NOW → the owner's phone), or an AI-closer WhatsApp number. Instant-Form leads polled every 10 min; SMS alert to the owner's phone on every new lead. |
| **Keeps self-learning** | ✅ | Winning creatives embed into per-tenant vector memory that seeds future generations; fatigue rotations refresh tired ads; **research re-runs monthly** so angles never freeze. |

## Channels

| Channel | Status | Notes |
|---|---|---|
| **Facebook** | ✅ Live | Full campaign/adset/ad/creative/insights via the Graph API. |
| **Instagram** | ✅ Live | Every ad set explicitly targets `publisher_platforms: [facebook, instagram]` — IG delivery is guaranteed, not left to Meta's default placement expansion. |
| **WhatsApp** | ✅ Live | As the **lead destination** (that is what a "WhatsApp ad" is — a Click-to-WhatsApp ad on FB/IG that opens a chat). Own-number, Cloud-API, and call modes supported. |
| **Google Ads** | 🔜 Phase 2 | The `ChannelAdapter` seam (`integrations/meta` is one implementation of it) is built to accept a second network. Google is deliberately not in v1 because it needs a **Google Ads developer-token approval + per-client OAuth** (an external approval gate, unlike the review-free Meta agency path) and a different campaign model (Search keywords / Performance Max vs. Meta's audience+placement model). Adding it is a new adapter (`create_campaign`/`create_adset`/`get_insights`/lead retrieval) plus an OAuth connect flow and a Search-intent research branch — a focused build, not a rewrite, because the pipeline, optimizer, goal, budget, memory and UI are all channel-agnostic. |

## Deliberate non-goals (moats, not gaps)

- **Salmor never holds ad spend.** Meta bills each client's own ad account. This keeps
  Salmor out of money-transmitter / PA-PG regulation.
- **No fake platform status.** The review-free launch is legitimate agency operation
  (System User token, own-number CTWA, owned ad accounts), never spoofed verification.
