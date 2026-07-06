"""Celery app. One app, multiple queues; services bind to specific queues.

  closer-worker : -Q closer            (warm, latency-isolated hot path)
  agent-worker  : -Q agent,optimizer,launch,fatigue
  cron-dispatch : celery beat          (thin enqueuers; zero reasoning)
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init

from leadpilot.common.config import settings
from leadpilot.common.logging import configure_logging
from leadpilot.common.observability import init_observability

configure_logging()
# Same fail-closed secret check the web services run — so a worker never boots on
# dev-default JWT_SECRET / TOKEN_ENCRYPTION_KEY in production (workers decrypt Meta tokens).
init_observability("celery-worker")


@worker_process_init.connect
def _init_worker_process(**_kwargs) -> None:
    # Each prefork child gets its own DB pool — never share a connection across fork.
    from leadpilot.core.db import dispose_engine

    dispose_engine()


app = Celery("leadpilot", broker=settings.redis_url, backend=settings.redis_url)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_acks_late=True,
    # acks_late + Redis: a task outliving the visibility timeout gets REDELIVERED and runs
    # twice concurrently. Keep the timeout above the hardest kill-limit below.
    broker_transport_options={"visibility_timeout": 7200},
    task_time_limit=3600,
    task_soft_time_limit=3300,
    worker_prefetch_multiplier=1,
    task_default_queue="agent",
    task_routes={
        "leadpilot.closer.*": {"queue": "closer"},
        "leadpilot.optimizer.*": {"queue": "optimizer"},
        "leadpilot.launch.*": {"queue": "launch"},
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
    "progress-accounts": {  # autonomous pre-live progression (research→creative→launch)
        "task": "leadpilot.workflow.progress_accounts",
        "schedule": 600.0,  # every 10 min — a backstop; onboarding also drives these
    },
    "auto-approve-pending": {  # autopilot-with-veto: launch unless the owner intervened
        "task": "leadpilot.approvals.auto_approve",
        "schedule": crontab(minute="*/30"),
    },
    "poll-form-leads": {  # review-free Instant-Form intake via owned-asset Graph reads
        "task": "leadpilot.leads.poll_form_leads",
        "schedule": 600.0,  # every 10 min — leads are perishable, call within minutes
    },
    "mark-no-response-hourly": {
        "task": "leadpilot.leads.mark_no_response",
        "schedule": crontab(minute=15),
    },
    "re-engage-hourly": {
        "task": "leadpilot.leads.re_engage",
        "schedule": crontab(minute=30),
    },
    "reporter-daily-2000-ist": {
        "task": "leadpilot.reporter.dispatch_daily",
        "schedule": crontab(hour=20, minute=0),
    },
    "research-refresh-daily-0400-ist": {  # staleness-gated: only briefs >30 days old
        "task": "leadpilot.research.refresh_stale",
        "schedule": crontab(hour=4, minute=0),
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
