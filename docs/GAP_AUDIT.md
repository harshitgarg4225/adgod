# Salmor — Exhaustive Product Gap Audit & Build Log

> An entrepreneur's perfection pass across eight dimensions — product, user-need,
> ease-of-use, design/delight (Airbnb bar), security/privacy, scalability/reliability,
> tech quality, and monetization. Each item is tagged with severity and a **status**:
>
> - ✅ **Done** — built and verified this pass (tests/build green)
> - 🟡 **Partial** — foundation built; finish noted
> - ⬜ **Planned** — scoped, not yet built
>
> Audit method: eight parallel reviewer agents read the actual code (backend `src/`,
> web `web/`, migrations, tests). Findings below are de-duplicated and grounded in files.

---

## 0. Brand
- ✅ Rename user-facing brand LeadPilot → **Salmor** (web, FastAPI titles, README, docs).
  Internal package stays `leadpilot`; agent stays **Saathi**.

---

## 1. Product completeness & user-need (persona: Ramesh/Priya/Asha)

| # | Gap | Sev | Status |
|---|-----|-----|--------|
| 1.1 | No self-serve signup — unknown phone 404'd; accounts only via seed/partner | critical | ✅ create-on-first-verified-OTP → new owner account in `SIGNED_UP` |
| 1.2 | Day-one zero value — dashboard spend/CPQL hardcoded to 0 | high | ✅ real spend/CPQL/7-day trend from `ad_insights` |
| 1.3 | No settings/profile screen — nothing editable after onboarding | high | ✅ `/settings` + `GET/PATCH /accounts/{id}/settings` |
| 1.4 | No owner autopilot control / pause kill-switch | high | ✅ pause/resume endpoints + dashboard toggle + autopilot selector |
| 1.5 | Notifications generated but never surfaced | high | ✅ `/notifications` screen + unread badge + mark-read |
| 1.6 | No real lead inbox (buried in dashboard, no filter/search) | high | ✅ `/leads` with search + Hot/Warm/Won tabs |
| 1.7 | Owner can't send WhatsApp from app (only wa.me deep-link) | high | 🟡 wa.me + tel deep-links polished; in-app compose ⬜ |
| 1.8 | Booking/scheduling orphaned — `BOOK`/`BOOKED`/`Booking` unused | critical | ⬜ orchestrator `BOOK` transition + `/bookings` |
| 1.9 | No follow-up / silence / re-engagement system | critical | 🟡 trial-sweep + retention shipped; `re_engage` beat + `NO_RESPONSE` ⬜ |
| 1.10 | 24h/72h WhatsApp window not enforced (prod sends rejected) | critical | ⬜ branch outbound on `free_window_expires_at` → approved template |
| 1.11 | Partner can't manage a client (no drill-in/impersonate/per-client) | high | ⬜ |
| 1.12 | Daily report computed but never sent to owner WhatsApp | med | ⬜ |
| 1.13 | Budget+timeline captured as one field; scoring conflates | med | ⬜ |
| 1.14 | Owner can't approve/reject/edit individual creatives | med | 🟡 real images render + launch blocked on failed policy; per-item approve ⬜ |
| 1.15 | Brief read-only; owner can't correct AI understanding | med | ⬜ |
| 1.16 | Wallet disconnected from spend; monthly cap unenforced | med | ⬜ |
| 1.17 | No GST/business details (GSTIN) → non-compliant invoices; no PDF | med | ⬜ |
| 1.18 | No help/support/FAQ | med | 🟡 WhatsApp-to-support link in settings; FAQ ⬜ |
| 1.19 | Autonomous loop only optimize+report; pre-live needs triggers; `can_transition` bypassed | med | ⬜ |

---

## 2. Ease-of-use & onboarding

| # | Gap | Sev | Status |
|---|-----|-----|--------|
| 2.1 | Frontend 100% hardcoded English; no i18n; `<html lang>` fixed | blocker | ✅ i18n layer (inline-English fallback + Hindi catalog), live switch, `<html lang>` sync |
| 2.2 | No voice-to-text despite low-literacy persona | blocker | ✅ Web Speech mic on Input/Textarea (offer, business, city) |
| 2.3 | Connect demands raw Meta/WhatsApp IDs a mobile owner can't get | blocker/critical | ⬜ Embedded Signup OAuth (raw-ID fields remain for pilot) |
| 2.4 | No Offline state/detection; no PWA shell | blocker | ✅ OfflineBanner + PWA manifest + icon |
| 2.5 | Login: no OTP autofill, fake default number, no validation | high | ✅ `autocomplete=one-time-code`, maxLength, phone validation, empty default |
| 2.6 | No form validation anywhere; advances through empty fields | high | 🟡 login + settings validated; full onboarding step-gating ⬜ |
| 2.7 | No bottom nav / persistent home | high | ✅ BottomNav (Home/Leads/Reports/Billing) |
| 2.8 | No global 401 handling except dashboard | med | ✅ centralised 401 → login in `req()` |
| 2.9 | English error fallbacks bypass vernacular | high | ✅ localized fallbacks via `t()` |
| 2.10 | No save/resume in onboarding; back loses state | high | ⬜ persist onboarding draft |
| 2.11 | Loading = blank spinner everywhere | high | ✅ content-shaped skeletons |
| 2.12 | Notifications API unused | low | ✅ surfaced (1.5) |

