"""Spend guard (PRD §4.5.1) and budget-scaling bound (§6.5).

Deterministic re-validation of any money-moving decision BEFORE it reaches Meta.
The LLM Optimizer cannot exceed these bounds even if it hallucinates a value.
Wired into the Buyer/Optimizer executors in Phase 2/3; defined here so the
contract exists from Phase 1.
"""
from __future__ import annotations

from leadpilot.core.enums import GuardrailType
from leadpilot.saathi.guardrails.base import GuardrailResult

MAX_DAILY_SCALE_PCT = 20  # max +20%/day per ad set (§6.5.1)


def check_daily_spend(*, proposed_daily_paise: int, account_daily_budget_paise: int) -> GuardrailResult:
    if proposed_daily_paise > account_daily_budget_paise:
        return GuardrailResult.blocked(
            GuardrailType.SPEND,
            reason="exceeds_daily_budget",
            severity="ERROR",
            action="HARD_PAUSE",
        )
    return GuardrailResult.passed(GuardrailType.SPEND)


def clamp_scale(*, current_paise: int, proposed_paise: int) -> int:
    """Clamp a budget increase to +MAX_DAILY_SCALE_PCT%/day."""
    ceiling = current_paise + (current_paise * MAX_DAILY_SCALE_PCT) // 100
    return min(proposed_paise, ceiling)


def check_monthly_cap(
    *, month_to_date_paise: int, monthly_cap_paise: int | None
) -> GuardrailResult:
    """Block further spend once the account's month-to-date spend reaches its monthly cap.
    A cap of None/0 means uncapped."""
    if monthly_cap_paise and month_to_date_paise >= monthly_cap_paise:
        return GuardrailResult.blocked(
            GuardrailType.SPEND,
            reason="monthly_cap_reached",
            severity="ERROR",
            action="HARD_PAUSE",
        )
    return GuardrailResult.passed(GuardrailType.SPEND)
