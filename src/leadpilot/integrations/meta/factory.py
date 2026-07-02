"""Meta adapter selection + per-account token plumbing.

The review-free agency model runs each client's ads with a System User token from the
founder's Business Manager: per-account tokens live encrypted on MetaConnection and are
decrypted only here, at the transport boundary; META_SYSTEM_USER_TOKEN is the shared
fallback (one founder token serves every client). Mock mode keeps a process singleton.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from leadpilot.common.config import settings
from leadpilot.integrations.meta.base import MetaAdapter

_mock_adapter: MetaAdapter | None = None
_cloud_adapters: dict[str, MetaAdapter] = {}  # keyed by token → reuse httpx pools


def _cloud_for_token(token: str) -> MetaAdapter:
    adapter = _cloud_adapters.get(token)
    if adapter is None:  # pragma: no cover - requires live Meta creds
        from leadpilot.integrations.meta.cloud import CloudMetaAdapter

        adapter = CloudMetaAdapter(token)
        _cloud_adapters[token] = adapter
    return adapter


def get_meta_adapter(token: str | None = None) -> MetaAdapter:
    """Adapter for a known token (or the shared founder token). Prefer
    meta_adapter_for_account() wherever an account is in scope."""
    global _mock_adapter
    if settings.mock_meta:
        if _mock_adapter is None:
            from leadpilot.integrations.meta.mock import MockMetaAdapter

            _mock_adapter = MockMetaAdapter()
        return _mock_adapter
    tok = token or settings.meta_system_user_token
    if not tok:
        raise RuntimeError(
            "No Meta access token: store one on the account's MetaConnection "
            "(provision_client --meta-token) or set META_SYSTEM_USER_TOKEN"
        )
    return _cloud_for_token(tok)


def meta_adapter_for_account(session: Session, account_id: UUID | str) -> MetaAdapter:
    """The adapter every pipeline phase must use: decrypts the account's own System User
    token when present, else falls back to the shared founder token."""
    if settings.mock_meta:
        return get_meta_adapter()
    from sqlalchemy import select

    from leadpilot.common.crypto import decrypt
    from leadpilot.core.models import MetaConnection

    conn = session.scalar(select(MetaConnection).where(MetaConnection.account_id == account_id))
    token = decrypt(conn.system_user_token_enc) if conn and conn.system_user_token_enc else None
    return get_meta_adapter(token)
