"""Guardrail Engine — the synchronous gate (PRD §4.5).

Every side-effecting action passes through here before execution. Blocked actions
are persisted to `guardrail_events` and never applied.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from leadpilot.common.logging import get_logger
from leadpilot.core.models import GuardrailEvent
from leadpilot.saathi.contracts import CloserOutput
from leadpilot.saathi.guardrails.base import GuardrailResult
from leadpilot.saathi.guardrails.scope import check_closer_scope

log = get_logger("guardrail")


class GuardrailEngine:
    def __init__(self, session: Session, *, tenant_id: UUID, account_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.account_id = account_id

    def record(self, result: GuardrailResult) -> GuardrailResult:
        """Persist non-passing (or notable) guardrail outcomes."""
        if not result.ok or result.severity in ("WARN", "ERROR"):
            self.session.add(
                GuardrailEvent(
                    tenant_id=self.tenant_id,
                    account_id=self.account_id,
                    type=result.type.value,
                    severity=result.severity,
                    detail=result.detail,
                    action_taken=result.action_taken,
                )
            )
            log.info("guardrail", type=result.type.value, ok=result.ok,
                     severity=result.severity, action=result.action_taken)
        return result

    def closer_scope(self, output: CloserOutput) -> GuardrailResult:
        """Check + record the Closer scope guard. Returns the result (ok=False blocks send)."""
        return self.record(check_closer_scope(output))
