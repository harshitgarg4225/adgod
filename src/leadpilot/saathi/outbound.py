"""Proactive outbound WhatsApp sends via the transactional outbox.

Used by owner in-app replies and the re-engagement sweep. Every send persists an OUT
Message (QUEUED) and enqueues an idempotent `whatsapp_send` effect — the same exactly-once
path the Closer uses. Free-form text is only valid inside the 24h service window; outside
it, Meta requires an approved template, so callers pass `kind="template"`.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from leadpilot.common.logging import redact_text
from leadpilot.core.enums import MessageDirection, MessageStatus, MessageType
from leadpilot.core.models import Message
from leadpilot.core.outbox import enqueue_effect


def enqueue_send(
    session: Session,
    *,
    tenant_id: UUID,
    account_id: UUID,
    conversation_id: UUID,
    phone_number_id: str,
    to_phone: str,
    step_id: str,
    kind: str = "text",
    body: str | None = None,
    template_name: str | None = None,
    language: str = "hi",
    params: list[str] | None = None,
) -> Message:
    """Persist an outbound message and enqueue its send. `step_id` is the idempotency key —
    reusing it (e.g. per re-engagement round) makes retries/replays a no-op."""
    out_msg = Message(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        direction=MessageDirection.OUT.value,
        type=MessageType.TEMPLATE.value if kind == "template" else MessageType.TEXT.value,
        body=body if kind != "template" else None,
        template_name=template_name,
        redacted_body=redact_text(body) if body else None,
        status=MessageStatus.QUEUED.value,
    )
    session.add(out_msg)
    session.flush()

    payload: dict = {
        "message_id": str(out_msg.id),
        "phone_number_id": phone_number_id,
        "to_phone": to_phone,
        "kind": kind,
    }
    if kind == "template":
        payload.update(template_name=template_name, language=language, params=params or [])
    else:
        payload["body"] = body

    enqueue_effect(
        session,
        tenant_id=tenant_id,
        account_id=account_id,
        step_id=step_id,
        effect_type="whatsapp_send",
        payload=payload,
    )
    return out_msg
