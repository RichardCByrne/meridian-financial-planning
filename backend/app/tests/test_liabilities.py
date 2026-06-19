"""Liabilities: mortgage/loan amortisation, overpayment, debt-service flow,
plus time-keyed adjustments (rate steps / overpayment changes / lump sums)."""

from datetime import date

from fastapi.testclient import TestClient

from app.engine.simulator import (
    AssetInput,
    AssumptionsInput,
    LiabilityAdjustmentInput,
    LiabilityInput,
    PersonInput,
    PlanInput,
    simulate,
)
from app.main import app


def _person() -> PersonInput:
    return PersonInput(id=1, name="Aoife", dob=date(1990, 1, 1), is_primary=True, life_expectancy=90)


def _amortised(principal: float, rate: float, term: int) -> float:
    if rate <= 0:
        return principal / term
    r = rate / 12.0
    return principal * r / (1 - (1 + r) ** -term)


def _mortgage_plan(rate: float, adjustments: list[LiabilityAdjustmentInput]) -> PlanInput:
    """4-year projection, 200k / 25y mortgage at `rate`, starting 2026."""
    return PlanInput(
        base_year=2026, projection_years=4,
        people=[_person()], incomes=[], expenses=[],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=200_000, growth_rate=0.0, cost_basis=0.0)],
        liabilities=[
            LiabilityInput(
                id=1, name="Mortgage", kind="mortgage", principal=200_000.0,
                interest_rate=rate, term_months=300, start_year=2026,
                monthly_payment=_amortised(200_000.0, rate, 300),
                adjustments=adjustments,
            )
        ],
        assumptions=AssumptionsInput(inflation_rate=0.0),
    )


def test_mortgage_amortisation_zero_rate_is_straight_line():
    """0% mortgage: 240k over 240 months = 1000/mo = 12k/yr. Balance falls by 12k."""
    plan = PlanInput(
        base_year=2026,
        projection_years=3,
        people=[_person()],
        incomes=[],
        expenses=[],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=100_000, growth_rate=0.0, cost_basis=0.0)],
        liabilities=[
            LiabilityInput(
                id=1, name="Mortgage", kind="mortgage", principal=240_000.0,
                interest_rate=0.0, term_months=240, start_year=2026, monthly_payment=1_000.0,
            )
        ],
        assumptions=AssumptionsInput(inflation_rate=0.0),
    )
    rows = simulate(plan)
    assert abs(rows[0].liability_balances[1] - 228_000.0) < 0.5
    assert abs(rows[1].liability_balances[1] - 216_000.0) < 0.5
    assert abs(rows[0].expenses_by_category["debt_service"] - 12_000.0) < 0.5


def test_mortgage_with_interest_amortises_correctly():
    """Standard 200k @ 4% / 25y mortgage. First-year balance well known."""
    # Standard payment for 200k @ 4%/25y ≈ 1,055.67
    payment = 200_000 * (0.04 / 12) / (1 - (1 + 0.04 / 12) ** -300)
    plan = PlanInput(
        base_year=2026,
        projection_years=2,
        people=[_person()],
        incomes=[],
        expenses=[],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=20_000, growth_rate=0.0, cost_basis=0.0)],
        liabilities=[
            LiabilityInput(
                id=1, name="Mortgage", kind="mortgage", principal=200_000.0,
                interest_rate=0.04, term_months=300, start_year=2026,
                monthly_payment=payment,
            )
        ],
        assumptions=AssumptionsInput(),
    )
    rows = simulate(plan)
    # After 12 payments, balance ≈ 195,245 (closed-form amortisation).
    assert 195_000 < rows[0].liability_balances[1] < 195_500
    assert rows[0].debt_outstanding == rows[0].liability_balances[1]
    # Net worth subtracts debt.
    assert rows[0].net_worth < rows[0].asset_balances[1]


def test_overpayment_shortens_loan_and_reduces_balance():
    """€200/mo extra capital paydown gets the balance lower year-by-year vs zero overpayment."""
    payment = 200_000 * (0.04 / 12) / (1 - (1 + 0.04 / 12) ** -300)
    base_plan = PlanInput(
        base_year=2026, projection_years=5,
        people=[_person()], incomes=[], expenses=[],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=100_000, growth_rate=0.0, cost_basis=0.0)],
        liabilities=[
            LiabilityInput(
                id=1, name="Mortgage", kind="mortgage", principal=200_000.0,
                interest_rate=0.04, term_months=300, start_year=2026,
                monthly_payment=payment,
            )
        ],
        assumptions=AssumptionsInput(inflation_rate=0.0),
    )
    overpay_plan = PlanInput(
        base_year=2026, projection_years=5,
        people=[_person()], incomes=[], expenses=[],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=100_000, growth_rate=0.0, cost_basis=0.0)],
        liabilities=[
            LiabilityInput(
                id=1, name="Mortgage", kind="mortgage", principal=200_000.0,
                interest_rate=0.04, term_months=300, start_year=2026,
                monthly_payment=payment, monthly_overpayment=200.0,
            )
        ],
        assumptions=AssumptionsInput(inflation_rate=0.0),
    )
    base_rows = simulate(base_plan)
    over_rows = simulate(overpay_plan)
    # Year-1 balance must be lower with overpayment.
    assert over_rows[0].liability_balances[1] < base_rows[0].liability_balances[1]
    # Approx €200/mo × 12 = €2,400 extra capital paid in year 1 (compounding effect
    # rounds it up slightly via reduced interest).
    diff = base_rows[0].liability_balances[1] - over_rows[0].liability_balances[1]
    assert 2_400 < diff < 2_500
    # Debt service line item rises by the overpayment amount.
    assert (
        over_rows[0].expenses_by_category["debt_service"]
        - base_rows[0].expenses_by_category["debt_service"]
    ) == 200 * 12


