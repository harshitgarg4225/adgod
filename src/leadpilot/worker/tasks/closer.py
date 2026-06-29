"""closer-worker task: process one inbound WhatsApp message end to end.

`run_inbound` is a plain function (reused by the Celery task, the demo script, and
tests). It loads the idempotent inbound_event, runs the Orchestrator's CLOSER flow
inside a tenant session, then drains the outbox so the reply goes out promptly.
"""
from __future__ import annotations

from uuid import UUID

from leadpilot.common.logging import get_logger
from leadpilot.core.db import tenant_session
from leadpilot.core.routing import load_inbound_event, mark_inbound_processed
from leadpilot.integrations.whatsapp.base import InboundMessage
from leadpilot.saathi.orchestrator import get_orchestrator
from leadpilot.saathi.workflow import get_workflow_runner
from leadpilot.worker.celery_app import app

log = get_logger("task.closer")


def run_inbound(inbound_event_id: str) -> dict:
    event = load_inbound_event(UUID(inbound_event_id))
    if event is None:
        return {"skipped": "event_missing"}
    if event.get("processed_at"):
        return {"skipped": "already_processed"}

    tenant_id = UUID(str(event["tenant_id"]))
    account_id = UUID(str(event["account_id"]))
    msg = event["payload"]["message"]
    inbound = InboundMessage(
        wa_message_id=msg["wa_message_id"],
        from_phone=msg["from_phone"],
        phone_number_id=msg["phone_number_id"],
        text=msg.get("text", ""),
        type=msg.get("type", "text"),
        timestamp=msg.get("timestamp"),
    )

    with tenant_session(tenant_id) as session:
        result = get_orchestrator().handle_inbound(
            session, tenant_id=tenant_id, account_id=account_id, inbound=inbound
        )

    mark_inbound_processed(UUID(inbound_event_id))
    # Deliver the queued reply now (also covered by the periodic drain).
    get_workflow_runner().drain_until_empty()

    return {
        "lead_id": str(result.lead_id),
        "sent": result.sent,
        "blocked": result.blocked,
        "score": result.score,
        "next_state": result.next_state,
        "hot": result.hot,
    }


@app.task(name="leadpilot.closer.process_inbound", bind=True, max_retries=3, default_retry_delay=2)
def process_inbound(self, inbound_event_id: str) -> dict:
    try:
        return run_inbound(inbound_event_id)
    except Exception as exc:  # noqa: BLE001
        log.error("closer_failed", error=str(exc), event_id=inbound_event_id)
        raise self.retry(exc=exc) from exc
