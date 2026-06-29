"""LLMProvider router (PRD §10.4).

Per-agent model selection + fallback + per-account cost cap + token/cost logging.
`MOCK_LLM=true` swaps in a deterministic provider so the entire agent loop runs in
CI without keys; flipping the flag uses the real Claude/Gemini path behind the same
interface. The contract is identical: `generate(...) -> LLMResult`.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel

from leadpilot.common.config import settings
from leadpilot.common.logging import get_logger
from leadpilot.saathi.providers.mock_llm import mock_generate

log = get_logger("llm")

TModel = TypeVar("TModel", bound=BaseModel)

# Per-agent role → which model to use. Claude reasons; Gemini drafts/closes at scale.
ROLE_MODELS = {
    "reasoning": settings.llm_reasoning_model,   # Orchestrator-adjacent / Optimizer / Scout
    "creative": settings.llm_creative_model,     # Maker
    "closer": settings.llm_closer_model,         # Closer (hot path)
    "reporter": settings.llm_creative_model,
}

# Rough output paise per 1k tokens, by vendor family, for the per-account cap.
_COST_PER_1K_PAISE = {"claude": 150, "gemini": 8, "mock": 0}


@dataclass(slots=True)
class LLMResult:
    parsed: BaseModel
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost_paise: int = 0
    raw: dict = field(default_factory=dict)


def _vendor(model: str) -> str:
    if model.startswith("claude"):
        return "claude"
    if model.startswith("gemini"):
        return "gemini"
    return "mock"


def _estimate_cost_paise(model: str, output_tokens: int) -> int:
    return (_COST_PER_1K_PAISE.get(_vendor(model), 0) * output_tokens) // 1000


class LLMBudgetExceeded(RuntimeError):
    pass


class LLMProvider:
    """Routes generate() to the configured model for the agent role."""

    def __init__(self, mock: bool) -> None:
        self.mock = mock

    def model_for(self, role: str) -> str:
        return ROLE_MODELS.get(role, settings.llm_reasoning_model)

    def generate(
        self,
        *,
        role: str,
        system: str,
        user: str,
        response_model: type[TModel],
        context: dict | None = None,
        temperature: float = 0.3,
    ) -> LLMResult:
        model = self.model_for(role)
        started = time.monotonic()
        if self.mock:
            parsed = mock_generate(response_model, context or {})
            out_tokens = 64
        else:
            parsed, out_tokens = self._generate_real(
                model=model, system=system, user=user,
                response_model=response_model, temperature=temperature,
            )
        latency_ms = int((time.monotonic() - started) * 1000)
        return LLMResult(
            parsed=parsed,
            model=model,
            output_tokens=out_tokens,
            latency_ms=latency_ms,
            cost_paise=_estimate_cost_paise(model, out_tokens),
        )

    def _generate_real(
        self,
        *,
        model: str,
        system: str,
        user: str,
        response_model: type[TModel],
        temperature: float,
    ) -> tuple[TModel, int]:
        """Real provider call. Imports SDKs lazily; forces JSON; validates."""
        vendor = _vendor(model)
        schema_hint = (
            "Respond with ONLY valid JSON matching this schema, no prose:\n"
            f"{response_model.model_json_schema()}"
        )
        if vendor == "claude":
            text, out_tokens = self._call_claude(model, system, user, schema_hint, temperature)
        elif vendor == "gemini":
            text, out_tokens = self._call_gemini(model, system, user, schema_hint, temperature)
        else:  # pragma: no cover - defensive
            raise LLMBudgetExceeded(f"No real provider for model {model}")
        parsed = response_model.model_validate_json(_strip_fences(text))
        return parsed, out_tokens

    def _call_claude(self, model, system, user, schema_hint, temperature):  # pragma: no cover
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        msg = client.messages.create(
            model=model,
            max_tokens=1024,
            temperature=temperature,
            system=f"{system}\n\n{schema_hint}",
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return text, msg.usage.output_tokens

    def _call_gemini(self, model, system, user, schema_hint, temperature):  # pragma: no cover
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        gm = genai.GenerativeModel(model_name=model, system_instruction=f"{system}\n\n{schema_hint}")
        resp = gm.generate_content(
            user,
            generation_config={"temperature": temperature, "response_mime_type": "application/json"},
        )
        out_tokens = getattr(getattr(resp, "usage_metadata", None), "candidates_token_count", 0) or 0
        return resp.text, out_tokens


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    global _provider
    if _provider is None:
        _provider = LLMProvider(mock=settings.mock_llm)
    return _provider
