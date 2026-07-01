"""Saathi autonomous ad pipeline, end to end in mock mode (PRD §6.2–6.5, §6.8).

research → creative → launch → optimize → report, driving an account
ONBOARDING → RESEARCHED → CREATIVE_GENERATED → LIVE → OPTIMIZING."""
from __future__ import annotations

from sqlalchemy import func, select

from leadpilot.core.db import tenant_session
from leadpilot.core.models import (
    Account,
    Ad,
    AdInsight,
    AdSet,
    Angle,
    BusinessBrief,
    Campaign,
    Creative,
    Notification,
    OptimizationDecision,
)
from leadpilot.saathi import pipeline
from leadpilot.scripts.demo_constants import DEMO_ACCOUNT_ID, DEMO_TENANT_ID


def _full_autopilot():
    with tenant_session(DEMO_TENANT_ID) as s:
        s.get(Account, DEMO_ACCOUNT_ID).autopilot_level = "FULL"


def test_research_builds_brief_and_angles(seeded):
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_research(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        assert s.get(Account, DEMO_ACCOUNT_ID).phase == "RESEARCHED"
        assert s.scalar(select(BusinessBrief).where(BusinessBrief.account_id == DEMO_ACCOUNT_ID))
        angles = s.scalar(select(func.count(Angle.id)).where(Angle.account_id == DEMO_ACCOUNT_ID))
        assert angles >= 8  # PRD §6.2.1


def test_full_pipeline_to_optimizing(seeded):
    _full_autopilot()

    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_research(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        creative_ids = pipeline.run_creative(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    assert creative_ids

    with tenant_session(DEMO_TENANT_ID) as s:
        # Creatives passed compliance and auto-approved under full autopilot.
        passed = s.scalars(select(Creative).where(Creative.account_id == DEMO_ACCOUNT_ID)).all()
        assert passed and all(c.compliance_status == "PASSED" for c in passed)
        assert s.get(Account, DEMO_ACCOUNT_ID).phase == "CREATIVE_GENERATED"

    with tenant_session(DEMO_TENANT_ID) as s:
        campaign_ids = pipeline.launch_campaigns(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    assert campaign_ids

    with tenant_session(DEMO_TENANT_ID) as s:
        camp = s.scalar(select(Campaign).where(Campaign.account_id == DEMO_ACCOUNT_ID))
        assert camp.status == "ACTIVE" and camp.meta_campaign_id
        adsets = s.scalars(select(AdSet).where(AdSet.account_id == DEMO_ACCOUNT_ID)).all()
        assert {a.role for a in adsets} == {"PROSPECTING", "RETARGETING", "TESTING"}
        assert all(a.meta_adset_id for a in adsets)
        # Budget split sums within the daily budget (65/20/15 across the three tiers).
        assert sum(a.budget_paise for a in adsets) <= 50000
        assert s.scalar(select(func.count(Ad.id)).where(Ad.account_id == DEMO_ACCOUNT_ID)) >= 2
        assert s.get(Account, DEMO_ACCOUNT_ID).phase == "LIVE"

    with tenant_session(DEMO_TENANT_ID) as s:
        decisions = pipeline.run_optimization(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    assert decisions

    with tenant_session(DEMO_TENANT_ID) as s:
        assert s.get(Account, DEMO_ACCOUNT_ID).phase == "OPTIMIZING"
        assert s.scalar(select(func.count(AdInsight.id)).where(AdInsight.account_id == DEMO_ACCOUNT_ID)) >= 1
        recorded = s.scalars(
            select(OptimizationDecision).where(OptimizationDecision.account_id == DEMO_ACCOUNT_ID)
        ).all()
        # All applied decisions stay within bounds (no scale beyond +20%/day handled by clamp).
        assert all(d.applied for d in recorded)
        actions = {d.action for d in recorded}
        assert actions & {"PAUSE", "SCALE", "REQUEST_CREATIVE"}

    with tenant_session(DEMO_TENANT_ID) as s:
        msg = pipeline.run_report(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    assert msg and ("₹" in msg or "Spent" in msg)
    with tenant_session(DEMO_TENANT_ID) as s:
        assert s.scalar(
            select(Notification).where(Notification.account_id == DEMO_ACCOUNT_ID,
                                       Notification.kind == "REPORT")
        )


def test_launch_is_idempotent(seeded):
    _full_autopilot()
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_research(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_creative(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        first = pipeline.launch_campaigns(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        again = pipeline.launch_campaigns(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    assert first == again
    with tenant_session(DEMO_TENANT_ID) as s:
        n = s.scalar(select(func.count(Campaign.id)).where(Campaign.account_id == DEMO_ACCOUNT_ID))
        assert n == 1  # no duplicate campaign
