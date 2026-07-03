"""webhook-intake service (PRD §7.2, §9.4, §10.2).

Public, signature-verified webhooks for WhatsApp / Meta leadgen / Razorpay. The hot
path: verify signature → parse → resolve tenant via wa_routes → idempotent persist to
inbound_events (on wa_message_id) → enqueue the closer job → 200 fast. It NEVER calls
Meta/LLM inline, protecting the 99.9% lead-path SLO.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.concurrency import run_in_threadpool

from leadpilot.common.config import settings
from leadpilot.common.logging import configure_logging, get_logger
from leadpilot.common.observability import init_observability, readiness
from leadpilot.common.security_headers import SecurityHeadersMiddleware
from leadpilot.core.routing import record_inbound_event, resolve_wa_route
from leadpilot.core.webhooks import apply_razorpay_event, capture_leadgen
from leadpilot.integrations.razorpay.base import RazorpayAdapter
from leadpilot.integrations.whatsapp.base import WhatsAppAdapter
from leadpilot.worker.dispatch import enqueue_inbound

configure_logging()
init_observability("webhook-intake")
log = get_logger("webhook")

app = FastAPI(title="Salmor webhook-intake", version="0.1.0")
app.add_middleware(SecurityHeadersMiddleware)

# Indirection so tests can assert enqueue behavior without a live broker.
enqueue_closer = enqueue_inbound


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "webhook-intake"}


@app.get("/ready")
def ready() -> JSONResponse:
    r = readiness()
    return JSONResponse(r, status_code=200 if r["ready"] else 503)


def _meta_signature_ok(body: bytes, signature: str | None) -> bool:
    secret = settings.meta_app_secret or settings.whatsapp_app_secret
    if not secret:
        # Fail-closed unless this is an explicitly recognised local/dev/test environment.
        return not settings.requires_secure_webhooks
    return WhatsAppAdapter.verify_signature(body, signature, secret)


def _extract_lead_fields(value: dict) -> tuple[str | None, str | None]:
    name = phone = None
    for f in value.get("field_data", []):
        key = (f.get("name") or "").lower()
        val = (f.get("values") or [None])[0]
        if key in ("full_name", "name"):
            name = val
        elif key in ("phone_number", "phone"):
            phone = val
    return name, phone


def _signature_ok(body: bytes, signature: str | None) -> bool:
    secret = settings.whatsapp_app_secret
    if not secret:
        # Dev convenience only — fail-closed for any non-dev/test environment so a
        # mis-set ENVIRONMENT string can't silently accept forged, unsigned webhooks.
        return not settings.requires_secure_webhooks
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

    # The per-message work is synchronous DB + broker I/O; run it in a threadpool so it
    # never blocks the async event loop (which serves every other inbound webhook).
    accepted = await run_in_threadpool(_process_wa_messages, payload)
    # Always 200 so Meta does not retry storms; we've durably recorded what we accepted.
    return JSONResponse({"accepted": accepted}, status_code=200)


def _process_wa_messages(payload: dict) -> int:
    accepted = 0
    for msg in WhatsAppAdapter.parse_inbound(payload):
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
            continue  # duplicate delivery — already recorded
        enqueue_closer(str(event_id))
        accepted += 1
    return accepted


@app.get("/webhooks/meta/leadgen")
def meta_leadgen_verify(request: Request) -> Response:
    """Meta's GET handshake for the Lead Ads (leadgen) callback URL — required to 'Verify
    and Save' the subscription. Uses the Meta-specific verify token."""
    params = request.query_params
    expected = settings.meta_webhook_verify_token or settings.whatsapp_webhook_verify_token
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == expected:
        return PlainTextResponse(params.get("hub.challenge", ""))
    return PlainTextResponse("forbidden", status_code=403)


@app.post("/webhooks/meta/leadgen")
async def meta_leadgen(request: Request) -> JSONResponse:
    """Instant-Form (Lead Ads) leads → inbox. Idempotent on leadgen_id."""
    body = await request.body()
    if not _meta_signature_ok(body, request.headers.get("X-Hub-Signature-256")):
        return JSONResponse({"error": "invalid signature"}, status_code=403)
    payload = json.loads(body or b"{}")
    accepted = await run_in_threadpool(_process_leadgen, payload)
    return JSONResponse({"accepted": accepted}, status_code=200)


