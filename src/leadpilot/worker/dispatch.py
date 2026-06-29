"""Producer-side enqueue helpers (send by task name; no agent code imported)."""
from __future__ import annotations

from leadpilot.worker.celery_app import app


def enqueue_inbound(inbound_event_id: str) -> None:
    app.send_task(
        "leadpilot.closer.process_inbound",
        args=[inbound_event_id],
        queue="closer",
    )
