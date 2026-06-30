"""Scout — market research → Business Brief + Angle Bank (PRD §11.2)."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from leadpilot.core.enums import AgentName
from leadpilot.saathi.agents.base import BaseAgent
from leadpilot.saathi.contracts import ScoutOutput

SYSTEM_PROMPT = """You are Scout, a market-research module for Indian Tier-2 small businesses.
Input: business category, the owner's offer text, optional scraped site/Instagram/GBP text,
and competitor ads (from Meta Ad Library) for the category+city.
Task: produce a Business Brief and an Angle Bank for a lead-generation ad campaign whose
goal is QUALIFIED WhatsApp enquiries (not clicks). Be concrete and local; reflect the
owner's actual offer; identify real customer objections; angles must be distinct and each
tied to a hypothesis about why it will produce qualified leads. >= 8 angles.
Respond ONLY with valid JSON matching the ScoutOutput schema."""


class ScoutAgent(BaseAgent):
    name = AgentName.SCOUT
    role = "reasoning"
    temperature = 0.4

    @property
    def system_prompt(self) -> str:  # type: ignore[override]
        return SYSTEM_PROMPT

    def run(self, session: Session, *, tenant_id: UUID, account_id: UUID, context: dict) -> ScoutOutput:
        user = (
            f"Category: {context.get('category')}\n"
            f"Offer: {context.get('offer')}\n"
            f"City: {context.get('city')}\n"
            f"Competitor ads: {context.get('competitors')}\n"
            "Produce the Business Brief and >= 8 angles."
        )
        out = self._generate(
            session, tenant_id=tenant_id, account_id=account_id,
            response_model=ScoutOutput, user=user, context=context, trigger="research",
        )
        assert isinstance(out, ScoutOutput)
        return out