def _fetch_lead_fields(page_id: str, leadgen_id: str) -> tuple[str | None, str | None]:
    """Meta's real leadgen webhook payload carries only ids — the contact details must be
    fetched from Graph with the page's account token. Failure is non-fatal: the polling
    task (leadpilot.leads.poll_form_leads) backfills field_data on its next pass."""
    if settings.mock_meta:
        return None, None
    try:  # pragma: no cover - requires live Meta creds
        from sqlalchemy import select

        from leadpilot.core.db import platform_session
        from leadpilot.core.models import MetaConnection
        from leadpilot.integrations.meta import meta_adapter_for_account

        with platform_session() as s:
            conn = s.scalar(select(MetaConnection).where(MetaConnection.page_id == page_id))
            if conn is None:
                return None, None
            adapter = meta_adapter_for_account(s, conn.account_id)
        detail = adapter.get_lead_details(leadgen_id=leadgen_id)
        return _extract_lead_fields(detail)
    except Exception as exc:  # noqa: BLE001
        log.warning("leadgen_detail_fetch_failed", leadgen_id=leadgen_id, error=str(exc)[:200])
        return None, None


def _process_leadgen(payload: dict) -> int:
    accepted = 0
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "leadgen":
                continue
            v = change.get("value", {})
            leadgen_id, page_id = str(v.get("leadgen_id") or ""), str(v.get("page_id") or "")
            # Graph ids are numeric — anything else in an (HMAC-verified) payload is
            # malformed and must not reach a Graph path segment or a DB lookup.
            if not (leadgen_id.isdigit() and page_id.isdigit()):
                continue
            event_id = record_inbound_event(
                provider="meta_leadgen", external_id=leadgen_id,
                tenant_id=None, account_id=None, payload=v)
            if event_id is None:
                continue  # duplicate
            # field_data in the payload only exists in test fixtures; real deliveries
            # require a Graph fetch for the name/phone.
            name, phone = _extract_lead_fields(v)
            if name is None and phone is None:
                name, phone = _fetch_lead_fields(page_id, leadgen_id)
            capture_leadgen(page_id=page_id, leadgen_id=leadgen_id, name=name, phone=phone)
            accepted += 1
    return accepted


@app.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request) -> JSONResponse:
    """Subscription lifecycle → status + GST invoice. Signature-verified."""
    body = await request.body()
    secret = settings.razorpay_webhook_secret
    sig = request.headers.get("X-Razorpay-Signature")
    if secret:
        if not RazorpayAdapter.verify_webhook(body, sig, secret):
            return JSONResponse({"error": "invalid signature"}, status_code=403)
    elif settings.requires_secure_webhooks:
        return JSONResponse({"error": "unconfigured"}, status_code=403)

    # Replay protection: dedupe on Razorpay's event id so a captured, validly-signed body
    # can't be replayed to re-flip subscription state.
    event_uid = request.headers.get("X-Razorpay-Event-Id")
    payload = json.loads(body or b"{}")
    event = payload.get("event")
    sub = payload.get("payload", {}).get("subscription", {}).get("entity", {})
    sub_id = sub.get("id")
    if event and sub_id:
        dedupe_key = event_uid or f"{event}:{sub_id}:{sub.get('current_end', '')}"
        end = sub.get("current_end")
        period_end = datetime.fromtimestamp(end, UTC) if end else None
        status = await run_in_threadpool(
            _apply_razorpay, dedupe_key, payload, event, sub_id, period_end
        )
        return JSONResponse({"status": status}, status_code=200)
    return JSONResponse({"status": "ok"}, status_code=200)


def _apply_razorpay(dedupe_key, payload, event, sub_id, period_end) -> str:
    if record_inbound_event(
        provider="razorpay", external_id=dedupe_key,
        tenant_id=None, account_id=None, payload=payload,
    ) is None:
        return "duplicate"
    apply_razorpay_event(event=event, subscription_id=sub_id, period_end=period_end)
    return "ok"
