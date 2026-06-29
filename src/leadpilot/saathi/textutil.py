"""Shared text heuristics for qualification (single source of truth)."""
from __future__ import annotations

import re

_JUNK_RE = re.compile(r"^[\W_]+$")
_ABUSE = {"abuse", "spam", "idiot", "stupid", "bkl", "chutiya"}


def is_junk(text: str) -> bool:
    t = (text or "").strip().lower()
    if len(t) < 2 or _JUNK_RE.match(t):
        return True
    return any(w in t for w in _ABUSE)
