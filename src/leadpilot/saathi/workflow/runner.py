"""WorkflowRunner — drains the transactional outbox.

Claim (mark IN_PROGRESS, commit) → perform external effect → mark DONE / retry.
A crash mid-effect leaves the row IN_PROGRESS; the cron reaper re-queues it. Because
handlers are idempotent, re-running is safe. This is the Temporal replacement seam.
"""
from __future__ import annotations

from leadpilot.common.logging import get_logger
from leadpilot.core.db import platform_session
from leadpilot.core.outbox import claim_pending, mark_done, mark_retry, reap_orphans
from leadpilot.saathi.workflow.effects import EFFECT_HANDLERS

log = get_logger("workflow")


class WorkflowRunner:
    def drain(self, *, limit: int = 20) -> int:
        """Process up to `limit` pending outbox rows. Returns count attempted."""
        with platform_session() as session:
            entries = claim_pending(session, limit=limit)
        for entry in entries:
            self._process(entry)
        return len(entries)

    def drain_until_empty(self, *, max_batches: int = 50) -> int:
        total = 0
        for _ in range(max_batches):
            n = self.drain()
            total += n
            if n == 0:
                break
        return total

    def _process(self, entry: dict) -> None:
        handler = EFFECT_HANDLERS.get(entry["effect_type"])
        if handler is None:
            with platform_session() as session:
                mark_retry(session, entry["id"], entry["attempts"],
                           f"no_handler:{entry['effect_type']}")
            return
        try:
            result = handler(entry)
            with platform_session() as session:
                mark_done(session, entry["id"], result)
        except Exception as exc:  # noqa: BLE001 - record and retry/DLQ
            log.error("effect_failed", effect=entry["effect_type"], error=str(exc))
            with platform_session() as session:
                mark_retry(session, entry["id"], entry["attempts"], str(exc))

    def reap(self, *, stuck_minutes: int = 10) -> int:
        with platform_session() as session:
            return reap_orphans(session, stuck_minutes=stuck_minutes)


_runner: WorkflowRunner | None = None


def get_workflow_runner() -> WorkflowRunner:
    global _runner
    if _runner is None:
        _runner = WorkflowRunner()
    return _runner
