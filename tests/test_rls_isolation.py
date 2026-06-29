"""RLS multi-tenant isolation (PRD §7.4, §13). Tenant A cannot read tenant B's
lead/conversation/message rows — even though the app connection role is a superuser,
because tenant_session SET LOCAL ROLE to the non-superuser app role + sets the GUC."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from leadpilot.core.db import platform_session, tenant_session
from leadpilot.core.models import Account, Conversation, Lead, Message, Tenant


def _make_tenant(name: str) -> uuid.UUID:
    tid = uuid.uuid4()
    with platform_session() as s:
        s.add(Tenant(id=tid, name=name, type="DIRECT", status="ACTIVE", settings={}))
    return tid


def _make_account_with_lead(tenant_id: uuid.UUID, phone: str) -> tuple[uuid.UUID, uuid.UUID]:
    with tenant_session(tenant_id) as s:
        acc = Account(tenant_id=tenant_id, business_name="Biz", category="coaching",
                      default_language="hi")
        s.add(acc)
        s.flush()
        lead = Lead(tenant_id=tenant_id, account_id=acc.id, wa_phone=phone, status="NEW")
        s.add(lead)
        s.flush()
        conv = Conversation(tenant_id=tenant_id, lead_id=lead.id, state="GREET")
        s.add(conv)
        s.flush()
        s.add(Message(tenant_id=tenant_id, conversation_id=conv.id, direction="IN",
                      body="secret-of-tenant", status="DELIVERED"))
        return acc.id, lead.id


def test_tenant_cannot_read_another_tenants_data():
    t_a = _make_tenant("Tenant A")
    t_b = _make_tenant("Tenant B")
    _, lead_a = _make_account_with_lead(t_a, "+919800000001")
    _, lead_b = _make_account_with_lead(t_b, "+919800000002")

    # Tenant B's session must NOT see tenant A's lead, and vice versa.
    with tenant_session(t_b) as s:
        assert s.get(Lead, lead_a) is None
        visible = s.scalars(select(Lead)).all()
        assert {ld.id for ld in visible} == {lead_b}
        # Messages/conversations also isolated.
        assert s.scalars(select(Message)).all() and all(
            m.body == "secret-of-tenant" for m in s.scalars(select(Message)).all()
        )
        assert all(m.tenant_id == t_b for m in s.scalars(select(Message)).all())

    with tenant_session(t_a) as s:
        assert s.get(Lead, lead_b) is None
        assert {ld.id for ld in s.scalars(select(Lead)).all()} == {lead_a}


def test_write_under_wrong_tenant_is_blocked():
    """A row whose tenant_id != the session GUC is rejected by the RLS WITH CHECK."""
    import pytest
    from sqlalchemy.exc import ProgrammingError

    t_a = _make_tenant("Tenant A2")
    other = uuid.uuid4()
    with pytest.raises((ProgrammingError, Exception)):
        with tenant_session(t_a) as s:
            s.add(Lead(tenant_id=other, account_id=uuid.uuid4(),
                       wa_phone="+919800000009", status="NEW"))
            s.flush()
