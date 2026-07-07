"""Saathi ad pipeline — the autonomous loop competitors don't have (PRD §6.2–6.5).

Each phase is a function: research → creative → launch → optimize → report. They run
under a tenant session, call the scoped sub-agents, pass results through the Guardrail
Engine, persist state, and drive Meta/creative/WhatsApp effects. Deterministic in mock
mode so the whole loop is testable end to end without external accounts.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from leadpilot.common.clock import IST, ist_day_start
from leadpilot.common.config import settings
from leadpilot.common.logging import get_logger
from leadpilot.core.enums import (
    AccountPhase,
    AdSetRole,
    AgentName,
    AgentRunStatus,
    ApprovalKind,
    ApprovalState,
    ApprovalStatus,
    AutopilotLevel,
    CampaignStatus,
    ComplianceStatus,
    CreativeFormat,
    InsightLevel,
    LeadStatus,
    NotificationKind,
    OptimizationAction,
    WhatsAppMode,
)
from leadpilot.core.models import (
    Account,
    Ad,
    AdInsight,
    AdSet,
    AgentRun,
    Angle,
    Approval,
    BusinessBrief,
    BusinessProfile,
    Campaign,
    Creative,
    GuardrailEvent,
    Lead,
    MetaConnection,
    Notification,
    OptimizationDecision,
    User,
    WhatsAppConnection,
)
from leadpilot.integrations.meta import meta_adapter_for_account
from leadpilot.integrations.scrape import scrape_site
from leadpilot.integrations.whatsapp import get_whatsapp_adapter
from leadpilot.saathi.agents.buyer import BuyerAgent
from leadpilot.saathi.agents.maker import MakerAgent
from leadpilot.saathi.agents.reporter import ReporterAgent
from leadpilot.saathi.agents.scout import ScoutAgent
from leadpilot.saathi.guardrails.anomaly import check_adset_anomaly
from leadpilot.saathi.guardrails.compliance import check_creative_copy
from leadpilot.saathi.guardrails.engine import GuardrailEngine
from leadpilot.saathi.guardrails.spend import check_daily_spend, clamp_scale
from leadpilot.saathi.memory import embed_creative, retrieve_winning_creatives
from leadpilot.saathi.providers.creative import get_creative_provider

log = get_logger("pipeline")

# Budget split (PRD §6.4.2) and optimization thresholds (PRD §6.5).
# 3-tier structure: proven winners get the bulk, retargeting warms visitors, a thin slice
# tests new creative in isolation so an unproven ad can't disrupt the winners.
BUDGET_SPLIT = {AdSetRole.PROSPECTING: 65, AdSetRole.RETARGETING: 20, AdSetRole.TESTING: 15}
MIN_SPEND_THRESHOLD_PAISE = 10000   # ₹100 before a pause decision
# Optimizer thresholds (a steady lead stream comes from killing fatigue + reallocating to
# winners on a loop, not from launching once).
FATIGUE_FREQUENCY = 4.0             # audience saturation → refresh creative
FATIGUE_CTR = 0.01                  # CTR below 1% with high frequency → fatigue
ZERO_CONV_SPEND_MULTIPLE = 2        # spent ≥ 2× target CPQL with 0 leads → kill
HIGH_CPL_MULTIPLE = 3               # CPL > 3× target → kill
WINNER_MIN_LEADS = 5               # a "proven" winner (efficient + enough volume)
EMERGENCY_DAY_MULTIPLE = 1.25       # day spend ≥ 1.25× budget → emergency pause-all


def _now() -> datetime:
    return datetime.now(UTC)


# ─────────────────────────── Scout: research ───────────────────────────

def run_research(session: Session, *, tenant_id: UUID, account_id: UUID,
                 refresh: bool = False) -> UUID:
    account = session.get(Account, account_id)
    profile = session.scalar(select(BusinessProfile).where(BusinessProfile.account_id == account_id))
    city = (profile.service_area_city if profile else None) or "your city"
    offer = (profile.offer if profile else None) or account.business_name
    # Ground the research in the owner's own site (value props / testimonials / pricing)
    # and competitor ads from the Meta Ad Library (fresh angles + counter-positioning).
    site_text = scrape_site(profile.website_url if profile else None)
    # Competitor data is optional garnish: the Ad Library API is separately gated
    # (identity verification) and a System User marketing token may not have it — research
    # must still produce a brief from the site + profile alone.
    try:
        competitors = meta_adapter_for_account(session, account_id).search_ad_library(
            query=f"{account.category} {city}")
    except Exception as exc:  # noqa: BLE001 - degrade, never stall the account
        log.warning("ad_library_unavailable", account=str(account_id), error=str(exc)[:200])
        competitors = []

    out = ScoutAgent().run(
        session, tenant_id=tenant_id, account_id=account_id,
        context={"category": account.category, "offer": offer, "city": city,
                 "site_content": site_text, "competitors": competitors},
    )

    version = (session.scalar(
        select(func.coalesce(func.max(BusinessBrief.version), 0))
        .where(BusinessBrief.account_id == account_id)
    ) or 0) + 1
    brief = BusinessBrief(
        tenant_id=tenant_id, account_id=account_id, offer=out.brief.offer,
        audience=out.brief.audience, usp=out.brief.usp, objections=out.brief.objections,
        tone=out.brief.tone, source_refs={"competitors": competitors}, version=version,
    )
    session.add(brief)
    session.flush()
    for a in out.angles:
        session.add(Angle(tenant_id=tenant_id, account_id=account_id, brief_id=brief.id,
                          title=a.title, rationale=a.rationale, hypothesis=a.hypothesis))
    if not refresh:
        # A post-launch refresh must never knock a LIVE account out of the live loop —
        # it only versions the brief and appends fresh angles for future rotations.
        account.phase = AccountPhase.RESEARCHED.value
    log.info("research_done", account=str(account_id), angles=len(out.angles),
             refresh=refresh)
    return brief.id


# ─────────────────────────── Maker: creative ───────────────────────────

def run_creative(session: Session, *, tenant_id: UUID, account_id: UUID, max_angles: int = 3) -> list[UUID]:
    account = session.get(Account, account_id)
    brief = session.scalar(
        select(BusinessBrief).where(BusinessBrief.account_id == account_id)
        .order_by(BusinessBrief.version.desc())
    )
    angles = session.scalars(
        select(Angle).where(Angle.account_id == account_id, Angle.status == "ACTIVE").limit(max_angles)
    ).all()
    guard = GuardrailEngine(session, tenant_id=tenant_id, account_id=account_id)
    full_autopilot = account.autopilot_level == AutopilotLevel.FULL.value
    creative_ids: list[UUID] = []

    # The ad's button opens either a WhatsApp chat or a phone call — the copy's CTA
    # must match, or a CALL ad reads "message us on WhatsApp" under a CALL NOW button.
    wa_conn = session.scalar(
        select(WhatsAppConnection).where(WhatsAppConnection.account_id == account_id))
    cta_channel = (
        "phone call (the button dials the business — tell them to call now)"
        if wa_conn and wa_conn.mode == WhatsAppMode.CALL.value
        else "WhatsApp message (the button opens a WhatsApp chat)"
    )

    for angle in angles:
        # Memory: retrieve past winning creatives similar to this angle (tenant-scoped).
        winners = [
            w.headline for w in retrieve_winning_creatives(
                session, account_id=account_id, query_text=angle.title, k=3)
            if w.headline
        ]
        out = MakerAgent().run(
            session, tenant_id=tenant_id, account_id=account_id,
            context={"language": account.default_language, "angle": angle.title,
                     "brief": brief.offer if brief else "", "winners": winners,
                     "cta_channel": cta_channel},
        )
        variant = out.variants[0]
        comp = guard.record(check_creative_copy(
            variant.primary_text, variant.headline, variant.description
        ))
        compliance_status = ComplianceStatus.PASSED if comp.ok else ComplianceStatus.FAILED
        image_url = None
        if comp.ok and out.image_prompts:
            image_url = get_creative_provider().generate_image(prompt=out.image_prompts[0])

        approval = (
            ApprovalState.APPROVED_FOR_LAUNCH if (comp.ok and full_autopilot)
            else (ApprovalState.DRAFT if comp.ok else ApprovalState.REJECTED)
        )
        creative = Creative(
            tenant_id=tenant_id, account_id=account_id, angle_id=angle.id,
            language=account.default_language, format=CreativeFormat.IMAGE_VERTICAL.value,
            primary_text=variant.primary_text, headline=variant.headline,
            description=variant.description, asset_url=image_url,
            compliance_status=compliance_status.value, approval_status=approval.value,
            hypothesis=angle.hypothesis,
        )
        session.add(creative)
        session.flush()
        if comp.ok:
            embed_creative(session, creative)  # semantic memory for future retrieval
        creative_ids.append(creative.id)

        # UGC-style video variant for the same angle — sustained scroll-stopping creative
        # keeps click-through (and leads) from decaying. Uses the approved copy as the
        # script; reuses the image as the thumbnail.
        if comp.ok:
            script = f"{variant.headline}. {variant.primary_text}"
            video_url = get_creative_provider().generate_video(script=script)
            video = Creative(
                tenant_id=tenant_id, account_id=account_id, angle_id=angle.id,
                language=account.default_language, format=CreativeFormat.VIDEO_9_16.value,
                primary_text=variant.primary_text, headline=variant.headline,
                description=variant.description, asset_url=video_url, thumb_url=image_url,
                compliance_status=compliance_status.value, approval_status=approval.value,
                hypothesis=angle.hypothesis,
            )
            session.add(video)
            session.flush()
            creative_ids.append(video.id)

    # Trust gate (PRD §4.5.4): full autopilot auto-approves; otherwise queue an approval.
    from leadpilot.common.i18n import t as _t

    lang = account.default_language or "en"
    if full_autopilot:
        account.phase = AccountPhase.CREATIVE_GENERATED.value
        title, body = _t("notify.auto_launch.title", lang), f"{len(creative_ids)} ads ready."
    else:
        account.phase = AccountPhase.PENDING_APPROVAL.value
        session.add(Approval(
            tenant_id=tenant_id, account_id=account_id, kind=ApprovalKind.CREATIVE_BATCH.value,
            payload={"creative_ids": [str(i) for i in creative_ids]},
            status=ApprovalStatus.PENDING.value,
        ))
        title = _t("notify.auto_launch.title", lang)
        if (account.autopilot_level == AutopilotLevel.ASSISTED.value
                and (account.auto_approve_hours or 0) > 0):
            when = (datetime.now(IST) + timedelta(hours=account.auto_approve_hours))
            body = _t("notify.auto_launch.body", lang, n=len(creative_ids),
                      when=when.strftime("%I:%M %p"))
        else:
            body = f"{len(creative_ids)} ad creatives generated."
    session.add(Notification(
        tenant_id=tenant_id, account_id=account_id, kind=NotificationKind.CREATIVE_READY.value,
        title=title, body=body,
    ))
    log.info("creative_done", account=str(account_id), creatives=len(creative_ids))
    return creative_ids


# ─────────────────────────── Buyer: launch ───────────────────────────

def approve_creative_batch(session: Session, *, tenant_id: UUID, account_id: UUID,
                           approval: Approval, auto: bool = False) -> int:
    """Promote a CREATIVE_BATCH's creatives to launch-ready. VETO-PRESERVING: only DRAFT
    + compliance-PASSED creatives are promoted — an owner's explicit REJECTED must never
    be resurrected (especially by the auto-approve cron). Moves the account phase forward
    only when something was actually promoted. Shared by the human decide endpoint and
    the autopilot-with-veto cron."""
    promoted = 0
    for cid in approval.payload.get("creative_ids", []):
        c = session.get(Creative, cid)
        if (c is not None and c.compliance_status == ComplianceStatus.PASSED.value
                and c.approval_status == ApprovalState.DRAFT.value):
            c.approval_status = ApprovalState.APPROVED_FOR_LAUNCH.value
            promoted += 1
    if promoted:
        account = session.get(Account, account_id)
        if account is not None and account.phase == AccountPhase.PENDING_APPROVAL.value:
            account.phase = AccountPhase.APPROVED.value
    log.info("creative_batch_approved", account=str(account_id), promoted=promoted,
             auto=auto)
    return promoted


def set_live_state(session: Session, *, tenant_id: UUID, account_id: UUID,
                   pause: bool, reason: str | None = None) -> bool:
    """Pause/resume must reach META, not just our rows — a 'paused' account whose
    campaign keeps delivering is spending real money against the owner's explicit stop.
    Resume also reactivates PAUSED ad sets (the recovery path after an emergency pause
    or a kill-rule sweep) and restores the pre-pause phase."""
    account = session.get(Account, account_id)
    if account is None:
        return False
    campaign = session.scalar(select(Campaign).where(
        Campaign.account_id == account_id,
        Campaign.status.in_([CampaignStatus.ACTIVE.value, CampaignStatus.PAUSED.value]))
        .order_by(Campaign.created_at.desc()))
    meta = meta_adapter_for_account(session, account_id) if campaign is not None else None

    if pause:
        if campaign is not None and campaign.meta_campaign_id:
            meta.set_status(level="CAMPAIGN", meta_id=campaign.meta_campaign_id,
                            status="PAUSED")
            campaign.status = CampaignStatus.PAUSED.value
        if account.phase != AccountPhase.PAUSED.value:
            account.phase_before_pause = account.phase
        account.pause_reason = reason or "owner"
        account.phase = AccountPhase.PAUSED.value
        return True

    # Resume: campaign back on, every paused ad set back on (optimizer re-kills real
    # losers later — a resume that resumes nothing is the wedge we're fixing).
    if campaign is not None and campaign.meta_campaign_id:
        meta.set_status(level="CAMPAIGN", meta_id=campaign.meta_campaign_id, status="ACTIVE")
        campaign.status = CampaignStatus.ACTIVE.value
        for adset in session.scalars(select(AdSet).where(
                AdSet.campaign_id == campaign.id,
                AdSet.status == CampaignStatus.PAUSED.value)).all():
            if adset.meta_adset_id:
                meta.set_status(level="ADSET", meta_id=adset.meta_adset_id, status="ACTIVE")
            adset.status = CampaignStatus.ACTIVE.value
    restored = account.phase_before_pause
    live_phases = {AccountPhase.LIVE.value, AccountPhase.OPTIMIZING.value,
                   AccountPhase.FATIGUE_REFRESH.value}
    account.phase = restored if restored in live_phases else (
        AccountPhase.OPTIMIZING.value if campaign is not None else
        (restored or AccountPhase.OPTIMIZING.value))
    account.pause_reason = None
    account.phase_before_pause = None
    return True


def is_platform_blind(mode: str | None) -> bool:
    """Own-number CTWA and click-to-call both convert OFF-platform (the owner's WhatsApp
    app / phone) — lead-based kill rules must never fire on them."""
    return mode in ("APP_DESTINATION", "CALL")


def _ctwa_cta(wa_conn: WhatsAppConnection | None, page_id: str) -> dict:
    """link_data payload by destination. WhatsApp modes get the review-free wa.me deep
    link; CALL mode gets a CALL_NOW CTA dialing the owner. Graph requires a `link` —
    fall back to the Page URL if no number exists."""
    import re

    digits = ""
    if wa_conn and wa_conn.display_phone:
        digits = re.sub(r"\D", "", wa_conn.display_phone)
    if wa_conn and wa_conn.mode == "CALL" and digits:
        tel = f"tel:+{digits}"
        return {"link": tel, "call_to_action": {"type": "CALL_NOW", "value": {"link": tel}}}
    link = f"https://wa.me/{digits}" if digits else f"https://facebook.com/{page_id}"
    return {"link": link, "call_to_action": {"type": "WHATSAPP_MESSAGE", "value": {"link": link}}}


def _budget_tiers(daily_budget: int) -> dict[AdSetRole, int]:
    """Split the budget across the 3-tier structure, folding tiers whose share would fall
    below Meta's per-adset daily minimum into PROSPECTING (small budgets run one ad set
    rather than failing the launch or getting rejected by Graph)."""
    minimum = settings.meta_min_adset_daily_paise
    if daily_budget < minimum:
        raise ValueError(
            f"daily budget too small to launch: ₹{daily_budget // 100}/day is under the "
            f"Meta ad-set minimum (₹{minimum // 100}/day)"
        )
    roles = [AdSetRole.PROSPECTING, AdSetRole.RETARGETING, AdSetRole.TESTING]
    split_total = sum(BUDGET_SPLIT[r] for r in roles)
    tiers = {r: daily_budget * BUDGET_SPLIT[r] // split_total for r in roles}
    for role in (AdSetRole.TESTING, AdSetRole.RETARGETING):
        if tiers.get(role, 0) < minimum:
            tiers[AdSetRole.PROSPECTING] += tiers.pop(role)
    return tiers


def launch_campaigns(session: Session, *, tenant_id: UUID, account_id: UUID) -> list[UUID]:
    account = session.get(Account, account_id)
    profile = session.scalar(select(BusinessProfile).where(BusinessProfile.account_id == account_id))
    meta_conn = session.scalar(select(MetaConnection).where(MetaConnection.account_id == account_id))
    ad_account_id = (meta_conn.ad_account_id if meta_conn else None) or "MOCKACT"
    page_id = (meta_conn.page_id if meta_conn else None) or "MOCKPAGE"
    daily_budget = profile.daily_budget_paise if profile else 50000

    # CTWA destination: in APP_DESTINATION mode the ad opens the owner's existing WhatsApp
    # number (no Cloud API / WABA needed — the fastest go-live path).
    wa_conn = session.scalar(
        select(WhatsAppConnection).where(WhatsAppConnection.account_id == account_id))
    cta = _ctwa_cta(wa_conn, page_id)

    # Idempotency: if an ACTIVE campaign already exists, do not relaunch.
    existing = session.scalar(
        select(Campaign).where(Campaign.account_id == account_id,
                               Campaign.status == CampaignStatus.ACTIVE.value)
    )
    if existing is not None:
        return [existing.id]

    # Approval gate: only APPROVED_FOR_LAUNCH (compliant) creatives go live. Adapters
    # without a video upload path launch image/text ads only — never a degraded video ad.
    meta = meta_adapter_for_account(session, account_id)
    creatives = session.scalars(
        select(Creative).where(
            Creative.account_id == account_id,
            Creative.compliance_status == ComplianceStatus.PASSED.value,
            Creative.approval_status == ApprovalState.APPROVED_FOR_LAUNCH.value,
        )
    ).all()
    if not meta.supports_video:
        creatives = [c for c in creatives if c.format != CreativeFormat.VIDEO_9_16.value]
    if not creatives:
        raise ValueError("no approved creatives to launch (awaiting owner approval)")
    creative_ids = [str(c.id) for c in creatives]

    plan = BuyerAgent().run(
        session, tenant_id=tenant_id, account_id=account_id,
        context={"brief": account.business_name, "city": profile.service_area_city if profile else "",
                 "radius_km": profile.service_radius_km if profile else 10,
                 "daily_budget_paise": daily_budget, "creative_ids": creative_ids},
    )

    # Spend guard: planned daily spend must never exceed the account budget.
    check_daily_spend(proposed_daily_paise=daily_budget, account_daily_budget_paise=daily_budget)
    tiers = _budget_tiers(daily_budget)

    objective = plan.campaigns[0].objective if plan.campaigns else "OUTCOME_LEADS"
    # Name is the cross-system idempotency key: unique per account, stable across retries.
    campaign_name = f"{account.business_name} CTWA {str(account_id)[:8]}"

    # Crash-safety: a partial launch leaves an IN_REVIEW row (committed independently
    # below) — resume it instead of stacking a duplicate campaign on Meta.
    campaign = session.scalar(
        select(Campaign).where(Campaign.account_id == account_id,
                               Campaign.status == CampaignStatus.IN_REVIEW.value)
    )
    if campaign is not None:
        meta_campaign_id = campaign.meta_campaign_id
    else:
        # Even the local row can be lost (crash before commit) — ask Meta first. Campaigns
        # are created PAUSED and only activated at the very end, so an orphan never spends.
        meta_campaign_id = (
            meta.find_campaign_by_name(ad_account_id=ad_account_id, name=campaign_name)
            or meta.create_campaign(ad_account_id=ad_account_id, name=campaign_name,
                                    objective=objective)
        )
        # Claim the launch in its own committed transaction so a crash mid-adsets can be
        # resumed (the caller's session would roll this back with everything else).
        from leadpilot.core.db import tenant_session as _claim_session

        try:
            with _claim_session(tenant_id) as claim:
                claim.add(Campaign(
                    tenant_id=tenant_id, account_id=account_id,
                    meta_campaign_id=meta_campaign_id, objective=objective,
                    channel="META_CTWA", status=CampaignStatus.IN_REVIEW.value,
                    daily_budget_paise=daily_budget, strategy={"split": "65/20/15"},
                ))
        except IntegrityError:
            # Lost the launch race (uq_campaigns_one_open): a concurrent cron/click claimed
            # first. Adopt the winner's campaign and resume it — never a 500, never a dup.
            log.warning("launch_race_lost", account=str(account_id))
        campaign = session.scalar(
            select(Campaign).where(
                Campaign.account_id == account_id,
                Campaign.status.in_([CampaignStatus.IN_REVIEW.value,
                                     CampaignStatus.ACTIVE.value])))
        if campaign.status == CampaignStatus.ACTIVE.value:
            return [campaign.id]  # the race winner already finished
        meta_campaign_id = campaign.meta_campaign_id

    city = profile.service_area_city if profile else "Indore"
    radius = profile.service_radius_km if profile else 10
    # Resume support: skip tiers that already exist locally or on Meta (matched by name).
    existing_roles = {
        a.role for a in session.scalars(
            select(AdSet).where(AdSet.campaign_id == campaign.id)).all()
    }
    meta_adsets_by_name = {
        a.get("name"): a.get("id")
        for a in meta.list_adsets(meta_campaign_id=meta_campaign_id)
    }

    # 3-tier structure: PROSPECTING (proven, 65%) + RETARGETING (visitors, 20%) +
    # TESTING (new creative in isolation, 15%). Testing winners graduate to prospecting.
    for role, budget in tiers.items():
        if role.value in existing_roles:
            continue
        adset_name = f"{role.value} {city}"
        targeting = {
            "geo_locations": {"cities": [{"name": city, "radius": radius, "distance_unit": "kilometer"}]},
            "age_min": 18, "age_max": 55,
            # Explicit placements: the promise is "Facebook AND Instagram" — never leave
            # it to Meta's default placement expansion to decide.
            "publisher_platforms": ["facebook", "instagram"],
            "_role": role.value,
        }
        if role == AdSetRole.RETARGETING:
            # Warm audience: people who engaged with the ads / clicked to WhatsApp.
            targeting["custom_audiences"] = [{"type": "ENGAGEMENT", "lookback_days": 30}]
        # Ad-set shape follows the destination: CTWA optimizes for conversations;
        # click-to-call uses Meta's call-leads combination. Verify both once against a
        # PAUSED live launch before trusting new Graph field shapes.
        call_mode = wa_conn is not None and wa_conn.mode == "CALL"
        meta_adset_id = meta_adsets_by_name.get(adset_name) or meta.create_adset(
            ad_account_id=ad_account_id, campaign_id=meta_campaign_id,
            name=adset_name, targeting=targeting, daily_budget_paise=budget,
            optimization_goal="QUALITY_CALL" if call_mode else "CONVERSATIONS",
            destination_type="PHONE_CALL" if call_mode else "WHATSAPP",
            promoted_object={"page_id": page_id},
        )
        adset = AdSet(
            tenant_id=tenant_id, account_id=account_id, campaign_id=campaign.id,
            meta_adset_id=meta_adset_id, name=adset_name, role=role.value,
            targeting=targeting, budget_paise=budget, status=CampaignStatus.ACTIVE.value,
        )
        session.add(adset)
        session.flush()
        # One ad per creative into this ad set. Names are deterministic per creative so a
        # resumed launch reuses ads that already exist on Meta instead of stacking dupes.
        existing_ads = {a.get("name"): a.get("id")
                        for a in meta.list_ads(meta_adset_id=meta_adset_id)}
        for creative in creatives:
            ad_name = f"ad-{creative.id.hex[:10]}"
            meta_ad_id = existing_ads.get(ad_name)
            if meta_ad_id is None:
                meta_creative_id = meta.create_creative(
                    ad_account_id=ad_account_id, page_id=page_id,
                    message=creative.primary_text or "",
                    headline=creative.headline or "", link_or_cta=cta,
                    image_url=creative.asset_url,
                )
                meta_ad_id = meta.create_ad(
                    ad_account_id=ad_account_id, adset_id=meta_adset_id,
                    creative_meta_id=meta_creative_id, name=ad_name,
                )
            session.add(Ad(tenant_id=tenant_id, account_id=account_id, ad_set_id=adset.id,
                          meta_ad_id=meta_ad_id, creative_id=creative.id,
                          status=CampaignStatus.ACTIVE.value, review_status="IN_REVIEW"))
        meta.set_status(level="ADSET", meta_id=meta_adset_id, status="ACTIVE")

    meta.set_status(level="CAMPAIGN", meta_id=meta_campaign_id, status="ACTIVE")
    campaign.status = CampaignStatus.ACTIVE.value
    account.phase = AccountPhase.LIVE.value

    # Trust: each successful launch builds trust; cross the threshold → full autopilot.
    account.trust_score = (account.trust_score or 0) + 1
    if (account.trust_score >= settings.default_trust_threshold
            and account.autopilot_level == AutopilotLevel.ASSISTED.value):
        account.autopilot_level = AutopilotLevel.FULL.value

    session.add(Notification(
        tenant_id=tenant_id, account_id=account_id, kind=NotificationKind.CAMPAIGN_LIVE.value,
        title="Your ads are live 🎉", body="Saathi launched your WhatsApp ad campaign.",
    ))
    log.info("launch_done", account=str(account_id), campaign=str(campaign.id))
    return [campaign.id]


# ─────────────────────────── Optimizer: optimize toward CPQL ───────────────────────────

def _upsert_daily_insight(session: Session, *, tenant_id: UUID, account_id: UUID,
                          level: str, ref_id: UUID, day: datetime, **fields) -> None:
    """One AdInsight row per (level, ref, day) — hourly optimizer passes refresh it in
    place, so summing a day never overcounts."""
    existing = session.scalar(
        select(AdInsight).where(
            AdInsight.account_id == account_id, AdInsight.level == level,
            AdInsight.ref_id == ref_id, AdInsight.date >= day,
            AdInsight.date < day + timedelta(days=1))
    )
    if existing is None:
        session.add(AdInsight(tenant_id=tenant_id, account_id=account_id, level=level,
                              ref_id=ref_id, date=day, **fields))
    else:
        for k, v in fields.items():
            setattr(existing, k, v)


def run_optimization(session: Session, *, tenant_id: UUID, account_id: UUID) -> list[dict]:
    account = session.get(Account, account_id)
    target_cpql = account.target_cpql_paise or 20000
    ad_sets = session.scalars(
        select(AdSet).where(AdSet.account_id == account_id,
                            AdSet.status == CampaignStatus.ACTIVE.value)
    ).all()
    meta = meta_adapter_for_account(session, account_id)
    if not ad_sets:
        # Recovery: kill rules can legally pause every ad set, but a LIVE account with an
        # ACTIVE campaign and zero delivery is a stall, not a strategy — restart the
        # prospecting tier and let the rules re-evaluate with fresh data.
        campaign = session.scalar(select(Campaign).where(
            Campaign.account_id == account_id,
            Campaign.status == CampaignStatus.ACTIVE.value))
        paused = session.scalars(select(AdSet).where(
            AdSet.account_id == account_id,
            AdSet.status == CampaignStatus.PAUSED.value)).all() if campaign else []
        restart = next((a for a in paused if a.role == AdSetRole.PROSPECTING.value),
                       paused[0] if paused else None)
        if restart is None:
            return []
        if restart.meta_adset_id:
            meta.set_status(level="ADSET", meta_id=restart.meta_adset_id, status="ACTIVE")
        restart.status = CampaignStatus.ACTIVE.value
        session.add(OptimizationDecision(
            tenant_id=tenant_id, account_id=account_id, run_id=None,
            level=InsightLevel.ADSET.value, ref_id=restart.id,
            action=OptimizationAction.RESUME.value, reason_code="auto_recovery_restart",
            before={}, after={"status": "ACTIVE"}, applied=True))
        log.warning("optimizer_auto_recovery", account=str(account_id),
                    adset=str(restart.id))
        ad_sets = [restart]

    # Blind mode: on the own-number (APP_DESTINATION) path the qualification chats happen
    # on the client's phone — platform-side lead counts can be zero while the client's
    # WhatsApp is full. Lead-based kill rules would murder healthy campaigns, so they are
    # disabled; spend caps and frequency-based fatigue (real signals) stay on.
    wa_conn = session.scalar(
        select(WhatsAppConnection).where(WhatsAppConnection.account_id == account_id))
    blind = (not settings.mock_meta) and wa_conn is not None \
        and is_platform_blind(wa_conn.mode)
    guard = GuardrailEngine(session, tenant_id=tenant_id, account_id=account_id)
    rows = meta.get_insights(level=InsightLevel.ADSET.value,
                             meta_ids=[a.meta_adset_id for a in ad_sets if a.meta_adset_id])
    by_meta = {r.meta_id: r for r in rows}

    # Account-level qualified leads today → CPQL (joined from the lead stream, PRD §6.5.1).
    # IST day boundary: Meta's date_preset=today follows the ad account timezone, so the
    # snapshot day must too — UTC midnight would clobber each night's numbers at 05:30 IST.
    today = ist_day_start()
    qualified_today = session.scalar(
        select(func.count(Lead.id)).where(
            Lead.account_id == account_id, Lead.created_at >= today,
            Lead.status.in_([LeadStatus.QUALIFIED_HOT.value, LeadStatus.QUALIFIED_WARM.value]),
        )
    ) or 0

    total_budget = account_daily_budget(session, account_id)
    decisions: list[dict] = []
    run = AgentRun(tenant_id=tenant_id, account_id=account_id, agent=AgentName.OPTIMIZER.value,
                   trigger="cron", status=AgentRunStatus.OK.value, model="rule-engine")
    session.add(run)
    session.flush()

    # Emergency stop: if the day's spend has blown past the budget (runaway), pause
    # everything and escalate — the ultimate spend safety net. Only meaningful against real
    # Meta spend (the mock's synthetic numbers aren't calibrated to the budget).
    day_spend = sum(r.spend_paise for r in rows)
    if not settings.mock_meta and total_budget and day_spend >= int(EMERGENCY_DAY_MULTIPLE * total_budget):
        for adset in ad_sets:
            if adset.meta_adset_id:
                meta.set_status(level="ADSET", meta_id=adset.meta_adset_id, status="PAUSED")
            adset.status = CampaignStatus.PAUSED.value
            session.add(OptimizationDecision(
                tenant_id=tenant_id, account_id=account_id, run_id=run.id,
                level=InsightLevel.ADSET.value, ref_id=adset.id,
                action=OptimizationAction.PAUSE.value, reason_code="emergency_daily_cap",
                before={"budget_paise": adset.budget_paise}, after={}, applied=True))
        account.phase_before_pause = account.phase
        account.pause_reason = "emergency"
        account.phase = AccountPhase.PAUSED.value
        session.add(Notification(
            tenant_id=tenant_id, account_id=account_id, kind=NotificationKind.ANOMALY.value,
            title="Ads paused for safety",
            body="Today's spend hit the safety limit, so Saathi paused everything. Review in Settings."))
        log.warning("optimizer_emergency_pause", account=str(account_id), day_spend=day_spend)
        return [{"adset": str(a.id), "action": "PAUSE", "reason": "emergency_daily_cap"}
                for a in ad_sets]

    # Track freed budget (from kills) and winners (to reallocate toward) — the
    # refresh-and-reallocate loop is what keeps leads flowing instead of decaying.
    freed_paise = 0
    winners: list[AdSet] = []

    for adset in ad_sets:
        row = by_meta.get(adset.meta_adset_id)
        if row is None:
            continue
        cpl = (row.spend_paise // row.leads) if row.leads else None
        cpql = (row.spend_paise // qualified_today) if qualified_today else None
        # Persist the insight as a DAILY SNAPSHOT (upsert on adset+day): the optimizer runs
        # hourly with cumulative today-numbers — appending would overcount spend ~24× in
        # every consumer (reports, dashboard).
        _upsert_daily_insight(
            session, tenant_id=tenant_id, account_id=account_id,
            level=InsightLevel.ADSET.value, ref_id=adset.id, day=today,
            spend_paise=row.spend_paise, impressions=row.impressions, clicks=row.clicks,
            ctr=row.ctr, frequency=row.frequency, leads=row.leads,
            qualified_leads=qualified_today, cpl_paise=cpl or 0, cpql_paise=cpql or 0,
        )

        # Anomaly guard first (PRD §4.5.5): pause + escalate, overrides the rule engine.
        # Lead-based anomaly rules are meaningless in blind mode (see above).
        anomaly = guard.record(check_adset_anomaly(
            spend_paise=row.spend_paise, leads=row.leads, cpl_paise=cpl,
            target_cpql_paise=target_cpql)) if not blind else None
        if anomaly is not None and not anomaly.ok:
            action, reason, after = OptimizationAction.PAUSE, f"anomaly:{anomaly.detail['reason']}", {}
            meta.set_status(level="ADSET", meta_id=adset.meta_adset_id, status="PAUSED")
            adset.status = CampaignStatus.PAUSED.value
            freed_paise += adset.budget_paise  # reclaim for winners
            session.add(Notification(
                tenant_id=tenant_id, account_id=account_id, kind=NotificationKind.ANOMALY.value,
                title="Paused an ad set", body="Saathi paused an underperforming ad set and is reviewing."))
        else:
            action, reason, after = _decide(adset, row, cpl, target_cpql, total_budget,
                                            blind=blind)
            if action == OptimizationAction.PAUSE:
                meta.set_status(level="ADSET", meta_id=adset.meta_adset_id, status="PAUSED")
                adset.status = CampaignStatus.PAUSED.value
                freed_paise += adset.budget_paise  # reclaim for winners
            elif action == OptimizationAction.SCALE:
                capped = _cap_to_account_budget(ad_sets, adset, after["budget_paise"],
                                                total_budget)
                if capped <= adset.budget_paise:
                    # A winner held back by the owner's budget is worth recording — it is
                    # the honest answer to "why didn't Saathi scale my best ad set?".
                    session.add(OptimizationDecision(
                        tenant_id=tenant_id, account_id=account_id, run_id=run.id,
                        level=InsightLevel.ADSET.value, ref_id=adset.id,
                        action=OptimizationAction.SCALE.value,
                        reason_code="held_by_account_budget",
                        before={"budget_paise": adset.budget_paise},
                        after={}, applied=False))
                    action, reason, after = OptimizationAction.NO_OP, "account_budget_cap", {}
                    winners.append(adset)  # still a winner for freed-budget reallocation
                else:
                    after = {"budget_paise": capped}
                    meta.set_adset_budget(meta_adset_id=adset.meta_adset_id,
                                          daily_budget_paise=capped)
                    adset.budget_paise = capped
                    winners.append(adset)
                # Promote a proven test winner into the prospecting tier (isolation → scale).
                if reason == "proven_winner" and adset.role == AdSetRole.TESTING.value:
                    adset.role = AdSetRole.PROSPECTING.value
                    session.add(OptimizationDecision(
                        tenant_id=tenant_id, account_id=account_id, run_id=run.id,
                        level=InsightLevel.ADSET.value, ref_id=adset.id,
                        action=OptimizationAction.PROMOTE.value, reason_code="test_winner_promoted",
                        before={"role": "TESTING"}, after={"role": "PROSPECTING"}, applied=True))
                    decisions.append({"adset": str(adset.id), "action": "PROMOTE",
                                      "reason": "test_winner_promoted", "cpl_paise": cpl})
            elif action == OptimizationAction.REQUEST_CREATIVE:
                # Fatigue refresh (PRD §6.5.2) with a 24h cooldown — the optimizer runs
                # hourly and a saturated audience must not spawn a new creative + Meta ad
                # + notification every single hour.
                if _rotated_recently(session, account_id):
                    action, reason, after = OptimizationAction.NO_OP, "fatigue_cooldown", {}
                else:
                    rotate_fresh_creative(session, tenant_id=tenant_id,
                                          account_id=account_id, target_adset=adset)
                    session.add(Notification(
                        tenant_id=tenant_id, account_id=account_id,
                        kind=NotificationKind.ANOMALY.value,
                        title="Refreshing tired ads",
                        body="Saathi created fresh creative for a fatigued ad set."))

        if action != OptimizationAction.NO_OP:
            session.add(OptimizationDecision(
                tenant_id=tenant_id, account_id=account_id, run_id=run.id,
                level=InsightLevel.ADSET.value, ref_id=adset.id, action=action.value,
                reason_code=reason, before={"budget_paise": adset.budget_paise, "cpl_paise": cpl},
                after=after, applied=True,
            ))
        decisions.append({"adset": str(adset.id), "action": action.value, "reason": reason,
                          "cpl_paise": cpl})

    # Reallocate the budget freed from killed ad sets to the winners (70/20/10 spirit) —
    # each still bounded by the +20%/day guardrail so total spend stays within the cap.
    if freed_paise > 0 and winners:
        share = freed_paise // len(winners)
        for adset in winners:
            proposed = clamp_scale(current_paise=adset.budget_paise,
                                   proposed_paise=adset.budget_paise + share)
            new_budget = _cap_to_account_budget(ad_sets, adset, proposed, total_budget)
            if new_budget <= adset.budget_paise:
                continue
            meta.set_adset_budget(meta_adset_id=adset.meta_adset_id, daily_budget_paise=new_budget)
            session.add(OptimizationDecision(
                tenant_id=tenant_id, account_id=account_id, run_id=run.id,
                level=InsightLevel.ADSET.value, ref_id=adset.id,
                action=OptimizationAction.REALLOCATE.value, reason_code="reallocate_to_winner",
                before={"budget_paise": adset.budget_paise},
                after={"budget_paise": new_budget}, applied=True))
            adset.budget_paise = new_budget
            decisions.append({"adset": str(adset.id), "action": "REALLOCATE",
                              "reason": "reallocate_to_winner", "cpl_paise": None})

    # Daily ACCOUNT rollup — the single source the dashboard, settings screen and the
    # monthly-cap gate read. Refreshed on every optimizer pass so "today's spend" is live.
    total_leads = sum(r.leads for r in rows)
    total_spend = sum(r.spend_paise for r in rows)
    _upsert_daily_insight(
        session, tenant_id=tenant_id, account_id=account_id,
        level=InsightLevel.ACCOUNT.value, ref_id=account_id, day=today,
        spend_paise=total_spend, impressions=sum(r.impressions for r in rows),
        clicks=sum(r.clicks for r in rows), ctr=0.0, frequency=0.0,
        leads=total_leads, qualified_leads=qualified_today,
        cpl_paise=(total_spend // total_leads) if total_leads else 0,
        cpql_paise=(total_spend // qualified_today) if qualified_today else 0,
    )

    # Meta review rejections and dead delivery are silent otherwise — sweep them here so
    # the operator sees an alert instead of a mystery zero-lead week. Real mode only.
    if not settings.mock_meta:
        _sweep_ad_reviews(session, meta, tenant_id=tenant_id, account_id=account_id)
        if rows and all(r.impressions == 0 for r in rows) and datetime.now(IST).hour >= 12:
            already = session.scalar(select(GuardrailEvent).where(
                GuardrailEvent.account_id == account_id,
                GuardrailEvent.action_taken == "ZERO_DELIVERY",
                GuardrailEvent.created_at >= today))
            if already is None:
                session.add(GuardrailEvent(
                    tenant_id=tenant_id, account_id=account_id, type="ANOMALY",
                    severity="ERROR", action_taken="ZERO_DELIVERY",
                    detail={"reason": "active_campaign_zero_delivery",
                            "hint": "check ad review status / Page-WhatsApp link"}))

    if account.phase == AccountPhase.LIVE.value:
        account.phase = AccountPhase.OPTIMIZING.value
    log.info("optimize_done", account=str(account_id), decisions=len(decisions))
    return decisions


def _sweep_ad_reviews(session: Session, meta, *, tenant_id: UUID, account_id: UUID) -> None:
    ads = session.scalars(select(Ad).where(
        Ad.account_id == account_id, Ad.status == CampaignStatus.ACTIVE.value)).all()
    meta_ids = [a.meta_ad_id for a in ads if a.meta_ad_id]
    if not meta_ids:
        return
    try:
        statuses = meta.get_ad_statuses(meta_ids=meta_ids)
    except Exception as exc:  # noqa: BLE001 - the sweep must never break optimization
        log.warning("ad_status_sweep_failed", account=str(account_id), error=str(exc)[:200])
        return
    from leadpilot.common.i18n import t as _t

    account = session.get(Account, account_id)
    lang = (account.default_language if account else None) or "en"
    rejected_any = False
    for ad in ads:
        status = statuses.get(ad.meta_ad_id or "")
        if not status or status == ad.review_status:
            continue
        ad.review_status = status
        if status in {"DISAPPROVED", "WITH_ISSUES"}:
            # Real remediation, not fiction: stop the rejected ad and rotate a fresh
            # creative in (cooldown-guarded), so "Saathi is making a fix" is true.
            if ad.meta_ad_id:
                try:
                    meta.set_status(level="AD", meta_id=ad.meta_ad_id, status="PAUSED")
                except Exception as exc:  # noqa: BLE001 - sweep must survive
                    log.warning("ad_pause_failed", ad=str(ad.id), error=str(exc)[:120])
            ad.status = CampaignStatus.PAUSED.value
            rejected_any = True
            session.add(GuardrailEvent(
                tenant_id=tenant_id, account_id=account_id, type="ANOMALY", severity="ERROR",
                action_taken="AD_REJECTED", detail={"reason": "meta_ad_rejected",
                                                    "ad_id": str(ad.id), "status": status}))
            session.add(Notification(
                tenant_id=tenant_id, account_id=account_id,
                kind=NotificationKind.ANOMALY.value,
                title=_t("notify.ad_rejected.title", lang),
                body=_t("notify.ad_rejected.body", lang)))
    if rejected_any and not _rotated_recently(session, account_id):
        rotate_fresh_creative(session, tenant_id=tenant_id, account_id=account_id)
        session.add(OptimizationDecision(
            tenant_id=tenant_id, account_id=account_id, run_id=None,
            level=InsightLevel.AD.value, ref_id=account_id,
            action=OptimizationAction.REQUEST_CREATIVE.value,
            reason_code="meta_rejected_replacement", before={}, after={}, applied=True))


def reconcile_budgets(session: Session, *, tenant_id: UUID, account_id: UUID) -> int:
    """The owner changed the daily budget — push it to the LIVE Meta ad sets immediately.
    A spend control that only edits a database row while Meta keeps spending the old
    amount is a trust breaker. Scales each active ad set proportionally."""
    profile = session.scalar(
        select(BusinessProfile).where(BusinessProfile.account_id == account_id))
    if profile is None:
        return 0
    ad_sets = session.scalars(select(AdSet).where(
        AdSet.account_id == account_id, AdSet.status == CampaignStatus.ACTIVE.value)).all()
    current_total = sum(a.budget_paise for a in ad_sets)
    if not ad_sets or current_total <= 0:
        return 0
    meta = meta_adapter_for_account(session, account_id)
    new_total = profile.daily_budget_paise
    changed = 0
    for adset in ad_sets:
        new_budget = max(settings.meta_min_adset_daily_paise,
                         adset.budget_paise * new_total // current_total)
        if new_budget == adset.budget_paise or not adset.meta_adset_id:
            continue
        meta.set_adset_budget(meta_adset_id=adset.meta_adset_id,
                              daily_budget_paise=new_budget)
        adset.budget_paise = new_budget
        changed += 1
    if changed:
        log.info("budgets_reconciled", account=str(account_id), adsets=changed,
                 new_total=new_total)
    return changed


def _cap_to_account_budget(ad_sets: list, adset, proposed: int, total_budget: int) -> int:
    """The +20% clamp is per-adset; this caps the SUM of active ad-set budgets at the
    account's daily budget so hourly compounding can never grow past what the owner set."""
    if not total_budget:
        return proposed
    others = sum(a.budget_paise for a in ad_sets
                 if a is not adset and a.status == CampaignStatus.ACTIVE.value)
    return min(proposed, max(adset.budget_paise, total_budget - others))


