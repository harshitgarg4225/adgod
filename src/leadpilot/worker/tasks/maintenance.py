"""Maintenance / durability tasks + thin cron dispatchers.

These keep the outbox flowing and re-queue orphans. The optimizer/reporter
dispatchers are stubs for v1 (Phase 3 wires the sharded per-account fan-out);
they exist so the beat schedule and queues are real from Phase 1.
"""
from __future__ import annotations

from leadpilot.common.logging import get_logger
from leadpilot.saathi.workflow import get_workflow_runner
from leadpilot.worker.celery_app import app

log = get_logger("task.maintenance")


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
def optimizer_dispatch() -> dict:
    # Phase 3: shard LIVE accounts by account_id % OPTIMIZER_SHARD_COUNT and enqueue
    # one idempotent optimizer job per account onto the 'optimizer' queue.
    log.info("optimizer_dispatch_noop")
    return {"enqueued": 0, "note": "phase3"}


@app.task(name="leadpilot.reporter.dispatch_daily")
def reporter_dispatch_daily() -> dict:
    # Phase 2/3: enqueue daily Reporter jobs per LIVE account at 20:00 IST.
    log.info("reporter_dispatch_noop")
    return {"enqueued": 0, "note": "phase2"}
