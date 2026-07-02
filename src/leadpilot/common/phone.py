"""Phone normalisation. One canonical E.164 form everywhere (+91XXXXXXXXXX for the
10-digit Indian numbers this product serves) — a provisioned owner must match the same
person logging in, whether they type 98..., 919..., or +91 98-... Anything else creates
a ghost self-serve account instead of landing in their provisioned business."""
from __future__ import annotations

import re


def normalize_phone(phone: str, default_country: str = "91") -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 10:
        return f"+{default_country}{digits}"
    if len(digits) == 12 and digits.startswith(default_country):
        return f"+{digits}"
    if digits:
        return f"+{digits}"
    return phone
