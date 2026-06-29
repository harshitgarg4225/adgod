"""Account phase state machine (PRD §6.0).

The Orchestrator uses this to route triggers to sub-agents. v1 exercises the
inbound (CLOSER) path; the launch/optimize transitions are wired in later phases.
"""
from __future__ import annotations

from leadpilot.core.enums import AccountPhase

# Allowed forward transitions. PAUSED/CHURNED are reachable from most states.
TRANSITIONS: dict[AccountPhase, set[AccountPhase]] = {
    AccountPhase.SIGNED_UP: {AccountPhase.ONBOARDING},
    AccountPhase.ONBOARDING: {AccountPhase.RESEARCHED},
    AccountPhase.RESEARCHED: {AccountPhase.CREATIVE_GENERATED},
    AccountPhase.CREATIVE_GENERATED: {AccountPhase.PENDING_APPROVAL, AccountPhase.APPROVED},
    AccountPhase.PENDING_APPROVAL: {AccountPhase.APPROVED},
    AccountPhase.APPROVED: {AccountPhase.LAUNCHING},
    AccountPhase.LAUNCHING: {AccountPhase.LIVE},
    AccountPhase.LIVE: {AccountPhase.OPTIMIZING, AccountPhase.PAUSED},
    AccountPhase.OPTIMIZING: {AccountPhase.FATIGUE_REFRESH, AccountPhase.LIVE, AccountPhase.PAUSED},
    AccountPhase.FATIGUE_REFRESH: {AccountPhase.OPTIMIZING, AccountPhase.LIVE},
    AccountPhase.PAUSED: {AccountPhase.LIVE, AccountPhase.CHURNED},
}


def can_transition(src: AccountPhase, dst: AccountPhase) -> bool:
    if dst in (AccountPhase.PAUSED, AccountPhase.CHURNED):
        return True
    return dst in TRANSITIONS.get(src, set())
