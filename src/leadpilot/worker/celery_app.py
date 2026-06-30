"""Celery app. One app, multiple queues; services bind to specific queues.

  closer-worker : -Q closer            (warm, latency-isolated hot path)
  agent-worker  : -Q agent,optimizer,launch,fatigue
  cron-dispatch : celery beat          (thin enqueuers; zero reasoning)
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from leadpilot.common.config import settings
from leadpilot.common.logging import configure_logging

configure_logging()

app = Celery("leadpilot", broker=settings.redis_url, backend=settings.redis_url)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="agent",
    task_routes={
        "leadpilot.closer.*": {"queue": "closer"},
        "leadpilot.optimizer.*": {"queue": "optimizer"},
        "leadpilot.launch.*": {"queue": "launch"},
        "leadpilot.fatigue.*": {"queue": "fatigue"},
    },
)

# Discover task modules (imports leadpilot.worker.tasks on worker finalize).
app.autodiscover_tasks(["leadpilot.worker"])

# Cron schedule (cron-dispatch / beat). Dispatchers only enqueue idempotent jobs.
app.conf.beat_schedule = {
    "drain-outbox": {
        "task": "leadpilot.workflow.drain_outbox",
        "schedule": 5.0,  # seconds — keeps queued sends flowing even without inline drain
    },
    "reap-orphans": {
        "task": "leadpilot.workflow.reap",
        "schedule": 60.0,
    },
    "optimizer-hourly": {
        "task": "leadpilot.optimizer.dispatch",
        "schedule": crontab(minute=0),
    },
    "reporter-daily-2000-ist": {
        "task": "leadpilot.reporter.dispatch_daily",
        "schedule": crontab(hour=20, minute=0),
    },
    "retention-sweep-daily-0330-ist": {
        "task": "leadpilot.workflow.retention_sweep",
        "schedule": crontab(hour=3, minute=30),  # off-peak
    },
    "trial-sweep-daily-0900-ist": {
        "task": "leadpilot.billing.trial_sweep",
        "schedule": crontab(hour=9, minute=0),
    },
}
