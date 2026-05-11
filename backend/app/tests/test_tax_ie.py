"""Golden-number tests for the Ireland 2026 tax engine.

Each case is hand-computed against Budget 2026 rates (KPMG / BDO / Grant
Thornton tables). Tolerance is 1c. If a constant in tax_ie_2026.py changes,
update both the constant and the expectation here.
"""

import pytest

from app.config.tax_ie_2026 import FilingStatus
from app.engine import tax_ie


def approx(a: float, b: float, tol: float = 0.02) -> bool:
    return abs(a - b) <= tol


def test_single_paye_60k():
    s = FilingStatus(is_paye_employee=True)
    r = tax_ie.compute(60_000, s)
    # Income tax: 44k*20% + 16k*40% = 8,800 + 6,400 = 15,200, less 4,000 credits = 11,200
    assert approx(r.income_tax, 11_200.00)
    # USC: 60.06 + 333.76 + 939.00 = 1,332.82
    assert approx(r.usc, 1_332.82)
    # PRSI: 60,000 * 4.2375% (2026 blended Jan–Sep 4.20% / Oct–Dec 4.35%) = 2,542.50
    assert approx(r.prsi, 2_542.50)
    assert approx(r.total_tax, 15_075.32)
    assert approx(r.net_income, 44_924.68)
    assert r.band_used == "single"


def test_single_paye_30k():
    s = FilingStatus(is_paye_employee=True)
    r = tax_ie.compute(30_000, s)
    # IT: 30k*20% = 6,000 - 4,000 credits = 2,000
    assert approx(r.income_tax, 2_000.00)
    # USC: 60.06 + 333.76 + 39.00 = 432.82
    assert approx(r.usc, 432.82)
    # PRSI: 30,000 * 4.2375% = 1,271.25
    assert approx(r.prsi, 1_271.25)
    assert approx(r.net_income, 26_295.93)


def test_below_usc_and_prsi_thresholds():
    """At €12,500 gross: tax credits cover IT, USC exempt, PRSI weekly under threshold."""
    s = FilingStatus(is_paye_employee=True)
    r = tax_ie.compute(12_500, s)
    assert r.income_tax == 0.0
    assert r.usc == 0.0
    assert r.prsi == 0.0
    assert r.net_income == 12_500.0


def test_married_one_income_70k():
    s = FilingStatus(married=True, is_two_income_couple=False, is_paye_employee=True)
    r = tax_ie.compute(70_000, s)
    # IT: 53k*20% + 17k*40% = 10,600 + 6,800 = 17,400 - 6,000 credits = 11,400
    assert approx(r.income_tax, 11_400.00)
    # USC: 60.06 + 333.76 + 1,239.00 = 1,632.82
    assert approx(r.usc, 1_632.82)
    # PRSI: 70,000 * 4.2375% = 2,966.25
    assert approx(r.prsi, 2_966.25)
    assert approx(r.net_income, 54_000.93)
    assert r.band_used == "married_one_income"


def test_self_employed_50k():
    s = FilingStatus(is_paye_employee=False)
    r = tax_ie.compute(50_000, s)
    # IT: 44k*20% + 6k*40% = 8,800 + 2,400 = 11,200 - 4,000 (personal+earned-income) = 7,200
    assert approx(r.income_tax, 7_200.00)
    # USC: 60.06 + 333.76 + 639.00 = 1,032.82
    assert approx(r.usc, 1_032.82)
    # PRSI: 50,000 * 4.2375% = 2,118.75 (above min)
    assert approx(r.prsi, 2_118.75)
    assert approx(r.net_income, 39_648.43)


def test_top_usc_band_single_100k():
    s = FilingStatus(is_paye_employee=True)
    r = tax_ie.compute(100_000, s)
    # IT: 44k*20% + 56k*40% = 8,800 + 22,400 = 31,200 - 4,000 = 27,200
    assert approx(r.income_tax, 27_200.00)
    # USC: 60.06 + 333.76 + 1,240.32 + 2,396.48 = 4,030.62
    assert approx(r.usc, 4_030.62)
    # PRSI: 100,000 * 4.2375% = 4,237.50
    assert approx(r.prsi, 4_237.50)
    assert approx(r.net_income, 64_531.88)


def test_zero_income_returns_zero():
    s = FilingStatus()
    r = tax_ie.compute(0, s)
    assert r.income_tax == 0.0
    assert r.usc == 0.0
    assert r.prsi == 0.0
    assert r.net_income == 0.0


def test_single_parent_uses_extended_band():
    s = FilingStatus(is_single_parent=True, is_paye_employee=True)
    r = tax_ie.compute(50_000, s)
    # IT: 48k*20% + 2k*40% = 9,600 + 800 = 10,400 - (2k+2k+1.9k credits) = 4,500
    assert approx(r.income_tax, 4_500.00)
    assert r.band_used == "single_parent"


@pytest.mark.parametrize("gross", [10_000, 13_001, 28_700, 70_044, 150_000])
def test_usc_monotonic(gross: float):
    """USC should be non-decreasing with income."""
    prev = -1.0
    for amt in [gross - 1, gross, gross + 1]:
        u = tax_ie.usc(max(0.0, amt))
        assert u >= prev - 0.01
        prev = u


def test_rent_credit_single():
    """€1,000 rent credit reduces income tax by exactly €1,000 (when IT > €1,000)."""
    base = tax_ie.compute(60_000, FilingStatus(is_paye_employee=True))
    with_rent = tax_ie.compute(60_000, FilingStatus(is_paye_employee=True, claims_rent_credit=True))
    assert approx(base.income_tax - with_rent.income_tax, 1_000.0)


def test_rent_credit_married_doubles():
    """Married filers get 2x rent credit (each spouse's claim aggregated)."""
    base = tax_ie.compute(80_000, FilingStatus(married=True, is_paye_employee=True))
    with_rent = tax_ie.compute(80_000, FilingStatus(married=True, is_paye_employee=True, claims_rent_credit=True))
    assert approx(base.income_tax - with_rent.income_tax, 2_000.0)


def test_age_credit_single_at_65():
    """€245 age credit kicks in at 65."""
    s_under = FilingStatus(is_paye_employee=True, age=64)
    s_over = FilingStatus(is_paye_employee=True, age=65)
    under = tax_ie.compute(40_000, s_under)
    over = tax_ie.compute(40_000, s_over)
    assert approx(under.income_tax - over.income_tax, 245.0)


def test_age_credit_married_at_70():
    """Married couple at 70 gets €490 age credit."""
    base = tax_ie.compute(80_000, FilingStatus(married=True, is_paye_employee=True, age=50))
    aged = tax_ie.compute(80_000, FilingStatus(married=True, is_paye_employee=True, age=70))
    assert approx(base.income_tax - aged.income_tax, 490.0)
