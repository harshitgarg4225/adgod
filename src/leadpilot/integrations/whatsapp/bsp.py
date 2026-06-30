"""BSP (aggregator) WhatsApp transport — the fastest go-live path.

A BSP is a Meta Tech Provider, so onboarding a business number takes hours/days via
their Embedded Signup instead of weeks of direct WABA review. Because the Closer and
webhook-intake depend only on `WhatsAppAdapter`, swapping Cloud-API-direct for a BSP is
a config change (WHATSAPP_PROVIDER=bsp), not a code change.

This adapter targets the common case: a BSP that exposes a Meta-compatible REST send
endpoint and forwards inbound in Meta's webhook JSON (so the inherited parse_inbound
works unchanged). Per-provider mapping notes live in docs/WHATSAPP_PROVIDERS.md.
"""
from __future__ import annotations

import itertools

import httpx

from leadpilot.common.config import settings
from leadpilot.common.logging import get_logger
from leadpilot.integrations.whatsapp.base import OutboundResult, ReplyButton, WhatsAppAdapter

log = get_logger("whatsapp.bsp")
_counter = itertools.count(1)


class BSPWhatsAppAdapter(WhatsAppAdapter):  # pragma: no cover - exercised via factory test
    def __init__(self) -> None:
        if not settings.bsp_base_url:
            raise ValueError("BSP_BASE_URL is required for whatsapp_provider=bsp")
        self._base = settings.bsp_base_url.rstrip("/")
        self._path = settings.bsp_send_path
        self._headers = {
            settings.bsp_auth_header: (
                f"{settings.bsp_auth_scheme} {settings.bsp_api_key}".strip()
                if settings.bsp_auth_scheme else (settings.bsp_api_key or "")
            )
        }
        self._client = httpx.Client(timeout=10.0)

    def build_payload(self, *, to_phone: str, kind: str, body: str,
                      buttons: list[ReplyButton] | None = None) -> dict:
        """Meta-compatible message body. Many Indian BSPs accept this verbatim."""
        if kind == "interactive" and buttons:
            return {
                "messaging_product": "whatsapp", "to": to_phone, "type": "interactive",
                "interactive": {"type": "button", "body": {"text": body},
                                "action": {"buttons": [
                                    {"type": "reply", "reply": {"id": b.id, "title": b.title[:20]}}
                                    for b in buttons]}},
            }
        return {"messaging_product": "whatsapp", "to": to_phone, "type": "text",
                "text": {"body": body}}

    def _send(self, payload: dict) -> OutboundResult:
        resp = self._client.post(f"{self._base}{self._path}", json=payload, headers=self._headers)
        resp.raise_for_status()
        data = resp.json() if resp.content else {}
        mid = (data.get("messages", [{}])[0].get("id")
               or data.get("message_id") or f"bsp.{next(_counter):08d}")
        return OutboundResult(wa_message_id=mid, status="SENT")

    def send_text(self, *, phone_number_id: str, to_phone: str, body: str) -> OutboundResult:
        return self._send(self.build_payload(to_phone=to_phone, kind="text", body=body))

    def send_interactive(self, *, phone_number_id, to_phone, body, buttons) -> OutboundResult:
        return self._send(self.build_payload(to_phone=to_phone, kind="interactive",
                                             body=body, buttons=buttons))

    def send_template(self, *, phone_number_id, to_phone, template_name, language,
                      params=None) -> OutboundResult:
        components = ([{"type": "body", "parameters": [{"type": "text", "text": p}
                                                       for p in params]}] if params else [])
        return self._send({
            "messaging_product": "whatsapp", "to": to_phone, "type": "template",
            "template": {"name": template_name, "language": {"code": language},
                         "components": components},
        })
