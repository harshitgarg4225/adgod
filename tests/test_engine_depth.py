"""Engine depth: memory retrieval, anomaly guard, approval gate + autopilot,
fatigue rotation, k-anon priors (PRD §4.4, §4.5, §6.5.2)."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from leadpilot.core.db import tenant_session
from leadpilot.core.models import Account, Ad, Approval, Creative
from leadpilot.saathi import pipeline
from leadpilot.saathi.guardrails.anomaly import check_adset_anomaly
from leadpilot.saathi.memory import retrieve_winning_creatives, vertical_city_priors
from leadpilot.scripts.demo_constants import (
    DEMO_ACCOUNT_ID,
    DEMO_CATEGORY,
    DEMO_CITY,
    DEMO_TENANT_ID,
)


def _autopilot(level: str):
    with tenant_session(DEMO_TENANT_ID) as s:
        s.get(Account, DEMO_ACCOUNT_ID).autopilot_level = level


def _research_and_creative():
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_research(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_creative(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)


def test_creatives_are_embedded_and_retrievable(seeded):
    _autopilot("FULL")
    _research_and_creative()
    with tenant_session(DEMO_TENANT_ID) as s:
        # Every compliant creative carries a semantic embedding.
        embedded = s.scalar(
            select(func.count(Creative.id)).where(
                Creative.account_id == DEMO_ACCOUNT_ID, Creative.embedding.isnot(None))
        )
        assert embedded >= 1
        hits = retrieve_winning_creatives(
            s, account_id=DEMO_ACCOUNT_ID, query_text="NEET coaching offer", k=3)
        assert hits and all(h.embedding is not None for h in hits)


def test_anomaly_guard_thresholds():
    # Zero leads at non-trivial spend → pause.
    r = check_adset_anomaly(spend_paise=20000, leads=0, cpl_paise=None, target_cpql_paise=20000)
    assert not r.ok and r.action_taken == "PAUSE"
    # CPL far over target → pause.
    r2 = check_adset_anomaly(spend_paise=50000, leads=1, cpl_paise=80000, target_cpql_paise=20000)
    assert not r2.ok
    # Healthy → pass.
    assert check_adset_anomaly(spend_paise=20000, leads=5, cpl_paise=4000,
                               target_cpql_paise=20000).ok


def test_approval_gate_blocks_launch_until_approved(seeded):
    _autopilot("ASSISTED")
    _research_and_creative()
    with tenant_session(DEMO_TENANT_ID) as s:
        assert s.get(Account, DEMO_ACCOUNT_ID).phase == "PENDING_APPROVAL"
        approval = s.scalar(select(Approval).where(Approval.account_id == DEMO_ACCOUNT_ID))
        assert approval and approval.status == "PENDING"

    # Launch must refuse while creatives are unapproved.
    with pytest.raises(ValueError):
        with tenant_session(DEMO_TENANT_ID) as s:
            pipeline.launch_campaigns(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)

    # Owner approves the batch → creatives become launch-ready.
    with tenant_session(DEMO_TENANT_ID) as s:
        for c in s.scalars(select(Creative).where(Creative.account_id == DEMO_ACCOUNT_ID)).all():
            if c.compliance_status == "PASSED":
                c.approval_status = "APPROVED_FOR_LAUNCH"
    with tenant_session(DEMO_TENANT_ID) as s:
        assert pipeline.launch_campaigns(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)


def test_trust_threshold_upgrades_autopilot(seeded):
    # Cross the trust threshold on first launch (default threshold = 2 → set 1 to trip it).
    from leadpilot.common.config import settings

    settings.default_trust_threshold = 1
    _autopilot("ASSISTED")
    _research_and_creative()
    with tenant_session(DEMO_TENANT_ID) as s:
        for c in s.scalars(select(Creative).where(Creative.account_id == DEMO_ACCOUNT_ID)).all():
            c.approval_status = "APPROVED_FOR_LAUNCH"
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.launch_campaigns(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        assert s.get(Account, DEMO_ACCOUNT_ID).autopilot_level == "FULL"
    settings.default_trust_threshold = 2


def test_fatigue_rotation_adds_ad_to_testing(seeded):
    _autopilot("FULL")
    _research_and_creative()
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.launch_campaigns(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        before = s.scalar(select(func.count(Ad.id)).where(Ad.account_id == DEMO_ACCOUNT_ID))
    with tenant_session(DEMO_TENANT_ID) as s:
        new_id = pipeline.rotate_fresh_creative(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    assert new_id is not None
    with tenant_session(DEMO_TENANT_ID) as s:
        after = s.scalar(select(func.count(Ad.id)).where(Ad.account_id == DEMO_ACCOUNT_ID))
    assert after == before + 1


def test_cross_account_priors_respect_k_anonymity(seeded):
    # A single demo account is far below k=20 → no prior is exposed.
    prior = vertical_city_priors(DEMO_CATEGORY, DEMO_CITY)
    assert prior["available"] is False
