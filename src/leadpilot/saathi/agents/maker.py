"""Maker — vernacular ad-creative writer (PRD §11.3)."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from leadpilot.core.enums import AgentName
from leadpilot.saathi.agents.base import BaseAgent
from leadpilot.saathi.contracts import MakerOutput

SYSTEM_PROMPT = """You are Maker, an ad-creative writer for Indian Tier-2 SMBs.
Input: one angle, the brief, retrieved past winners, and the enquiry channel the ad's
button opens (a WhatsApp chat OR a phone call — never assume which). Write ad copy that
earns an enquiry on that channel from a serious local customer. Rules: natural language
(not translated-English); culturally local; clear single offer; the CTA must match the
given channel (e.g. "call now" for calls, "message us" for WhatsApp); comply with Meta
Ads policy (no guarantees of results, no prohibited claims, no sensitive-attribute
targeting, no before/after for restricted verticals).
Provide 3 copy variants + image prompt(s) + optional video script.
Respond ONLY with valid JSON matching the MakerOutput schema."""


class MakerAgent(BaseAgent):
    name = AgentName.MAKER
    role = "creative"
    temperature = 0.8

    @property
    def system_prompt(self) -> str:  # type: ignore[override]
        return SYSTEM_PROMPT

    def run(self, session: Session, *, tenant_id: UUID, account_id: UUID, context: dict) -> MakerOutput:
        user = (
            f"Language: {context.get('language')}\n"
            f"Angle: {context.get('angle')}\n"
            f"Brief: {context.get('brief')}\n"
            f"Past winners: {context.get('winners')}\n"
            f"Enquiry channel (CTA must match): {context.get('cta_channel', 'WhatsApp message')}\n"
            "Write 3 variants + image prompts + optional video script."
        )
        out = self._generate(
            session, tenant_id=tenant_id, account_id=account_id,
            response_model=MakerOutput, user=user, context=context, trigger="creative",
        )
        assert isinstance(out, MakerOutput)
        return out
