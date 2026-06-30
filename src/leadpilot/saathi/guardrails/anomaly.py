"""Anomaly guard (PRD §4.5.5).

Pause + escalate when an ad set burns non-trivial spend with no leads, or when CPL runs
far over target. The Optimizer records a guardrail_event and pauses; ops + owner are
notified. (Time-window variants — "for N hours" — use the ad_insights history in prod.)
"""
from __future__ import annotations

from leadpilot.core.enums import GuardrailType
from leadpilot.saathi.guardrails.base import GuardrailResult

ZERO_LEAD_MIN_SPEND_PAISE = 15000   # ₹150 spent with 0 leads → anomaly
CPL_ANOMALY_MULTIPLE = 3            # CPL > 3× target → anomaly (beyond the 2× pause rule)


def check_adset_anomaly(*, spend_paise: int, leads: int, cpl_paise: int | None,
                        target_cpql_paise: int) -> GuardrailResult:
    if leads == 0 and spend_paise >= ZERO_LEAD_MIN_SPEND_PAISE:
        return GuardrailResult.blocked(
            GuardrailType.ANOMALY, reason="zero_leads_at_spend", severity="ERROR", action="PAUSE"
        )
    if cpl_paise is not None and cpl_paise > CPL_ANOMALY_MULTIPLE * target_cpql_paise:
        return GuardrailResult.blocked(
            GuardrailType.ANOMALY, reason="cpl_over_3x_target", severity="WARN", action="PAUSE"
        )
    return GuardrailResult.passed(GuardrailType.ANOMALY)
