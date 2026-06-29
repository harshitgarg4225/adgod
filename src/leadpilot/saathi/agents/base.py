"""Base sub-agent: fixed system prompt + LLM call + agent_run logging.

Sub-agents are scoped and return schema-valid JSON (the `*Output` contracts).
The base records every invocation to `agent_runs` (model/tokens/latency/cost).
"""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from leadpilot.core.enums import AgentName, AgentRunStatus
from leadpilot.core.models import AgentRun
from leadpilot.saathi.providers.llm import LLMResult, get_llm_provider


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
