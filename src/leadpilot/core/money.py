"""Money is ALWAYS integer paise. No float ever touches a money value.

₹1 = 100 paise. GST and invoices are computed in paise. Display formatting is the
only place rupees appear, and only as strings.
"""
from __future__ import annotations

from dataclasses import dataclass

GST_RATE_BPS = 1800  # 18% in basis points


@dataclass(frozen=True, slots=True)
class Paise:
    """A non-negative integer amount in paise."""

    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.value, int) or isinstance(self.value, bool):
            raise TypeError(f"Paise must be int, got {type(self.value).__name__}")
        if self.value < 0:
            raise ValueError("Paise cannot be negative")

    def __int__(self) -> int:
        return self.value

    def __add__(self, other: Paise) -> Paise:
        return Paise(self.value + int(other))

    def __sub__(self, other: Paise) -> Paise:
        return Paise(self.value - int(other))

    @classmethod
    def from_rupees(cls, rupees: int) -> Paise:
        if not isinstance(rupees, int) or isinstance(rupees, bool):
            raise TypeError("from_rupees takes an int number of whole rupees")
        return cls(rupees * 100)

    def rupees_str(self) -> str:
        return f"₹{self.value // 100:,}.{self.value % 100:02d}"


def gst_paise(base_paise: int) -> int:
    """18% GST on a base amount, in paise, using integer math with round-half-up.

    Round-half-up matches statutory invoice rounding (floor could under-collect by up to a
    paise). Pure integer: add half the divisor before the integer division.
    """
    if base_paise < 0:
        raise ValueError("base cannot be negative")
    return (base_paise * GST_RATE_BPS + 5_000) // 10_000


def with_gst(base_paise: int) -> tuple[int, int, int]:
    """Return (base, gst, total) all in paise."""
    gst = gst_paise(base_paise)
    return base_paise, gst, base_paise + gst


def format_paise(paise: int) -> str:
    """Human display only. e.g. 50000 -> '₹500.00'."""
    sign = "-" if paise < 0 else ""
    paise = abs(paise)
    return f"{sign}₹{paise // 100:,}.{paise % 100:02d}"


def format_rupees(paise: int) -> str:
    """Whole-rupee display: drops the paise when the amount is a round rupee, so a plan
    price reads '₹1,499' not '₹1,499.00'. Falls back to two decimals for fractional
    amounts (e.g. a GST-inclusive total)."""
    sign = "-" if paise < 0 else ""
    paise = abs(paise)
    rupees, rem = paise // 100, paise % 100
    return f"{sign}₹{rupees:,}" if rem == 0 else f"{sign}₹{rupees:,}.{rem:02d}"
