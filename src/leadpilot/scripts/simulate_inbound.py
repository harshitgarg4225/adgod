"""Drive an end-to-end CTWA lead conversation in-process (no broker needed).

Mirrors the webhook → closer-worker path: record an idempotent inbound_event, run
the Closer flow, drain the outbox (mock WhatsApp send), and print the resulting lead
+ transcript. Proves the whole walking skeleton from one command.

Usage:
  python -m leadpilot.scripts.simulate_inbound                 # full scripted convo → HOT
  python -m leadpilot.scripts.simulate_inbound --text "..."    # single inbound message
"""
from __future__ import annotations

import argparse
import os
from dataclasses import asdict

from sqlalchemy import select

from leadpilot.core.db import tenant_session
from leadpilot.core.models import Conversation, Lead, Message, Notification
from leadpilot.core.routing import record_inbound_event
from leadpilot.integrations.whatsapp.base import InboundMessage
from leadpilot.scripts.demo_constants import (
    DEMO_ACCOUNT_ID,
    DEMO_LEAD_PHONE,
    DEMO_PHONE_NUMBER_ID,
    DEMO_TENANT_ID,
)
from leadpilot.scripts.seed_demo import seed
from leadpilot.worker.tasks.closer import run_inbound

SCRIPT = [
    "Hello, kya aap NEET ki coaching karate ho?",
    "Mera naam Aman hai",
    "NEET ke liye coaching chahiye, 12th ke baad",
    "Agle mahine se shuru karna hai, budget thik hai",
    "Main Vijay Nagar, Indore me rehta hoon",
]


def _mid() -> str:
    return "wamid.SIM" + os.urandom(8).hex()


def deliver(text: str) -> dict:
    inbound = InboundMessage(
        wa_message_id=_mid(), from_phone=DEMO_LEAD_PHONE,
        phone_number_id=DEMO_PHONE_NUMBER_ID, text=text,
    )
    event_id = record_inbound_event(
        provider="whatsapp", external_id=inbound.wa_message_id,
        tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID,
        payload={"message": asdict(inbound)},
    )
    if event_id is None:
        return {"skipped": "duplicate"}
    return run_inbound(str(event_id))


def _print_transcript() -> None:
    with tenant_session(DEMO_TENANT_ID) as s:
        lead = s.scalars(
            select(Lead).where(Lead.account_id == DEMO_ACCOUNT_ID)
            .order_by(Lead.created_at.desc())
        ).first()
        if lead is None:
            print("No lead created.")
            return
        conv = s.scalar(select(Conversation).where(Conversation.lead_id == lead.id))
        msgs = s.scalars(
            select(Message).where(Message.conversation_id == conv.id)
            .order_by(Message.created_at)
        ).all()
        print("\n──────── Transcript ────────")
        for m in msgs:
            who = "👤 Lead" if m.direction == "IN" else "🤖 Saathi"
            print(f"{who}: {m.body}")
        print("────────────────────────────")
        print(f"Lead    : {lead.name or '(unknown)'}  [{lead.wa_phone}]")
        print(f"Score   : {lead.score}   Status: {lead.status}")
        print(f"Intent  : {lead.intent_summary}")
        print(f"Location: {lead.location_signal}")
        notifs = s.scalars(
            select(Notification).where(Notification.account_id == DEMO_ACCOUNT_ID)
            .order_by(Notification.created_at.desc())
        ).all()
        if notifs:
            print("\nNotifications:")
            for n in notifs[:3]:
                print(f"  • [{n.kind}] {n.title} — {n.body}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", help="Send a single inbound message instead of the script")
    args = parser.parse_args()

    seed()  # ensure the demo account exists
    turns = [args.text] if args.text else SCRIPT
    for text in turns:
        res = deliver(text)
        print(f"→ delivered: {text!r}  ⇒  {res}")
    _print_transcript()


if __name__ == "__main__":
    main()
