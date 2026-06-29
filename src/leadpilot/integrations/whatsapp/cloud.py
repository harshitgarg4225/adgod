"""Real WhatsApp Cloud API transport (Graph API).

Used when MOCK_WHATSAPP=false. Inbound parsing / signature verification are inherited
from the base class. Send methods POST to /{phone_number_id}/messages.
Window rules (24h/72h free-entry) are enforced one layer up (the Closer), which
chooses send_text vs send_template based on `free_window_expires_at`.
"""
from __future__ import annotations

import httpx

from leadpilot.common.config import settings
from leadpilot.integrations.whatsapp.base import OutboundResult, ReplyButton, WhatsAppAdapter

_GRAPH = "https://graph.facebook.com"


class CloudWhatsAppAdapter(WhatsAppAdapter):  # pragma: no cover - requires live creds
    def __init__(self) -> None:
        self._token = settings.whatsapp_cloud_api_token
        self._version = settings.meta_graph_api_version
        self._client = httpx.Client(timeout=10.0)

    def _post(self, phone_number_id: str, payload: dict) -> OutboundResult:
        url = f"{_GRAPH}/{self._version}/{phone_number_id}/messages"
        resp = self._client.post(
            url, json=payload, headers={"Authorization": f"Bearer {self._token}"}
        )
        resp.raise_for_status()
        data = resp.json()
        mid = data.get("messages", [{}])[0].get("id", "")
        return OutboundResult(wa_message_id=mid, status="SENT")

    def send_text(self, *, phone_number_id: str, to_phone: str, body: str) -> OutboundResult:
        return self._post(phone_number_id, {
            "messaging_product": "whatsapp", "to": to_phone,
            "type": "text", "text": {"body": body},
        })

    def send_interactive(
        self, *, phone_number_id: str, to_phone: str, body: str, buttons: list[ReplyButton]
    ) -> OutboundResult:
        return self._post(phone_number_id, {
            "messaging_product": "whatsapp", "to": to_phone, "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body},
                "action": {"buttons": [
                    {"type": "reply", "reply": {"id": b.id, "title": b.title[:20]}}
                    for b in buttons
                ]},
            },
        })

    def send_template(
        self, *, phone_number_id: str, to_phone: str, template_name: str, language: str,
        params: list[str] | None = None,
    ) -> OutboundResult:
        components = []
        if params:
            components = [{"type": "body", "parameters": [
                {"type": "text", "text": p} for p in params
            ]}]
        return self._post(phone_number_id, {
            "messaging_product": "whatsapp", "to": to_phone, "type": "template",
            "template": {"name": template_name, "language": {"code": language},
                         "components": components},
        })
