"""Producer-side enqueue helpers (send by task name; no agent code imported)."""
from __future__ import annotations

from leadpilot.worker.celery_app import app


def enqueue_inbound(inbound_event_id: str) -> None:
    app.send_task(
        "leadpilot.closer.process_inbound",
        args=[inbound_event_id],
        queue="closer",
    )


def enqueue_pipeline(task_name: str, tenant_id: str, account_id: str, queue: str = "agent") -> None:
    """Enqueue an owner-initiated pipeline phase (used when pipeline_inline is false)."""
    app.send_task(task_name, args=[str(tenant_id), str(account_id)], queue=queue)
