"""Mock WhatsApp transport — records sends in-memory, returns deterministic ids.

Used when MOCK_WHATSAPP=true. The signature path and inbound parsing come from the
base class, so the only thing mocked is the outbound HTTP transport.
"""
from __future__ import annotations

import itertools

from leadpilot.common.logging import get_logger
from leadpilot.integrations.whatsapp.base import OutboundResult, ReplyButton, WhatsAppAdapter

log = get_logger("whatsapp.mock")
_counter = itertools.count(1)

# Last-sent registry for tests/inspection (per process).
SENT: list[dict] = []


class MockWhatsAppAdapter(WhatsAppAdapter):
    def _record(self, kind: str, to_phone: str, body: str, **extra) -> OutboundResult:
        mid = f"wamid.MOCK{next(_counter):08d}"
        SENT.append({"id": mid, "kind": kind, "to": to_phone, "body": body, **extra})
        log.info("wa_send", kind=kind, to=to_phone, mid=mid)
        return OutboundResult(wa_message_id=mid, status="SENT", cost_paise=0)

    def send_text(self, *, phone_number_id: str, to_phone: str, body: str) -> OutboundResult:
        return self._record("text", to_phone, body)

    def send_interactive(
        self, *, phone_number_id: str, to_phone: str, body: str, buttons: list[ReplyButton]
    ) -> OutboundResult:
        return self._record("interactive", to_phone, body,
                            buttons=[b.title for b in buttons])

    def send_template(
        self, *, phone_number_id: str, to_phone: str, template_name: str, language: str,
        params: list[str] | None = None,
    ) -> OutboundResult:
        return self._record("template", to_phone, template_name, language=language)
