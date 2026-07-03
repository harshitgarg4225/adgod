"""Structured logging with PII redaction (DPDP §14).

Phone numbers, emails, message bodies, and tokens are redacted before anything
reaches logs or semantic memory. `redact_text` is also used to build the
PII-scrubbed `messages.redacted_body` stored for memory.
"""
from __future__ import annotations

import logging
import re
import sys

import structlog

from leadpilot.common.config import settings

# E.164-ish phone, emails, and long bearer-ish tokens.
_PHONE_RE = re.compile(r"\+?\d[\d\s\-]{7,}\d")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Token shapes that must never reach logs even inside free text: Meta tokens (EAA…),
# explicit Bearer credentials, and very long continuous secrets (UUIDs are 36 chars with
# dashes, so the 60+ rule can't eat entity ids).
_TOKEN_RE = re.compile(r"EAA[A-Za-z0-9]{16,}|(?i:bearer)\s+\S{16,}|[A-Za-z0-9_\-]{60,}")
# Keys whose values are phone numbers → mask to last 4.
_PHONE_KEYS = {"phone", "wa_phone", "to", "from", "from_phone", "display_phone"}
# Keys whose values are secrets → drop entirely.
_SECRET_KEYS = {
    "token", "access", "refresh", "password", "secret", "authorization",
    "system_user_token", "system_user_token_enc", "code", "code_hash",
}
# Keys whose values are free text that may carry PII → scrub emails/phones inline.
_FREETEXT_KEYS = {"body", "text", "message", "reply", "detail", "note", "intent",
                  "offer", "primary_text", "headline", "description", "error"}


def redact_text(value: str) -> str:
    """Redact PII and credential-shaped strings from free text (error slices included —
    a Graph error message must never carry a token into the logs)."""
    if not value:
        return value
    value = _TOKEN_RE.sub("[token]", value)
    value = _EMAIL_RE.sub("[email]", value)
    value = _PHONE_RE.sub("[phone]", value)
    return value


def mask_phone(phone: str | None) -> str:
    """Keep last 4 digits for support correlation, redact the rest."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if len(digits) <= 4:
        return "****"
    return f"****{digits[-4:]}"


def _redact_processor(_logger, _name, event_dict):
    for key in list(event_dict.keys()):
        val = event_dict[key]
        if not isinstance(val, str):
            continue
        k = key.lower()
        if k in _PHONE_KEYS:
            event_dict[key] = mask_phone(val)
        elif k in _SECRET_KEYS:
            event_dict[key] = "[redacted]"
        elif k in _FREETEXT_KEYS:
            event_dict[key] = redact_text(val)
        # Other keys (timestamps, ids, levels, event names) are left intact.
    return event_dict


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact_processor,
            structlog.processors.JSONRenderer()
            if settings.is_production
            else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
