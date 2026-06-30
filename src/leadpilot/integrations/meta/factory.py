from __future__ import annotations

from leadpilot.common.config import settings
from leadpilot.integrations.meta.base import MetaAdapter

_adapter: MetaAdapter | None = None


def get_meta_adapter() -> MetaAdapter:
    global _adapter
    if _adapter is None:
        if settings.mock_meta:
            from leadpilot.integrations.meta.mock import MockMetaAdapter

            _adapter = MockMetaAdapter()
        else:  # pragma: no cover
            from leadpilot.integrations.meta.cloud import CloudMetaAdapter

            _adapter = CloudMetaAdapter()
    return _adapter