def _rotated_recently(session: Session, account_id: UUID, hours: int = 24) -> bool:
    last = session.scalar(
        select(OptimizationDecision.created_at).where(
            OptimizationDecision.account_id == account_id,
            OptimizationDecision.action == OptimizationAction.REQUEST_CREATIVE.value)
        .order_by(OptimizationDecision.created_at.desc()))
    return last is not None and last > _now() - timedelta(hours=hours)


def _decide(adset: AdSet, row, cpl, target_cpql, total_budget, *, blind: bool = False):
    """Kill-losers / scale-winners / refresh-fatigue rule engine. All bounds are
    deterministic — the guardrails cap what any decision can move (§6.5.1)."""
    # Kill: real spend with zero conversions. Skipped in blind mode — zero platform-side
    # leads on the own-number path usually means we can't see them, not that none exist.
    if (not blind and row.leads == 0
            and row.spend_paise >= ZERO_CONV_SPEND_MULTIPLE * target_cpql):
        return OptimizationAction.PAUSE, "zero_conversions", {"status": "PAUSED"}
    # Kill: runaway cost per lead.
    if (cpl is not None and cpl > HIGH_CPL_MULTIPLE * target_cpql
            and row.spend_paise >= MIN_SPEND_THRESHOLD_PAISE):
        return OptimizationAction.PAUSE, "cpl_over_3x_target", {"status": "PAUSED"}
    # Refresh: audience saturation (frequency) burns out a creative — rotate a fresh one in
    # rather than just pausing, so the lead stream never decays after a few days.
    if row.frequency > FATIGUE_FREQUENCY:
        return OptimizationAction.REQUEST_CREATIVE, "fatigue_frequency", {}
    # Scale: efficient ad set (CPL ≤ target) with conversions. +20%/day cap.
    if cpl is not None and cpl <= target_cpql and row.leads >= 1:
        scaled = clamp_scale(current_paise=adset.budget_paise,
                             proposed_paise=int(adset.budget_paise * 1.2))
        reason = "proven_winner" if row.leads >= WINNER_MIN_LEADS else "efficient_scale"
        return OptimizationAction.SCALE, reason, {"budget_paise": scaled}
    return OptimizationAction.NO_OP, "stable", {}