def test_negative_overpayment_clamped_to_zero():
    """Negative monthly_overpayment must not extend the loan or grow the balance."""
    payment = 200_000 * (0.04 / 12) / (1 - (1 + 0.04 / 12) ** -300)
    base_plan = PlanInput(
        base_year=2026, projection_years=2,
        people=[_person()], incomes=[], expenses=[],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=50_000, growth_rate=0.0, cost_basis=0.0)],
        liabilities=[
            LiabilityInput(
                id=1, name="Mortgage", kind="mortgage", principal=200_000.0,
                interest_rate=0.04, term_months=300, start_year=2026,
                monthly_payment=payment,
            )
        ],
        assumptions=AssumptionsInput(inflation_rate=0.0),
    )
    neg_plan = PlanInput(
        base_year=2026, projection_years=2,
        people=[_person()], incomes=[], expenses=[],
        assets=[AssetInput(id=1, name="Cash", kind="cash", value=50_000, growth_rate=0.0, cost_basis=0.0)],
        liabilities=[
            LiabilityInput(
                id=1, name="Mortgage", kind="mortgage", principal=200_000.0,
                interest_rate=0.04, term_months=300, start_year=2026,
                monthly_payment=payment, monthly_overpayment=-100.0,
            )
        ],
        assumptions=AssumptionsInput(inflation_rate=0.0),
    )
    base_rows = simulate(base_plan)
    neg_rows = simulate(neg_plan)
    assert abs(neg_rows[0].liability_balances[1] - base_rows[0].liability_balances[1]) < 0.5


# ----- Time-keyed adjustments -----
# Year index: 2026=0, 2027=1, 2028=2, 2029=3.


def test_rate_step_raises_payment_when_it_takes_effect():
    """Rate jumps 2%→6% in 2028: payment re-amortises higher; identical before."""
    base = simulate(_mortgage_plan(0.02, []))
    stepped = simulate(_mortgage_plan(
        0.02, [LiabilityAdjustmentInput(id=1, kind="rate", effective_year=2028, value=0.06)]
    ))
    ds = "debt_service"
    # Pre-step years identical.
    assert abs(stepped[1].expenses_by_category[ds] - base[1].expenses_by_category[ds]) < 1.0
    # From 2028 the stepped plan pays a materially higher monthly amount.
    assert stepped[2].expenses_by_category[ds] > base[2].expenses_by_category[ds] + 1_000
    assert stepped[3].expenses_by_category[ds] > base[3].expenses_by_category[ds] + 1_000


def test_lump_sum_drops_balance_in_effective_year_only():
    """€20k lump in 2027 cuts the outstanding balance by >20k (capital + saved interest)."""
    base = simulate(_mortgage_plan(0.04, []))
    lump = simulate(_mortgage_plan(
        0.04, [LiabilityAdjustmentInput(id=1, kind="lump_sum", effective_year=2027, value=20_000.0)]
    ))
    # 2026 (before the lump) identical.
    assert abs(lump[0].liability_balances[1] - base[0].liability_balances[1]) < 0.5
    # 2027 balance falls by more than the lump (less interest accrues on smaller balance).
    diff = base[1].liability_balances[1] - lump[1].liability_balances[1]
    assert diff > 20_000.0


def test_overpayment_adjustment_activates_from_its_year():
    """Overpayment of €300/mo starting 2028: debt-service rises by 300×12 then on."""
    base = simulate(_mortgage_plan(0.04, []))
    op = simulate(_mortgage_plan(
        0.04, [LiabilityAdjustmentInput(id=1, kind="overpayment", effective_year=2028, value=300.0)]
    ))
    ds = "debt_service"
    # 2027 untouched.
    assert abs(op[1].liability_balances[1] - base[1].liability_balances[1]) < 0.5
    # 2028 debt-service rises by exactly the annual overpayment.
    assert abs((op[2].expenses_by_category[ds] - base[2].expenses_by_category[ds]) - 3_600) < 1.0


def test_liability_adjustments_round_trip_through_api():
    """Create a mortgage with adjustments; read it back with the same set."""
    with TestClient(app) as client:
        pid = client.post(
            "/api/plans",
            json={"name": "Adj household", "base_year": 2026, "projection_years": 10},
        ).json()["id"]
        created = client.post(
            f"/api/plans/{pid}/liabilities",
            json={
                "name": "Mortgage", "kind": "mortgage", "principal": 200_000,
                "interest_rate": 0.02, "term_months": 300, "start_year": 2026,
                "adjustments": [
                    {"kind": "rate", "effective_year": 2031, "value": 0.055},
                    {"kind": "lump_sum", "effective_year": 2028, "value": 15_000},
                ],
            },
        )
        assert created.status_code == 201
        body = created.json()
        assert len(body["adjustments"]) == 2
        kinds = {a["kind"] for a in body["adjustments"]}
        assert kinds == {"rate", "lump_sum"}
        # PATCH replaces the full set.
        lid = body["id"]
        patched = client.patch(
            f"/api/liabilities/{lid}",
            json={"adjustments": [{"kind": "overpayment", "effective_year": 2030, "value": 250}]},
        ).json()
        assert len(patched["adjustments"]) == 1
        assert patched["adjustments"][0]["kind"] == "overpayment"
