"""Base sub-agent: fixed system prompt + LLM call + agent_run logging.

Sub-agents are scoped and return schema-valid JSON (the `*Output` contracts).
The base records every invocation to `agent_runs` (model/tokens/latency/cost).
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from leadpilot.common.config import settings
from leadpilot.core.enums import AgentName, AgentRunStatus
from leadpilot.core.models import AgentRun
from leadpilot.saathi.providers.llm import LLMBudgetExceeded, LLMResult, get_llm_provider


def _spent_today_paise(session: Session, account_id: UUID) -> int:
    """Sum of LLM cost charged to this account since UTC midnight."""
    day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    total = session.execute(
        select(func.coalesce(func.sum(AgentRun.cost_paise), 0)).where(
            AgentRun.account_id == account_id, AgentRun.created_at >= day_start
        )
    ).scalar_one()
    return int(total or 0)


class BaseAgent:
    name: AgentName
    role: str  # LLM router role: reasoning | creative | closer | reporter
    system_prompt: str = ""
    temperature: float = 0.3

    def __init__(self) -> None:
        self.llm = get_llm_provider()

    def _generate(
        self,
        session: Session,
        *,
        tenant_id: UUID,
        account_id: UUID,
        response_model: type[BaseModel],
        user: str,
        context: dict,
        trigger: str,
        input_ref: str | None = None,
    ) -> BaseModel:
        # Enforce the per-account daily LLM budget BEFORE spending more (PRD §10.4).
        # Skip the query when mocking (cost is always 0) to keep the hot path lean.
        cap = settings.llm_daily_budget_per_account_paise
        if not self.llm.mock and cap > 0 and _spent_today_paise(session, account_id) >= cap:
            raise LLMBudgetExceeded(
                f"Daily LLM budget of {cap} paise reached for account {account_id}"
            )
        result: LLMResult = self.llm.generate(
            role=self.role,
            system=self.system_prompt,
            user=user,
            response_model=response_model,
            context=context,
            temperature=self.temperature,
        )
        session.add(
            AgentRun(
                tenant_id=tenant_id,
                account_id=account_id,
                agent=self.name.value,
                trigger=trigger,
                input_ref=input_ref,
                output={"ok": True},
                status=AgentRunStatus.OK.value,
                model=result.model,
                tokens=result.output_tokens,
                latency_ms=result.latency_ms,
                cost_paise=result.cost_paise,
            )
        )
        return result.parsed
