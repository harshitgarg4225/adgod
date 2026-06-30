"""Buyer — LLM planner; the deterministic executor lives in the pipeline (PRD §11.4)."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from leadpilot.core.enums import AgentName
from leadpilot.saathi.agents.base import BaseAgent
from leadpilot.saathi.contracts import BuyerOutput

SYSTEM_PROMPT = """You are Buyer, a Meta media-buying planner for Indian Tier-2 SMBs.
Select campaign structure and targeting from the brief. Default structure: Prospecting
(broad + interest), Lookalike (if a seed exists), and an isolated Testing ad set for new
creatives. Budget split default 70/20/10 (prospecting/lookalike/testing) within the
owner's daily budget. Goal: qualified WhatsApp enquiries (CTWA). Never exceed the daily
budget. Respond ONLY with valid JSON matching the BuyerOutput schema."""


class BuyerAgent(BaseAgent):
    name = AgentName.BUYER
    role = "reasoning"
    temperature = 0.3

    @property
    def system_prompt(self) -> str:  # type: ignore[override]
        return SYSTEM_PROMPT

    def run(self, session: Session, *, tenant_id: UUID, account_id: UUID, context: dict) -> BuyerOutput:
        user = (
            f"Brief: {context.get('brief')}\n"
            f"City: {context.get('city')} radius {context.get('radius_km')}km\n"
            f"Daily budget (paise): {context.get('daily_budget_paise')}\n"
            f"Creative ids: {context.get('creative_ids')}\n"
            "Plan campaigns, ad sets (with 70/20/10 split), and ads."
        )
        out = self._generate(
            session, tenant_id=tenant_id, account_id=account_id,
            response_model=BuyerOutput, user=user, context=context, trigger="launch",
        )
        assert isinstance(out, BuyerOutput)
        return out
