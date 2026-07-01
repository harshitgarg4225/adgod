"""Outbox effect handlers. Each is idempotent (read-modify-write), so a redelivery
never produces a duplicate side effect — the core of exactly-once *effect*.

This is also the seam where Temporal Cloud could later replace the home-grown
runner without changing handlers.
"""
from __future__ import annotations

from uuid import UUID

from leadpilot.common.logging import get_logger
from leadpilot.core.db import tenant_session
from leadpilot.core.enums import MessageStatus
from leadpilot.core.models import Message
from leadpilot.integrations.whatsapp import get_whatsapp_adapter
from leadpilot.integrations.whatsapp.base import ReplyButton

log = get_logger("effects")


def handle_whatsapp_send(entry: dict) -> dict:
    """Send a queued WhatsApp reply. Idempotent on the message's SENT status."""
    payload = entry["payload"]
    tenant_id = entry["tenant_id"]
    message_id = UUID(str(payload["message_id"]))

    with tenant_session(tenant_id) as session:
        msg = session.get(Message, message_id)
        if msg is None:
            return {"skipped": "message_missing"}
        if msg.status == MessageStatus.SENT.value:
            # Already sent on a prior delivery — no-op (exactly-once effect).
            return {"idempotent": True, "wa_message_id": msg.wa_message_id}

        adapter = get_whatsapp_adapter()
        phone_number_id = payload["phone_number_id"]
        to_phone = payload["to_phone"]
        kind = payload.get("kind")
        if kind == "template":
            # Proactive / out-of-window send — Meta only allows approved templates here.
            result = adapter.send_template(
                phone_number_id=phone_number_id,
                to_phone=to_phone,
                template_name=payload["template_name"],
                language=payload.get("language", "hi"),
                params=payload.get("params") or [],
            )
        elif kind == "interactive" and payload.get("buttons"):
            result = adapter.send_interactive(
                phone_number_id=phone_number_id,
                to_phone=to_phone,
                body=payload["body"],
                buttons=[ReplyButton(id=b["id"], title=b["title"]) for b in payload["buttons"]],
            )
        else:
            result = adapter.send_text(
                phone_number_id=phone_number_id, to_phone=to_phone, body=payload["body"]
            )

        msg.wa_message_id = result.wa_message_id
        msg.status = MessageStatus.SENT.value
        msg.cost_paise = result.cost_paise

    log.info("effect_whatsapp_send", message_id=str(message_id))
    return {"wa_message_id": result.wa_message_id}


EFFECT_HANDLERS = {
    "whatsapp_send": handle_whatsapp_send,
}