def account_daily_budget(session: Session, account_id: UUID) -> int:
    profile = session.scalar(select(BusinessProfile).where(BusinessProfile.account_id == account_id))
    return profile.daily_budget_paise if profile else 50000


def rotate_fresh_creative(session: Session, *, tenant_id: UUID, account_id: UUID,
                          target_adset: AdSet | None = None) -> UUID | None:
    """Fatigue refresh: generate a fresh creative and rotate it into the Testing ad set —
    or, when no Testing tier exists (small budgets fold it away; promotion converts it),
    straight into the fatigued ad set itself (PRD §6.5.2)."""
    account = session.get(Account, account_id)
    angle = session.scalar(
        select(Angle).where(Angle.account_id == account_id, Angle.status == "ACTIVE"))
    testing = session.scalar(
        select(AdSet).where(AdSet.account_id == account_id, AdSet.role == AdSetRole.TESTING.value,
                            AdSet.status == CampaignStatus.ACTIVE.value))
    if testing is None or not testing.meta_adset_id:
        testing = target_adset
    if angle is None or testing is None or not testing.meta_adset_id:
        return None
    meta_conn = session.scalar(select(MetaConnection).where(MetaConnection.account_id == account_id))
    ad_account_id = (meta_conn.ad_account_id if meta_conn else None) or "MOCKACT"
    page_id = (meta_conn.page_id if meta_conn else None) or "MOCKPAGE"
    wa_conn = session.scalar(
        select(WhatsAppConnection).where(WhatsAppConnection.account_id == account_id))

    winners = [w.headline for w in retrieve_winning_creatives(
        session, account_id=account_id, query_text=angle.title, k=3) if w.headline]
    out = MakerAgent().run(
        session, tenant_id=tenant_id, account_id=account_id,
        context={"language": account.default_language, "angle": angle.title,
                 "brief": "", "winners": winners})
    variant = out.variants[0]
    if not check_creative_copy(variant.primary_text, variant.headline, variant.description).ok:
        return None
    image_url = get_creative_provider().generate_image(
        prompt=out.image_prompts[0] if out.image_prompts else variant.headline)
    creative = Creative(
        tenant_id=tenant_id, account_id=account_id, angle_id=angle.id,
        language=account.default_language, format=CreativeFormat.IMAGE_VERTICAL.value,
        primary_text=variant.primary_text, headline=variant.headline,
        description=variant.description, asset_url=image_url,
        compliance_status=ComplianceStatus.PASSED.value,
        approval_status=ApprovalState.APPROVED_FOR_LAUNCH.value, hypothesis=angle.hypothesis)
    session.add(creative)
    session.flush()
    embed_creative(session, creative)

    meta = meta_adapter_for_account(session, account_id)
    meta_creative_id = meta.create_creative(
        ad_account_id=ad_account_id, page_id=page_id, message=variant.primary_text,
        headline=variant.headline, link_or_cta=_ctwa_cta(wa_conn, page_id),
        image_url=image_url)
    meta_ad_id = meta.create_ad(ad_account_id=ad_account_id, adset_id=testing.meta_adset_id,
                                creative_meta_id=meta_creative_id, name=f"refresh-{variant.headline}"[:60])
    session.add(Ad(tenant_id=tenant_id, account_id=account_id, ad_set_id=testing.id,
                  meta_ad_id=meta_ad_id, creative_id=creative.id,
                  status=CampaignStatus.ACTIVE.value, review_status="IN_REVIEW"))
    log.info("fatigue_rotation", account=str(account_id), creative=str(creative.id))
    return creative.id


