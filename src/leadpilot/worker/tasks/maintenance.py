"""Maintenance / durability tasks + thin cron dispatchers.

These keep the outbox flowing and re-queue orphans. The optimizer/reporter
dispatchers are stubs for v1 (Phase 3 wires the sharded per-account fan-out);
they exist so the beat schedule and queues are real from Phase 1.
"""
from __future__ import annotations

from sqlalchemy import text

from leadpilot.common.config import settings
from leadpilot.common.logging import get_logger
from leadpilot.core.db import platform_session, tenant_session
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


# Retention windows (days). Durability/PII tables grow unbounded otherwise (DB audit P1).
_RETENTION = {
    # processed effects no longer needed once delivered + a safety margin
    "outbox": ("status IN ('DONE','DEAD') AND created_at <", 7),
    # idempotency only needs to cover client retries
    "idempotency_keys": ("created_at <", 2),
    # consumed/expired OTPs
    "auth_otps": ("created_at <", 1),
    # webhook intake records once processed
    "inbound_events": ("processed_at IS NOT NULL AND created_at <", 30),
}


@app.task(name="leadpilot.workflow.progress_accounts")
def progress_accounts() -> dict:
    """Autonomously advance accounts through the pre-live pipeline — the 'set-and-forget'
    backstop so an account never stalls waiting for a UI click:
      SIGNED_UP/ONBOARDING (+business profile) → research
      RESEARCHED                                → creative (image + video)
      CREATIVE_GENERATED/APPROVED (+connections+approved creatives) → launch

    Idempotent by phase (each advance moves the phase forward). Launch only fires when the
    Meta+WhatsApp connections and approved creatives exist — it can't put ads live without
    them. Per-account try/except so one failure never blocks the rest."""
    from sqlalchemy import func, select

    from leadpilot.core.models import (
        BusinessProfile,
        Creative,
        MetaConnection,
        WhatsAppConnection,
    )
    from leadpilot.saathi import pipeline

    advanced = {"research": 0, "creative": 0, "launch": 0}
    with platform_session() as s:
        rows = s.execute(text(
            "SELECT tenant_id, id, phase FROM accounts WHERE deleted_at IS NULL AND phase IN "
            "('SIGNED_UP','ONBOARDING','RESEARCHED','CREATIVE_GENERATED','PENDING_APPROVAL',"
            "'APPROVED')"
        )).all()

    for tenant_id, account_id, phase in rows:
        try:
            if phase in ("SIGNED_UP", "ONBOARDING"):
                with tenant_session(tenant_id) as s:
                    ready = s.scalar(
                        select(BusinessProfile.id).where(BusinessProfile.account_id == account_id))
                if ready:
                    with tenant_session(tenant_id) as s:
                        pipeline.run_research(s, tenant_id=tenant_id, account_id=account_id)
                    advanced["research"] += 1
            elif phase == "RESEARCHED":
                with tenant_session(tenant_id) as s:
                    pipeline.run_creative(s, tenant_id=tenant_id, account_id=account_id)
                advanced["creative"] += 1
            elif phase in ("CREATIVE_GENERATED", "PENDING_APPROVAL", "APPROVED"):
                # PENDING_APPROVAL counts too: once the owner has approved creatives (via
                # API/UI) the account must launch autonomously even if no phase-advancing
                # click ever happens — approved>0 is the actual gate.
                with tenant_session(tenant_id) as s:
                    has_meta = s.scalar(
                        select(MetaConnection.id).where(MetaConnection.account_id == account_id))
                    has_wa = s.scalar(
                        select(WhatsAppConnection.id).where(
                            WhatsAppConnection.account_id == account_id))
                    approved = s.scalar(select(func.count(Creative.id)).where(
                        Creative.account_id == account_id,
                        Creative.approval_status == "APPROVED_FOR_LAUNCH")) or 0
                if has_meta and has_wa and approved:
                    with tenant_session(tenant_id) as s:
                        pipeline.launch_campaigns(s, tenant_id=tenant_id, account_id=account_id)
                    advanced["launch"] += 1
        except Exception as exc:  # noqa: BLE001 - one stall must not block the fleet
            log.warning("progress_failed", account=str(account_id), phase=phase,
                        error=str(exc)[:200])
            _record_progress_failure(tenant_id, account_id, phase, exc)
    if any(advanced.values()):
        log.info("progress_accounts", **advanced)
    return advanced


