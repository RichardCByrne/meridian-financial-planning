"""Unit tests for pension_ie helpers."""

import pytest

from app.engine.pension_ie import (
    age_contribution_cap_pct,
    arf_minimum_drawdown_pct,
    lump_sum_tax,
    relievable_contribution,
)


@pytest.mark.parametrize(
    "age,expected",
    [
        (25, 0.15),
        (30, 0.20),
        (40, 0.25),
        (50, 0.30),
        (55, 0.35),
        (60, 0.40),
        (75, 0.40),
    ],
)
def test_age_contribution_cap_pct(age: int, expected: float) -> None:
    assert age_contribution_cap_pct(age) == expected


def test_relievable_contribution_caps_at_age_pct() -> None:
    # 25% requested, age 30 cap is 20% → 20% of 50k = 10k.
    assert relievable_contribution(50_000, 0.25, 30) == 10_000


def test_relievable_contribution_caps_at_earnings() -> None:
    # 40% requested, age 60 cap = 40%, but earnings cap kicks in at €115k.
    # So even on €200k of earnings, only €115k counts → 40% of 115k = €46,000.
    assert relievable_contribution(200_000, 0.40, 60) == 46_000


def test_relievable_contribution_zero_for_no_earnings() -> None:
    assert relievable_contribution(0, 0.20, 35) == 0
    assert relievable_contribution(50_000, 0.0, 35) == 0


def test_lump_sum_tax_zero_below_200k() -> None:
    assert lump_sum_tax(150_000) == 0
    assert lump_sum_tax(200_000) == 0


def test_lump_sum_tax_band_2() -> None:
    # 250k → 50k taxed at 20% = 10k.
    assert lump_sum_tax(250_000) == 10_000
    # 500k → 300k @ 20% = 60k.
    assert lump_sum_tax(500_000) == 60_000


def test_lump_sum_tax_band_3() -> None:
    # 600k → 300k @ 20% = 60k, plus 100k @ 40% = 40k → 100k total.
    assert lump_sum_tax(600_000) == 100_000


@pytest.mark.parametrize(
    "age,fund,expected_pct",
    [
        (55, 100_000, 0.0),
        (60, 100_000, 0.04),
        (69, 100_000, 0.04),
        (70, 100_000, 0.05),
        (80, 1_000_000, 0.05),
        (70, 2_500_000, 0.06),
    ],
)
def test_arf_minimum_drawdown_pct(age: int, fund: float, expected_pct: float) -> None:
    assert arf_minimum_drawdown_pct(age, fund) == expected_pct