# ─────────────────────────── Reporter: daily summary ───────────────────────────

def run_report(session: Session, *, tenant_id: UUID, account_id: UUID) -> str:
    account = session.get(Account, account_id)
    today = ist_day_start()
    # Sum ADSET-level daily snapshots only — mixing levels (or the pre-fix hourly appends)
    # would tell a paying owner an inflated spend number.
    spend = session.scalar(
        select(func.coalesce(func.sum(AdInsight.spend_paise), 0))
        .where(AdInsight.account_id == account_id, AdInsight.date >= today,
               AdInsight.level == InsightLevel.ADSET.value)
    ) or 0
    enquiries = session.scalar(
        select(func.count(Lead.id)).where(Lead.account_id == account_id, Lead.created_at >= today)
    ) or 0
    qualified = session.scalar(
        select(func.count(Lead.id)).where(
            Lead.account_id == account_id, Lead.created_at >= today,
            Lead.status.in_([LeadStatus.QUALIFIED_HOT.value, LeadStatus.QUALIFIED_WARM.value]),
        )
    ) or 0
    decisions = session.scalar(
        select(func.count(OptimizationDecision.id))
        .where(OptimizationDecision.account_id == account_id,
               OptimizationDecision.created_at >= today)
    ) or 0
    cpql = (spend // qualified) if qualified else 0

    out = ReporterAgent().run(
        session, tenant_id=tenant_id, account_id=account_id,
        context={"language": account.default_language, "spend_paise": spend,
                 "enquiries": enquiries, "qualified": qualified, "cpql_paise": cpql,
                 "decisions": decisions},
    )
    session.add(Notification(
        tenant_id=tenant_id, account_id=account_id, kind=NotificationKind.REPORT.value,
        title="Aaj ki report", body=out.message,
    ))
    # WhatsApp delivery needs a Cloud-API number + approved template; when this account
    # has one, send it there too. On the own-number path the operator digest
    # (leadpilot.reporter.operator_digest) carries these summaries to the founder instead.
    wa = session.scalar(
        select(WhatsAppConnection).where(WhatsAppConnection.account_id == account_id))
    owner_phone = session.scalar(
        select(User.phone).where(User.account_id == account_id, User.role == "OWNER"))
    if (wa is not None and wa.mode == "CLOUD_API" and wa.phone_number_id
            and owner_phone and not settings.mock_whatsapp):
        try:  # pragma: no cover - requires live WhatsApp creds
            get_whatsapp_adapter().send_template(
                phone_number_id=wa.phone_number_id, to_phone=owner_phone,
                template_name="daily_report", language=account.default_language or "hi",
                params=[out.message])
        except Exception as exc:  # noqa: BLE001 - report must still land in-app
            log.warning("report_wa_send_failed", account=str(account_id), error=str(exc)[:200])
    log.info("report_done", account=str(account_id))
    return out.message