def _record_progress_failure(tenant_id, account_id, phase: str, exc: Exception) -> None:
    """A swallowed warning is how five clients silently stall at SIGNED_UP — surface every
    progress failure in the admin anomaly queue instead."""
    try:
        from leadpilot.core.models import GuardrailEvent

        with platform_session() as s:
            s.add(GuardrailEvent(
                tenant_id=tenant_id, account_id=account_id, type="ANOMALY", severity="ERROR",
                detail={"reason": "pipeline_progress_failed", "phase": phase,
                        "error": str(exc)[:300]},
                action_taken="NONE"))
    except Exception:  # noqa: BLE001 - reporting must never take down the cron
        log.warning("progress_failure_unrecorded", account=str(account_id))


@app.task(name="leadpilot.leads.poll_form_leads")
def poll_form_leads() -> dict:
    """Every 10 min: pull Instant-Form leads via Graph with each account's System User
    token. Owned-asset reads need NO app review and NO webhook subscription — this is the
    review-free automatic lead path (the leadgen webhook, when configured, just makes it
    faster). Idempotent per lead via leadgen_id."""
    if settings.mock_meta:
        return {"captured": 0}
    from leadpilot.core.webhooks import capture_leadgen
    from leadpilot.integrations.meta import meta_adapter_for_account

    captured = 0
    with platform_session() as s:
        conns = s.execute(text(
            "SELECT tenant_id, account_id, page_id FROM meta_connections "
            "WHERE page_id IS NOT NULL")).all()
    for tenant_id, account_id, page_id in conns:
        try:
            with tenant_session(tenant_id) as s:
                meta = meta_adapter_for_account(s, account_id)
            for ld in meta.get_form_leads(page_id=page_id):
                fields = {(f.get("name") or "").lower(): (f.get("values") or [None])[0]
                          for f in ld.get("field_data", [])}
                lead_id = capture_leadgen(
                    page_id=page_id, leadgen_id=ld["leadgen_id"],
                    name=fields.get("full_name") or fields.get("name"),
                    phone=fields.get("phone_number") or fields.get("phone"))
                if lead_id is not None:
                    captured += 1
        except Exception as exc:  # noqa: BLE001 - one account must not block the fleet
            log.warning("poll_form_leads_failed", account=str(account_id),
                        error=str(exc)[:200])
    if captured:
        log.info("poll_form_leads", captured=captured)
    return {"captured": captured}


@app.task(name="leadpilot.leads.mark_no_response")
def mark_no_response() -> dict:
    """Hourly: a lead that engaged but went silent until the 24h WhatsApp service window
    closed (and never qualified) is moved to NO_RESPONSE. This surfaces the 'silent lead'
    state the inbox/segments rely on, and is the precondition for out-of-window template
    re-engagement (which needs an approved WaTemplate — tracked separately)."""
    with platform_session() as s:
        res = s.execute(
            text(
                "UPDATE leads SET status='NO_RESPONSE' "
                "WHERE status='ENGAGED' AND id IN ("
                "  SELECT lead_id FROM conversations "
                "  WHERE free_window_expires_at IS NOT NULL AND free_window_expires_at < now())"
            )
        )
        n = res.rowcount or 0
    if n:
        log.info("mark_no_response", count=n)
    return {"marked": n}


