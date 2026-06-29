"""Money is always integer paise; no float ever touches a money value (PRD §8)."""
import pytest

from leadpilot.core.money import Paise, format_paise, gst_paise, with_gst


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
