"""BSP WhatsApp middleware adapter — payload mapping + factory wiring."""
from __future__ import annotations

from leadpilot.common.config import settings
from leadpilot.integrations.whatsapp.base import ReplyButton


def test_bsp_builds_meta_compatible_payloads(monkeypatch):
    monkeypatch.setattr(settings, "bsp_base_url", "https://bsp.example/v1")
    monkeypatch.setattr(settings, "bsp_api_key", "secret")
    from leadpilot.integrations.whatsapp.bsp import BSPWhatsAppAdapter

    a = BSPWhatsAppAdapter()
    text = a.build_payload(to_phone="+919812345678", kind="text", body="Namaste")
    assert text == {
        "messaging_product": "whatsapp", "to": "+919812345678",
        "type": "text", "text": {"body": "Namaste"},
    }

    inter = a.build_payload(
        to_phone="+919812345678", kind="interactive", body="Pick one",
        buttons=[ReplyButton(id="soon", title="A very long button title that overflows")])
    btn = inter["interactive"]["action"]["buttons"][0]["reply"]
    assert inter["type"] == "interactive"
    assert btn["id"] == "soon" and len(btn["title"]) <= 20  # WhatsApp 20-char limit

    # Auth header assembled from scheme + key.
    assert a._headers[settings.bsp_auth_header] == "Bearer secret"


def test_factory_selects_bsp_when_configured(monkeypatch):
    import leadpilot.integrations.whatsapp.factory as f

    monkeypatch.setattr(settings, "mock_whatsapp", False)
    monkeypatch.setattr(settings, "whatsapp_provider", "bsp")
    monkeypatch.setattr(settings, "bsp_base_url", "https://bsp.example/v1")
    monkeypatch.setattr(settings, "bsp_api_key", "secret")
    monkeypatch.setattr(f, "_adapter", None)  # reset singleton
    from leadpilot.integrations.whatsapp.bsp import BSPWhatsAppAdapter

    assert isinstance(f.get_whatsapp_adapter(), BSPWhatsAppAdapter)
    monkeypatch.setattr(f, "_adapter", None)  # don't leak into other tests
