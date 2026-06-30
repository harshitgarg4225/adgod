"""Maintenance / durability tasks + thin cron dispatchers.

These keep the outbox flowing and re-queue orphans. The optimizer/reporter
dispatchers are stubs for v1 (Phase 3 wires the sharded per-account fan-out);
they exist so the beat schedule and queues are real from Phase 1.
"""
from __future__ import annotations

from sqlalchemy import text

from leadpilot.common.config import settings
from leadpilot.common.logging import get_logger
from leadpilot.core.db import platform_session
from leadpilot.saathi.workflow import get_workflow_runner
from leadpilot.worker.celery_app import app

log = get_logger("task.maintenance")


def _live_accounts() -> list[tuple[str, str]]:
    """(tenant_id, account_id) for accounts Saathi should service. Cross-tenant scan
    runs via the platform role (BYPASSRLS), never the per-request app role."""
    with platform_session() as s:
        rows = s.execute(
            text("SELECT tenant_id, id FROM accounts "
                 "WHERE phase IN ('LIVE','OPTIMIZING') AND deleted_at IS NULL")
        ).all()
    return [(str(r[0]), str(r[1])) for r in rows]


@app.task(name="leadpilot.workflow.drain_outbox")
def drain_outbox() -> int:
    return get_workflow_runner().drain_until_empty()


@app.task(name="leadpilot.workflow.reap")
def reap() -> int:
    n = get_workflow_runner().reap()
    if n:
        log.info("reaped_orphans", count=n)
    return n


@app.task(name="leadpilot.optimizer.dispatch")
def optimizer_dispatch(shard: int | None = None) -> dict:
    """Hourly: enqueue one idempotent optimizer job per LIVE account, sharded by
    account_id so the fan-out spreads across agent-worker replicas (PRD §7.4)."""
    n = settings.optimizer_shard_count or 1
    enqueued = 0
    for tenant_id, account_id in _live_accounts():
        if shard is not None and (int(account_id.replace("-", ""), 16) % n) != shard:
            continue
        app.send_task("leadpilot.optimizer.run", args=[tenant_id, account_id], queue="optimizer")
        enqueued += 1
    log.info("optimizer_dispatch", enqueued=enqueued, shard=shard)
    return {"enqueued": enqueued}


@app.task(name="leadpilot.reporter.dispatch_daily")
def reporter_dispatch_daily() -> dict:
    """Daily 20:00 IST: enqueue a Reporter job per LIVE account."""
    enqueued = 0
    for tenant_id, account_id in _live_accounts():
        app.send_task("leadpilot.reporter.run", args=[tenant_id, account_id], queue="agent")
        enqueued += 1
    log.info("reporter_dispatch", enqueued=enqueued)
    return {"enqueued": enqueued}