---

## 3. Design & delight (Airbnb bar) — was ~2/10 "wireframe"

| # | Gap | Sev | Status |
|---|-----|-----|--------|
| 3.1 | No design system — ad-hoc utilities, 5 colours, no scales | P0 | ✅ full token system (colour/type/space/radius/elevation/motion) |
| 3.2 | No shared primitives; button re-declared ~12×; 2 Badge impls | P0 | ✅ `components/ui` kit, single source of truth |
| 3.3 | System font only — no type identity | P1 | ✅ Inter + Noto Sans Devanagari via `next/font` |
| 3.4 | Zero hover/focus/active/transition; no focus-visible | P0 | ✅ all states + focus rings + 150ms transitions |
| 3.5 | No skeletons, no toasts, no modals/sheets | P0/P1 | ✅ Skeleton, Toast, Sheet, ConfirmDialog |
| 3.6 | Emoji as icon set (inconsistent on Android) | P1 | ✅ inline SVG icon set |
| 3.7 | No logo — brand mark was 🚀 emoji | P0 | ✅ Saathi avatar + wordmark + app icon |
| 3.8 | No charts anywhere (ad-performance product!) | P0 | ✅ BarChart + Sparkline (dependency-free SVG) |
| 3.9 | No celebratory moments (first sale, ads live) | P1 | ✅ Celebration confetti on Won + launch |
| 3.10 | Saathi has no presence/personality | P1 | ✅ avatar + persistent SaathiStatusCard on home/reports |
| 3.11 | No safe-area handling for fixed CTAs | P1 | ✅ `cta-dock` with `env(safe-area-inset-bottom)` |
| 3.12 | Contrast/tiny-font/a11y gaps | P0/P1 | 🟡 rem type ramp, focus rings, aria-live, labelled icons; full WCAG audit ⬜ |
| 3.13 | Fake creative previews (🖼️ placeholder) | P1 | ✅ render real `asset_url` |
| 3.14 | Locked `max-w-md` desktop; no trust cues | P1 | 🟡 trust lines on login/billing; framed desktop ⬜ |

---

## 4. Security & privacy

| # | Gap | Sev | Status |
|---|-----|-----|--------|
| 4.1 | Dev-default secrets only warned in prod | P0 | ✅ fail-closed (SystemExit) on insecure secrets in production |
| 4.2 | Webhooks accept unsigned when env mis-set | P0 | ✅ mandatory signatures for any non-dev/test ENVIRONMENT |
| 4.3 | IDOR: OWNER with null account_id got all-access | P1 | ✅ exact-match required; null = no access |
| 4.4 | OTP verify enumerates users (404 vs token) | P1 | ✅ removed via create-on-first-login |
| 4.5 | Rate limiting fully fail-open; OTP cost abuse | P0 | ✅ fail-closed option; applied to OTP send/verify |
| 4.6 | Meta token in `?access_token=` query (logs) | P1 | ✅ moved to `Authorization: Bearer` |
| 4.7 | CSV export formula injection | P2 | ✅ neutralised (`'` prefix on `= + - @`) |
| 4.8 | No security headers (CSP/HSTS/XFO/nosniff) | P1 | ✅ middleware on both services + prod CORS tightened |
| 4.9 | LLM prompt injection from lead text unguarded | P1 | ✅ untrusted-input delimiting + system guard in provider |
| 4.10 | `dump.rdb` committed | P2 | ✅ untracked + gitignored |
| 4.11 | JWT: no rotation/revocation; trusts token claims | P0 | ⬜ jti/token-version + per-request DB re-bind |
| 4.12 | Token in `localStorage` (XSS) | P0 | ⬜ HttpOnly cookie migration |
| 4.13 | No DPDP consent/retention/DSR | P0 | 🟡 retention sweeps shipped; consent capture + export/delete ⬜ |
| 4.14 | Idempotency keys global, not tenant-scoped | P1 | ⬜ (module currently unwired) |
| 4.15 | `wa_routes` never revoked → recycled number leak | P1 | ⬜ |
| 4.16 | OTP hashed with static jwt_secret pepper, no salt | P1 | ⬜ |
| 4.17 | Webhook replay (no timestamp window) | P1 | ⬜ |
| 4.18 | No pinned dependency lockfile/hashes | P1 | ⬜ |

---

## 5. Scalability, reliability & observability

