"""Scoped-conversation guard (PRD §4.5.3, §6.6.3).

Meta prohibits general-purpose AI chatbots on WhatsApp (policy effective Jan 2026).
The Closer may ONLY do lead qualification. This deterministic guard blocks any reply
that escapes that scope — long essays, general assistance, code, external links, or an
invalid next state — before the message is ever sent.
"""
from __future__ import annotations

import re

from leadpilot.core.enums import ConversationState, GuardrailType
from leadpilot.saathi.contracts import CloserOutput
from leadpilot.saathi.guardrails.base import GuardrailResult

MAX_REPLY_CHARS = 600

# Patterns that signal the model has left the qualification task.
_OUT_OF_SCOPE = [
    re.compile(r"```"),                                  # code blocks
    re.compile(r"\bas an? (ai|language model)\b", re.I),
    re.compile(r"\bhere'?s? (a|the) (recipe|poem|essay|code|script)\b", re.I),
    re.compile(r"https?://(?!wa\.me|api\.whatsapp)", re.I),  # external links (allow wa.me)
    re.compile(r"\b(weather|cricket score|movie|song lyrics|homework)\b", re.I),
]

_ALLOWED_STATES = {s.value for s in ConversationState}


def check_closer_scope(output: CloserOutput) -> GuardrailResult:
    body = output.reply.body or ""

    if output.next_state not in _ALLOWED_STATES:
        return GuardrailResult.blocked(
            GuardrailType.SCOPE, reason=f"invalid_next_state:{output.next_state}", severity="ERROR"
        )

    if len(body) > MAX_REPLY_CHARS:
        return GuardrailResult.blocked(
            GuardrailType.SCOPE, reason="reply_too_long", severity="WARN"
        )

    for pattern in _OUT_OF_SCOPE:
        if pattern.search(body):
            return GuardrailResult.blocked(
                GuardrailType.SCOPE,
                reason=f"out_of_scope_pattern:{pattern.pattern[:40]}",
                severity="WARN",
            )

    if output.reply.buttons and len(output.reply.buttons) > 3:
        # WhatsApp interactive reply-button limit; keep replies well-formed.
        return GuardrailResult.blocked(
            GuardrailType.SCOPE, reason="too_many_buttons", severity="WARN"
        )

    return GuardrailResult.passed(GuardrailType.SCOPE)
