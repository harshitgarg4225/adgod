"""WhatsApp channel adapter interface (real interface; mock + cloud implementations).

The Closer and webhook intake depend only on this interface, so MOCK_WHATSAPP swaps
transport without touching agent code (PRD §7.5 channel abstraction).
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field


@dataclass(slots=True)
class InboundMessage:
    wa_message_id: str
    from_phone: str            # the lead's number (e164)
    phone_number_id: str       # the business number id → routes to a tenant
    text: str
    type: str = "text"
    timestamp: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass(slots=True)
class OutboundResult:
    wa_message_id: str
    status: str = "SENT"
    cost_paise: int = 0


@dataclass(slots=True)
class ReplyButton:
    id: str
    title: str


class WhatsAppAdapter:
    def send_text(self, *, phone_number_id: str, to_phone: str, body: str) -> OutboundResult:
        raise NotImplementedError

    def send_interactive(
        self, *, phone_number_id: str, to_phone: str, body: str, buttons: list[ReplyButton]
    ) -> OutboundResult:
        raise NotImplementedError

    def send_template(
        self, *, phone_number_id: str, to_phone: str, template_name: str, language: str,
        params: list[str] | None = None,
    ) -> OutboundResult:
        raise NotImplementedError

    # ── Inbound parsing / verification (shared logic) ──

    @staticmethod
    def parse_inbound(payload: dict) -> list[InboundMessage]:
        """Parse a Meta WhatsApp webhook payload into normalized InboundMessages."""
        out: list[InboundMessage] = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                metadata = value.get("metadata", {})
                phone_number_id = metadata.get("phone_number_id", "")
                for msg in value.get("messages", []):
                    mtype = msg.get("type", "text")
                    if mtype == "text":
                        text = msg.get("text", {}).get("body", "")
                    elif mtype == "interactive":
                        inter = msg.get("interactive", {})
                        text = (
                            inter.get("button_reply", {}).get("title")
                            or inter.get("list_reply", {}).get("title")
                            or ""
                        )
                    else:
                        text = msg.get(mtype, {}).get("caption", "") if isinstance(
                            msg.get(mtype), dict
                        ) else ""
                    out.append(
                        InboundMessage(
                            wa_message_id=msg.get("id", ""),
                            from_phone=msg.get("from", ""),
                            phone_number_id=phone_number_id,
                            text=text,
                            type=mtype,
                            timestamp=msg.get("timestamp"),
                            raw=msg,
                        )
                    )
        return out

    @staticmethod
    def verify_signature(payload_bytes: bytes, signature_header: str | None, app_secret: str) -> bool:
        """Verify Meta's X-Hub-Signature-256 (HMAC-SHA256 of the raw body)."""
        if not signature_header or not app_secret:
            return False
        expected = "sha256=" + hmac.new(
            app_secret.encode(), payload_bytes, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header)
