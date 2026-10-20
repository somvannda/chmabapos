from __future__ import annotations

from decimal import Decimal

from app.money import quantum_for, round_money


def test_whole_currency_has_no_subunit() -> None:
    assert quantum_for(0) == Decimal("1")
    assert str(round_money(Decimal("4000.49"), 0)) == "4000"
    assert str(round_money(Decimal("4000.50"), 0)) == "4001"


def test_two_decimal_currency_keeps_cents() -> None:
    assert quantum_for(2) == Decimal("0.01")
    assert str(round_money(Decimal("3"), 2)) == "3.00"
    assert str(round_money(Decimal("1.005"), 2)) == "1.01"


def test_missing_precision_is_treated_as_whole() -> None:
    assert quantum_for(None) == Decimal("1")
    assert str(round_money(Decimal("12.6"), None)) == "13"


def test_more_precision_is_honoured() -> None:
    assert quantum_for(3) == Decimal("0.001")
    assert str(round_money(Decimal("1.2345"), 3)) == "1.235"
