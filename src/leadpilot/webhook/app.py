"""webhook-intake service (PRD §7.2, §9.4, §10.2).

Public, signature-verified webhooks for WhatsApp / Meta leadgen / Razorpay. The hot
path: verify signature → parse → resolve tenant via wa_routes → idempotent persist to
inbound_events (on wa_message_id) → enqueue the closer job → 200 fast. It NEVER calls
Meta/LLM inline, protecting the 99.9% lead-path SLO.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from leadpilot.common.config import settings
from leadpilot.common.logging import configure_logging, get_logger
from leadpilot.core.routing import record_inbound_event, resolve_wa_route
from leadpilot.integrations.whatsapp.base import WhatsAppAdapter
from leadpilot.worker.dispatch import enqueue_inbound

configure_logging()
log = get_logger("webhook")

app = FastAPI(title="LeadPilot webhook-intake", version="0.1.0")

# Indirection so tests can assert enqueue behavior without a live broker.
enqueue_closer = enqueue_inbound


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "webhook-intake"}


def _signature_ok(body: bytes, signature: str | None) -> bool:
    secret = settings.whatsapp_app_secret
    if not secret:
        # Dev convenience only — never allow unsigned webhooks in production.
        return not settings.is_production
    return WhatsAppAdapter.verify_signature(body, signature, secret)


@app.get("/webhooks/whatsapp")
def whatsapp_verify(request: Request) -> Response:
    """Meta webhook verification handshake."""
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == settings.whatsapp_webhook_verify_token
    ):
        return PlainTextResponse(params.get("hub.challenge", ""))
    return PlainTextResponse("forbidden", status_code=403)


@app.post("/webhooks/whatsapp")
async def whatsapp_inbound(request: Request) -> JSONResponse:
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not _signature_ok(body, signature):
        log.warning("wa_signature_invalid")
        return JSONResponse({"error": "invalid signature"}, status_code=403)

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)

    messages = WhatsAppAdapter.parse_inbound(payload)
    accepted = 0
    for msg in messages:
        if not msg.wa_message_id or not msg.phone_number_id:
            continue
        route = resolve_wa_route(msg.phone_number_id)
        if route is None:
            log.warning("wa_unrouted", phone_number_id=msg.phone_number_id)
            continue
        tenant_id, account_id = route
        event_id = record_inbound_event(
            provider="whatsapp",
            external_id=msg.wa_message_id,
            tenant_id=tenant_id,
            account_id=account_id,
            payload={"message": asdict(msg)},
        )
        if event_id is None:
            # Duplicate delivery — already recorded; do not re-enqueue.
            continue
        enqueue_closer(str(event_id))
        accepted += 1

    # Always 200 so Meta does not retry storms; we've durably recorded what we accepted.
    return JSONResponse({"accepted": accepted}, status_code=200)


@app.post("/webhooks/meta/leadgen")
async def meta_leadgen(request: Request) -> JSONResponse:
    # Phase 2: verify signature, fetch leadgen field data, persist Lead via outbox.
    return JSONResponse({"status": "accepted"}, status_code=200)


@app.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request) -> JSONResponse:
    # Phase 2: verify Razorpay signature; handle subscription.charged / payment.failed.
    return JSONResponse({"status": "accepted"}, status_code=200)