| # | Gap | Sev | Status |
|---|-----|-----|--------|
| 5.1 | Tables grow unbounded (no retention) | P1 | ✅ retention sweep cron |
| 5.2 | Missing hot-path indexes (messages.wa_message_id, dlq, inbound, idem) | P1 | ✅ migration 0006 |
| 5.3 | LLM `temperature` → 400 on Opus 4.8 (every real reasoning call) | P0 | ✅ vendor-branch; sampling param dropped for Claude |
| 5.4 | Razorpay subscribe not idempotent → duplicate mandates | P0 | ✅ reuse live subscription on retry/replay |
| 5.5 | LLM budget cap defined but never enforced | P1 | ✅ enforced per-account/day before each call |
| 5.6 | LLM/SDK calls had no timeout (hang blocks Closer) | P1 | ✅ explicit timeouts |
| 5.7 | Fragile LLM JSON parsing | P1 | ✅ robust `{…}` extraction + fences |
| 5.8 | No 429/Retry-After handling on outbound | P1 | ⬜ |
| 5.9 | `Base.metadata.create_all` in migrations (model drift) | P1 | ⬜ pin explicit DDL going forward |
| 5.10 | Indexes not `CONCURRENTLY` (lock risk at scale) | P1 | 🟡 documented; small tables fine now |
| 5.11 | No partitioning on messages/ad_insights | P1 | ⬜ |
| 5.12 | ~25 bare-UUID FKs, no `ON DELETE` | P1 | ⬜ |
| 5.13 | Webhook handlers `async def` calling sync DB (loop block) | P1 | ⬜ |
| 5.14 | `export_leads_csv` materializes all rows | P2 | ⬜ stream |
| 5.15 | No circuit breakers / Closer degraded fallback | P2 | ⬜ |
| 5.16 | GST floor under-collected by ≤1 paise | P2 | ✅ round-half-up |

---

## 6. What was already solid (not over-flagged)
Deterministic optimizer with hard spend bounds; scope/compliance/anomaly guards;
transactional outbox + idempotent inbound (exactly-once effects); Postgres RLS (FORCE,
fail-closed) multi-tenancy; trust-based approval gating; pgvector semantic memory with
k-anonymity; mock adapters behind real interfaces.

---

## 7. Backlog closed (second pass)
The ⬜ items above were then built end-to-end:

- **1.7 / 1.9 / 1.10** — owner in-app WhatsApp reply; hourly re-engagement of silent
  (NO_RESPONSE) leads via approved templates; the 24h window now branches free-form vs.
  template (effect handler + `saathi/outbound.py`; seeded templates).
- **1.8** — booking flow (bookings router, orchestrator BOOK transition, `/bookings`
  screen, lead "Book appointment").
- **1.11** — partner client drill-in + 15% commission + "open as client" scoped token +
  acting-as banner.
- **1.13 / 1.14 / 1.15** — budget/timeline captured separately; per-creative
  approve/reject; editable brief + angle on/off toggles.
- **1.16 / 1.17** — ad-wallet screen + top-ups; monthly spend cap enforced at launch;
  GSTIN/legal-name/address capture; printable GST invoice document.
- **2.3** — Meta Embedded Signup start endpoint + "Connect with Facebook" button.
- **4.11–4.18** — JWT re-bind + token-version revocation (logout/delete); DPDP consent +
  data export + erasure; per-row OTP salt; tenant-scoped idempotency keys; Razorpay
  webhook replay dedupe; wa_route hijack refused; pinned `requirements.lock`.
- **5.8 / 5.12 / 5.13 / 5.14 / 5.15** — Retry-After-aware retry + circuit breaker;
  `ON DELETE CASCADE` FKs (migration 0009, `NOT VALID`); webhook handlers offloaded to a
  threadpool; streaming CSV export; degraded-Closer canned-reply fallback.

### Deliberately deferred (rationale, not omission)
- **4.12 HttpOnly cookies** — a full cookie+CSRF migration of the auth flow needs product
  sign-off; the risk it addresses (token theft/replay) is now mitigated by per-request JWT
  re-bind + token-version revocation and a strict CSP.
- **5.9 explicit-DDL migrations / 5.10 `CONCURRENTLY` / 5.11 partitioning** — operational
  hardening best applied against real production volume; the create_all-from-model
  approach and plain indexes are documented tradeoffs, fine at current scale.
- **1.12 daily report to WhatsApp** — delivered via the in-app notification centre; a
  business→owner template send needs an owner-side conversation record (small follow-up).
- **3.12 full WCAG pass / 3.14 framed desktop** — foundational a11y (focus rings, aria-live,
  labelled icons, rem type) is in; a formal WCAG audit + desktop treatment remain polish.

## 8. Verification snapshot (final)
- Backend: `ruff` clean; **96** tests passing; migrations 0001→0009 apply
  head-from-scratch.
- Web: production build green, **19** routes.
