"""Closer — the scoped, Meta-compliant WhatsApp qualification agent (PRD §11.6).

Engages every inbound lead in seconds, in their language, runs the qualification
state machine (GREET→…→SCORE), and returns a `CloserOutput`. It is strictly scoped:
a deterministic guard re-validates the reply before it is ever sent.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from leadpilot.core.enums import AgentName
from leadpilot.saathi.agents.base import BaseAgent
from leadpilot.saathi.contracts import CloserOutput

SYSTEM_PROMPT = """You are Closer, a WhatsApp assistant for {business_name} ({category}) in {city}.
Language: {language}. You ONLY do lead qualification for this business. You must NOT act
as a general assistant or answer unrelated questions (Meta policy, Jan 2026).
Collect across the conversation: name, intent, budget/timeline, location. Be warm, brief,
human, local. Use quick-reply buttons when helpful. If the user goes off-topic, steer back
once; if they persist, hand off to the owner. When enough is known, score HOT/WARM/COLD with
reasons. Respond ONLY with valid JSON matching the CloserOutput schema."""


class CloserAgent(BaseAgent):
    name = AgentName.CLOSER
    role = "closer"
    temperature = 0.4

    @property
    def system_prompt(self) -> str:  # type: ignore[override]
        return SYSTEM_PROMPT

    def run(
        self,
        session: Session,
        *,
        tenant_id: UUID,
        account_id: UUID,
        state: str,
        captured: dict,
        user_text: str,
        business_name: str,
        category: str,
        city: str,
        language: str,
        junk_turns: int = 0,
        input_ref: str | None = None,
    ) -> CloserOutput:
        context = {
            "state": state,
            "captured": captured,
            "user_text": user_text,
            "business_name": business_name,
            "category": category,
            "city": city,
            "language": language,
            "junk_turns": junk_turns,
        }
        user = (
            f"Current state: {state}\n"
            f"Known so far: {captured}\n"
            f"Latest message from lead: {user_text!r}\n"
            "Produce the next qualification turn."
        )
        out = self._generate(
            session,
            tenant_id=tenant_id,
            account_id=account_id,
            response_model=CloserOutput,
            user=user,
            context=context,
            trigger="inbound_whatsapp",
            input_ref=input_ref,
        )
        assert isinstance(out, CloserOutput)
        return out
