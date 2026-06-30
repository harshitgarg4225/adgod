"""Saathi ad pipeline — the autonomous loop competitors don't have (PRD §6.2–6.5).

Each phase is a function: research → creative → launch → optimize → report. They run
under a tenant session, call the scoped sub-agents, pass results through the Guardrail
Engine, persist state, and drive Meta/creative/WhatsApp effects. Deterministic in mock
mode so the whole loop is testable end to end without external accounts.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

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
    Lead,
    MetaConnection,
    Notification,
    OptimizationDecision,
)
from leadpilot.integrations.meta import get_meta_adapter
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
BUDGET_SPLIT = {AdSetRole.PROSPECTING: 70, AdSetRole.LOOKALIKE: 20, AdSetRole.TESTING: 10}
MIN_SPEND_THRESHOLD_PAISE = 10000   # ₹100 before a pause decision
FATIGUE_FREQUENCY = 3.0
FATIGUE_CTR = 0.01                  # CTR below 1% with high frequency → fatigue


def _now() -> datetime:
    return datetime.now(UTC)


# ─────────────────────────── Scout: research ───────────────────────────

def run_research(session: Session, *, tenant_id: UUID, account_id: UUID) -> UUID:
    account = session.get(Account, account_id)
    profile = session.scalar(select(BusinessProfile).where(BusinessProfile.account_id == account_id))
    city = (profile.service_area_city if profile else None) or "your city"
    offer = (profile.offer if profile else None) or account.business_name
    competitors = get_meta_adapter().search_ad_library(query=f"{account.category} {city}")

    out = ScoutAgent().run(
        session, tenant_id=tenant_id, account_id=account_id,
        context={"category": account.category, "offer": offer, "city": city,
                 "competitors": competitors},
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
    account.phase = AccountPhase.RESEARCHED.value
    log.info("research_done", account=str(account_id), angles=len(out.angles))
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
                     "brief": brief.offer if brief else "", "winners": winners},
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

    # Trust gate (PRD §4.5.4): full autopilot auto-approves; otherwise queue an approval.
    if full_autopilot:
        account.phase = AccountPhase.CREATIVE_GENERATED.value
    else:
        account.phase = AccountPhase.PENDING_APPROVAL.value
        session.add(Approval(
            tenant_id=tenant_id, account_id=account_id, kind=ApprovalKind.CREATIVE_BATCH.value,
            payload={"creative_ids": [str(i) for i in creative_ids]},
            status=ApprovalStatus.PENDING.value,
        ))
    session.add(Notification(
        tenant_id=tenant_id, account_id=account_id, kind=NotificationKind.CREATIVE_READY.value,
        title="Your ads are ready", body=f"{len(creative_ids)} ad creatives generated.",
    ))
    log.info("creative_done", account=str(account_id), creatives=len(creative_ids))
    return creative_ids


# ─────────────────────────── Buyer: launch ───────────────────────────

def launch_campaigns(session: Session, *, tenant_id: UUID, account_id: UUID) -> list[UUID]:
    account = session.get(Account, account_id)
    profile = session.scalar(select(BusinessProfile).where(BusinessProfile.account_id == account_id))
    meta_conn = session.scalar(select(MetaConnection).where(MetaConnection.account_id == account_id))
    ad_account_id = (meta_conn.ad_account_id if meta_conn else None) or "MOCKACT"
    page_id = (meta_conn.page_id if meta_conn else None) or "MOCKPAGE"
    daily_budget = profile.daily_budget_paise if profile else 50000

    # Idempotency: if an ACTIVE campaign already exists, do not relaunch.
    existing = session.scalar(
        select(Campaign).where(Campaign.account_id == account_id,
                               Campaign.status == CampaignStatus.ACTIVE.value)
    )
    if existing is not None:
        return [existing.id]

    # Approval gate: only APPROVED_FOR_LAUNCH (compliant) creatives go live.
    creatives = session.scalars(
        select(Creative).where(
            Creative.account_id == account_id,
            Creative.compliance_status == ComplianceStatus.PASSED.value,
            Creative.approval_status == ApprovalState.APPROVED_FOR_LAUNCH.value,
        )
    ).all()
    if not creatives:
        raise ValueError("no approved creatives to launch (awaiting owner approval)")
    creative_ids = [str(c.id) for c in creatives]

    plan = BuyerAgent().run(
        session, tenant_id=tenant_id, account_id=account_id,
        context={"brief": account.business_name, "city": profile.service_area_city if profile else "",
                 "radius_km": profile.service_radius_km if profile else 10,
                 "daily_budget_paise": daily_budget, "creative_ids": creative_ids},
    )

    meta = get_meta_adapter()
    # Spend guard: planned daily spend must never exceed the account budget.
    check_daily_spend(proposed_daily_paise=daily_budget, account_daily_budget_paise=daily_budget)

    objective = plan.campaigns[0].objective if plan.campaigns else "OUTCOME_LEADS"
    meta_campaign_id = meta.create_campaign(
        ad_account_id=ad_account_id, name=f"{account.business_name} CTWA", objective=objective,
    )
    campaign = Campaign(
        tenant_id=tenant_id, account_id=account_id, meta_campaign_id=meta_campaign_id,
        objective=objective, channel="META_CTWA", status=CampaignStatus.IN_REVIEW.value,
        daily_budget_paise=daily_budget, strategy={"split": "70/20/10"},
    )
    session.add(campaign)
    session.flush()

    city = profile.service_area_city if profile else "Indore"
    radius = profile.service_radius_km if profile else 10
    # Always build PROSPECTING + TESTING; LOOKALIKE only if a seed exists (none in v1).
    roles = [AdSetRole.PROSPECTING, AdSetRole.TESTING]
    split_total = sum(BUDGET_SPLIT[r] for r in roles)
    for role in roles:
        budget = daily_budget * BUDGET_SPLIT[role] // split_total
        targeting = {
            "geo_locations": {"cities": [{"name": city, "radius": radius, "distance_unit": "kilometer"}]},
            "age_min": 18, "age_max": 55, "_role": role.value,
        }
        meta_adset_id = meta.create_adset(
            ad_account_id=ad_account_id, campaign_id=meta_campaign_id,
            name=f"{role.value} {city}", targeting=targeting, daily_budget_paise=budget,
            optimization_goal="CONVERSATIONS", destination_type="WHATSAPP",
            promoted_object={"page_id": page_id},
        )
        adset = AdSet(
            tenant_id=tenant_id, account_id=account_id, campaign_id=campaign.id,
            meta_adset_id=meta_adset_id, name=f"{role.value} {city}", role=role.value,
            targeting=targeting, budget_paise=budget, status=CampaignStatus.ACTIVE.value,
        )
        session.add(adset)
        session.flush()
        # One ad per creative into this ad set.
        for creative in creatives:
            meta_creative_id = meta.create_creative(
                ad_account_id=ad_account_id, page_id=page_id, message=creative.primary_text or "",
                headline=creative.headline or "", link_or_cta={"call_to_action":
                {"type": "WHATSAPP_MESSAGE"}}, image_url=creative.asset_url,
            )
            meta_ad_id = meta.create_ad(
                ad_account_id=ad_account_id, adset_id=meta_adset_id,
                creative_meta_id=meta_creative_id, name=f"ad-{creative.headline}"[:60],
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

def run_optimization(session: Session, *, tenant_id: UUID, account_id: UUID) -> list[dict]:
    account = session.get(Account, account_id)
    target_cpql = account.target_cpql_paise or 20000
    ad_sets = session.scalars(
        select(AdSet).where(AdSet.account_id == account_id,
                            AdSet.status == CampaignStatus.ACTIVE.value)
    ).all()
    if not ad_sets:
        return []

    meta = get_meta_adapter()
    guard = GuardrailEngine(session, tenant_id=tenant_id, account_id=account_id)
    rows = meta.get_insights(level=InsightLevel.ADSET.value,
                             meta_ids=[a.meta_adset_id for a in ad_sets if a.meta_adset_id])
    by_meta = {r.meta_id: r for r in rows}

    # Account-level qualified leads today → CPQL (joined from the lead stream, PRD §6.5.1).
    today = _now().replace(hour=0, minute=0, second=0, microsecond=0)
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

    for adset in ad_sets:
        row = by_meta.get(adset.meta_adset_id)
        if row is None:
            continue
        cpl = (row.spend_paise // row.leads) if row.leads else None
        cpql = (row.spend_paise // qualified_today) if qualified_today else None
        # Persist the insight (denormalized CPL/CPQL).
        session.add(AdInsight(
            tenant_id=tenant_id, account_id=account_id, level=InsightLevel.ADSET.value,
            ref_id=adset.id, date=_now(), spend_paise=row.spend_paise, impressions=row.impressions,
            clicks=row.clicks, ctr=row.ctr, frequency=row.frequency, leads=row.leads,
            qualified_leads=qualified_today, cpl_paise=cpl or 0, cpql_paise=cpql or 0,
        ))

        # Anomaly guard first (PRD §4.5.5): pause + escalate, overrides the rule engine.
        anomaly = guard.record(check_adset_anomaly(
            spend_paise=row.spend_paise, leads=row.leads, cpl_paise=cpl,
            target_cpql_paise=target_cpql))
        if not anomaly.ok:
            action, reason, after = OptimizationAction.PAUSE, f"anomaly:{anomaly.detail['reason']}", {}
            meta.set_status(level="ADSET", meta_id=adset.meta_adset_id, status="PAUSED")
            adset.status = CampaignStatus.PAUSED.value
            session.add(Notification(
                tenant_id=tenant_id, account_id=account_id, kind=NotificationKind.ANOMALY.value,
                title="Paused an ad set", body="Saathi paused an underperforming ad set and is reviewing."))
        else:
            action, reason, after = _decide(adset, row, cpl, target_cpql, total_budget)
            if action == OptimizationAction.PAUSE:
                meta.set_status(level="ADSET", meta_id=adset.meta_adset_id, status="PAUSED")
                adset.status = CampaignStatus.PAUSED.value
            elif action == OptimizationAction.SCALE:
                meta.set_adset_budget(meta_adset_id=adset.meta_adset_id,
                                      daily_budget_paise=after["budget_paise"])
                adset.budget_paise = after["budget_paise"]
            elif action == OptimizationAction.REQUEST_CREATIVE:
                # Fatigue refresh (PRD §6.5.2): Maker → Buyer rotate fresh creative into Testing.
                rotate_fresh_creative(session, tenant_id=tenant_id, account_id=account_id)
                session.add(Notification(
                    tenant_id=tenant_id, account_id=account_id, kind=NotificationKind.ANOMALY.value,
                    title="Refreshing tired ads", body="Saathi created fresh creative for a fatigued ad set."))

        if action != OptimizationAction.NO_OP:
            session.add(OptimizationDecision(
                tenant_id=tenant_id, account_id=account_id, run_id=run.id,
                level=InsightLevel.ADSET.value, ref_id=adset.id, action=action.value,
                reason_code=reason, before={"budget_paise": adset.budget_paise, "cpl_paise": cpl},
                after=after, applied=True,
            ))
        decisions.append({"adset": str(adset.id), "action": action.value, "reason": reason,
                          "cpl_paise": cpl})

    if account.phase == AccountPhase.LIVE.value:
        account.phase = AccountPhase.OPTIMIZING.value
    log.info("optimize_done", account=str(account_id), decisions=len(decisions))
    return decisions


def _decide(adset: AdSet, row, cpl, target_cpql, total_budget):
    """Rule baseline (PRD §6.5.1). Bounds are deterministic; the LLM cannot exceed them."""
    # Pause runaway losers after minimum spend.
    if cpl is not None and cpl > 2 * target_cpql and row.spend_paise >= MIN_SPEND_THRESHOLD_PAISE:
        return OptimizationAction.PAUSE, "cpl_over_2x_target", {"status": "PAUSED"}
    # Fatigue → request fresh creative.
    if row.frequency > FATIGUE_FREQUENCY and row.ctr < FATIGUE_CTR:
        return OptimizationAction.REQUEST_CREATIVE, "fatigue_freq_ctr", {}
    # Scale efficient ad sets (+20%/day max), within the account budget.
    if cpl is not None and cpl < target_cpql and row.leads > 0:
        scaled = clamp_scale(current_paise=adset.budget_paise,
                             proposed_paise=int(adset.budget_paise * 1.2))
        return OptimizationAction.SCALE, "cpl_below_target", {"budget_paise": scaled}
    return OptimizationAction.NO_OP, "stable", {}


def account_daily_budget(session: Session, account_id: UUID) -> int:
    profile = session.scalar(select(BusinessProfile).where(BusinessProfile.account_id == account_id))
    return profile.daily_budget_paise if profile else 50000


def rotate_fresh_creative(session: Session, *, tenant_id: UUID, account_id: UUID) -> UUID | None:
    """Fatigue refresh: generate a fresh creative and rotate it into the Testing ad set,
    so the lead stream never depends on a single creative (PRD §6.5.2)."""
    account = session.get(Account, account_id)
    angle = session.scalar(
        select(Angle).where(Angle.account_id == account_id, Angle.status == "ACTIVE"))
    testing = session.scalar(
        select(AdSet).where(AdSet.account_id == account_id, AdSet.role == AdSetRole.TESTING.value,
                            AdSet.status == CampaignStatus.ACTIVE.value))
    if angle is None or testing is None or not testing.meta_adset_id:
        return None
    meta_conn = session.scalar(select(MetaConnection).where(MetaConnection.account_id == account_id))
    ad_account_id = (meta_conn.ad_account_id if meta_conn else None) or "MOCKACT"
    page_id = (meta_conn.page_id if meta_conn else None) or "MOCKPAGE"

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

    meta = get_meta_adapter()
    meta_creative_id = meta.create_creative(
        ad_account_id=ad_account_id, page_id=page_id, message=variant.primary_text,
        headline=variant.headline, link_or_cta={"call_to_action": {"type": "WHATSAPP_MESSAGE"}},
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
    today = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    spend = session.scalar(
        select(func.coalesce(func.sum(AdInsight.spend_paise), 0))
        .where(AdInsight.account_id == account_id, AdInsight.date >= today)
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
    # In real mode this goes to the owner's WhatsApp via an approved template.
    _ = get_whatsapp_adapter()
    log.info("report_done", account=str(account_id))
    return out.message
