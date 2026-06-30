from __future__ import annotations

from leadpilot.common.config import settings
from leadpilot.integrations.whatsapp.base import WhatsAppAdapter

_adapter: WhatsAppAdapter | None = None


def get_whatsapp_adapter() -> WhatsAppAdapter:
    global _adapter
    if _adapter is None:
        if settings.mock_whatsapp:
            from leadpilot.integrations.whatsapp.mock import MockWhatsAppAdapter

            _adapter = MockWhatsAppAdapter()
        elif settings.whatsapp_provider == "bsp":  # pragma: no cover
            from leadpilot.integrations.whatsapp.bsp import BSPWhatsAppAdapter

            _adapter = BSPWhatsAppAdapter()
        else:  # pragma: no cover
            from leadpilot.integrations.whatsapp.cloud import CloudWhatsAppAdapter

            _adapter = CloudWhatsAppAdapter()
    return _adapter

