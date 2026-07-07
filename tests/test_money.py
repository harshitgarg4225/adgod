"""Money is always integer paise; no float ever touches a money value (PRD §8)."""
import pytest

from leadpilot.core.money import Paise, format_paise, format_rupees, gst_paise, with_gst


def test_paise_rejects_float():
    with pytest.raises(TypeError):
        Paise(100.5)  # type: ignore[arg-type]


def test_paise_rejects_bool_and_negative():
    with pytest.raises(TypeError):
        Paise(True)  # bool is not a valid paise amount
    with pytest.raises(ValueError):
        Paise(-1)


def test_from_rupees_and_arithmetic():
    assert int(Paise.from_rupees(500)) == 50000
    assert int(Paise(50000) + Paise(100)) == 50100
    assert int(Paise(50000) - Paise(100)) == 49900


def test_gst_is_integer_paise():
    base, gst, total = with_gst(149900)  # ₹1499
    assert gst == gst_paise(149900) == 26982  # 18%
    assert isinstance(gst, int) and isinstance(total, int)
    assert total == base + gst


def test_format_paise():
    assert format_paise(50000) == "₹500.00"
    assert format_paise(149900) == "₹1,499.00"


def test_format_rupees_drops_round_paise():
    # A clean plan price shows without the noisy ".00".
    assert format_rupees(149900) == "₹1,499"
    assert format_rupees(699900) == "₹6,999"
    # A fractional (GST-inclusive) amount keeps its paise.
    assert format_rupees(176882) == "₹1,768.82"
    assert format_rupees(0) == "₹0"
