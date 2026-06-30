"""Reporter — plain-language vernacular daily/weekly summary (PRD §11.7)."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from leadpilot.core.enums import AgentName
from leadpilot.saathi.agents.base import BaseAgent
from leadpilot.saathi.contracts import ReporterOutput

SYSTEM_PROMPT = """You are Reporter. Input: today's metrics and the decisions Saathi made.
Write a short, friendly WhatsApp update in the owner's language that a non-technical shop
owner will understand. Include: amount spent, enquiries, qualified leads, cost per qualified
lead, bookings, and what Saathi did. No jargon. <= 6 short lines.
Respond ONLY with valid JSON matching the ReporterOutput schema."""


class ReporterAgent(BaseAgent):
    name = AgentName.REPORTER
    role = "reporter"
    temperature = 0.5

    @property
    def system_prompt(self) -> str:  # type: ignore[override]
        return SYSTEM_PROMPT

    def run(self, session: Session, *, tenant_id: UUID, account_id: UUID, context: dict) -> ReporterOutput:
        out = self._generate(
            session, tenant_id=tenant_id, account_id=account_id,
            response_model=ReporterOutput, user=f"Metrics: {context}", context=context,
            trigger="report",
        )
        assert isinstance(out, ReporterOutput)
        return out
