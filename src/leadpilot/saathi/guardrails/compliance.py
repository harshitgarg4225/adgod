"""Compliance guard (PRD §4.5.2, §14) — Meta Ads policy pre-screen for creatives.

Rules + (later) an LLM classifier. Blocks prohibited claims, guarantees of results,
before/after for restricted verticals, and sensitive-attribute targeting language.
Wired into the Maker→Buyer path in Phase 2; the rule baseline lives here now.
"""
from __future__ import annotations

import re

from leadpilot.core.enums import GuardrailType
from leadpilot.saathi.guardrails.base import GuardrailResult

_PROHIBITED = [
    re.compile(r"\b100%\s*(guarantee|guaranteed|result|cure)\b", re.I),
    re.compile(r"\bguaranteed (results?|income|admission|cure|weight loss)\b", re.I),
    re.compile(r"\bbefore\s*(&|and|/)\s*after\b", re.I),
    re.compile(r"\b(lose|gain)\s+\d+\s*(kg|kgs|pounds)\b", re.I),
    re.compile(r"\b(you are|you're)\s+(overweight|diabetic|depressed)\b", re.I),  # personal attribute
]


def check_creative_copy(*texts: str) -> GuardrailResult:
    blob = " \n ".join(t for t in texts if t)
    for pattern in _PROHIBITED:
        if pattern.search(blob):
            return GuardrailResult.blocked(
                GuardrailType.COMPLIANCE,
                reason=f"prohibited_claim:{pattern.pattern[:40]}",
                severity="WARN",
                action="REJECT_CREATIVE",
            )
    return GuardrailResult.passed(GuardrailType.COMPLIANCE)
