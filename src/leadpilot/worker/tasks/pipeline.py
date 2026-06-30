"""Pipeline worker tasks (agent-worker). Each runs one phase under a tenant session.

Triggered by owner actions (bff enqueues), by chained follow-ons, or by cron
(optimizer hourly, reporter daily). Idempotent and reason-coded.
"""
from __future__ import annotations

from uuid import UUID

from leadpilot.common.logging import get_logger
from leadpilot.core.db import tenant_session
from leadpilot.saathi import pipeline
from leadpilot.worker.celery_app import app

log = get_logger("task.pipeline")


def _ids(tenant_id: str, account_id: str) -> tuple[UUID, UUID]:
    return UUID(tenant_id), UUID(account_id)


@app.task(name="leadpilot.pipeline.research")
def research(tenant_id: str, account_id: str) -> str:
    t, a = _ids(tenant_id, account_id)
    with tenant_session(t) as s:
        brief_id = pipeline.run_research(s, tenant_id=t, account_id=a)
    return str(brief_id)


@app.task(name="leadpilot.pipeline.creative")
def creative(tenant_id: str, account_id: str) -> list[str]:
    t, a = _ids(tenant_id, account_id)
    with tenant_session(t) as s:
        ids = pipeline.run_creative(s, tenant_id=t, account_id=a)
    return [str(i) for i in ids]


@app.task(name="leadpilot.launch.run")
def launch(tenant_id: str, account_id: str) -> list[str]:
    t, a = _ids(tenant_id, account_id)
    with tenant_session(t) as s:
        ids = pipeline.launch_campaigns(s, tenant_id=t, account_id=a)
    return [str(i) for i in ids]


@app.task(name="leadpilot.optimizer.run")
def optimize(tenant_id: str, account_id: str) -> int:
    t, a = _ids(tenant_id, account_id)
    with tenant_session(t) as s:
        decisions = pipeline.run_optimization(s, tenant_id=t, account_id=a)
    return len(decisions)


@app.task(name="leadpilot.reporter.run")
def report(tenant_id: str, account_id: str) -> str:
    t, a = _ids(tenant_id, account_id)
    with tenant_session(t) as s:
        return pipeline.run_report(s, tenant_id=t, account_id=a)