@app.task(name="leadpilot.leads.re_engage")
def re_engage() -> dict:
    """Hourly: send an approved re-engagement template to silent (NO_RESPONSE) leads.

    Templates are the only messages Meta allows outside the 24h window, so this is how a
    gone-quiet paid lead gets one more nudge. Idempotent: a lead already carrying a
    re-engagement template message is skipped, so it fires at most once per lead."""
    from sqlalchemy import select

    from leadpilot.core.models import Conversation, Lead, Message, WhatsAppConnection
    from leadpilot.saathi.outbound import enqueue_send

    sent = 0
    with platform_session() as s:
        leads = s.scalars(select(Lead).where(Lead.status == "NO_RESPONSE")).all()
        for lead in leads:
            conv = s.scalar(select(Conversation).where(Conversation.lead_id == lead.id))
            if conv is None:
                continue
            already = s.scalar(
                select(Message).where(
                    Message.conversation_id == conv.id,
                    Message.type == "TEMPLATE",
                    Message.template_name == "re_engagement",
                )
            )
            if already is not None:
                continue
            wa = s.scalar(
                select(WhatsAppConnection).where(
                    WhatsAppConnection.account_id == lead.account_id
                )
            )
            if wa is None or not wa.phone_number_id:
                continue
            enqueue_send(
                s,
                tenant_id=lead.tenant_id,
                account_id=lead.account_id,
                conversation_id=conv.id,
                phone_number_id=wa.phone_number_id,
                to_phone=lead.wa_phone,
                step_id=f"reengage:{conv.id}",
                kind="template",
                template_name="re_engagement",
                language="hi",
                params=[lead.name or "there"],
            )
            sent += 1
    if sent:
        log.info("re_engage", sent=sent)
    return {"sent": sent}


@app.task(name="leadpilot.workflow.retention_sweep")
def retention_sweep() -> dict:
    """Daily: bound the growth of durability/PII tables. Runs as the platform role; each
    DELETE is independent so one failure can't block the rest."""
    deleted: dict[str, int] = {}
    for table, (predicate, days) in _RETENTION.items():
        try:
            with platform_session() as s:
                res = s.execute(
                    text(f"DELETE FROM {table} WHERE {predicate} now() - interval '{days} days'")
                )
                deleted[table] = res.rowcount or 0
        except Exception as exc:  # noqa: BLE001 - never let one table abort the sweep
            log.warning("retention_sweep_failed", table=table, error=str(exc)[:200])
    log.info("retention_sweep", **deleted)
    return deleted


@app.task(name="leadpilot.billing.trial_sweep")
def trial_sweep() -> dict:
    """Daily: convert expired trials. A TRIAL whose trial_end has passed without a captured
    mandate goes PAST_DUE and its ads are paused (stops free-rider spend); the owner gets a
    BILLING notification nudging them to add payment. Real mandate captures flip the
    subscription to ACTIVE via the Razorpay webhook before this runs."""
    from datetime import UTC, datetime

    expired = 0
    with platform_session() as s:
        rows = s.execute(
            text(
                "SELECT id, tenant_id, account_id FROM subscriptions "
                "WHERE status = 'TRIAL' AND trial_end IS NOT NULL AND trial_end < now()"
            )
        ).all()
        now = datetime.now(UTC)
        for sub_id, tenant_id, account_id in rows:
            s.execute(
                text("UPDATE subscriptions SET status='PAST_DUE', updated_at=:now WHERE id=:id"),
                {"now": now, "id": sub_id},
            )
            # Pause spend until they pay.
            s.execute(
                text("UPDATE accounts SET phase='PAUSED' WHERE id=:id AND phase IN "
                     "('LIVE','OPTIMIZING','FATIGUE_REFRESH')"),
                {"id": account_id},
            )
            s.execute(
                text(
                    "INSERT INTO notifications (tenant_id, account_id, kind, title, body) "
                    "VALUES (:t, :a, 'BILLING', :title, :body)"
                ),
                {
                    "t": tenant_id, "a": account_id,
                    "title": "Your free trial has ended",
                    "body": "Add a payment method to keep Saathi running your ads.",
                },
            )
            expired += 1
    if expired:
        log.info("trial_sweep", expired=expired)
    return {"expired": expired}
