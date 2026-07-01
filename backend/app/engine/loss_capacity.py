"""Capacity for loss — the largest one-off market shock a plan can absorb and
still meet its objectives (no shortfall over the horizon).

Adviser "capacity for loss" question: if markets crashed today, how big a hit
could the portfolio take before the plan stops working? We answer it by
applying an instantaneous haircut to the market-exposed assets at the base year
and binary-searching the largest fraction that still avoids any shortfall.

Pure function — no ORM, no numpy. Uses `simulate()` and the typed
`YearRow.had_shortfall` flag.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.engine.simulator import PlanInput, YearRow, simulate

# Market-exposed asset kinds a crash would hit. Cash / deposits are excluded
# (no market risk); property and pensions are included — a broad market shock
# hits them too.
MARKET_KINDS: frozenset[str] = frozenset(
    {
        "investment_unwrapped",
        "etf_fund",
        "investment_bond",
        "prsa",
        "occupational_pension",
        "arf",
        "property_primary",
        "property_btl",
    }
)


@dataclass
class LossCapacityResult:
    # Sum of market-exposed asset values at the base year.
    investable_base: float
    # Largest one-off loss (euros) the plan can absorb with no shortfall.
    max_absorbable_loss: float
    # Same as a fraction of the investable base (0.0–1.0).
    max_absorbable_pct: float
    # True when the plan already shortfalls even with no shock (capacity 0).
    already_short: bool
    # First year a shortfall appears just past the capacity threshold (context).
    limiting_year: int | None


def _first_shortfall_year(rows: list[YearRow]) -> int | None:
    for r in rows:
        if r.had_shortfall:
            return r.year
    return None


def loss_capacity(
    plan: PlanInput, *, tolerance: float = 0.01, max_iter: int = 20
) -> LossCapacityResult:
    """Binary-search the largest instantaneous market haircut the plan survives.

    `tolerance` is the fraction precision to stop at; `max_iter` caps the number
    of simulate() calls.
    """
    investable_base = sum(
        a.value for a in plan.assets if a.kind in MARKET_KINDS and a.value > 0
    )

    def survives(haircut: float) -> tuple[bool, list[YearRow]]:
        shocked = [
            replace(a, value=a.value * (1.0 - haircut)) if a.kind in MARKET_KINDS else a
            for a in plan.assets
        ]
        rows = simulate(replace(plan, assets=shocked))
        return (not any(r.had_shortfall for r in rows)), rows

    ok0, rows0 = survives(0.0)
    if not ok0:
        return LossCapacityResult(
            investable_base, 0.0, 0.0, already_short=True,
            limiting_year=_first_shortfall_year(rows0),
        )
    if investable_base <= 0:
        # Nothing to lose (no market assets) and no shortfall — infinite capacity;
        # report the whole (zero) base as absorbable.
        return LossCapacityResult(0.0, 0.0, 1.0, already_short=False, limiting_year=None)

    ok_full, _ = survives(1.0)
    if ok_full:
        return LossCapacityResult(
            investable_base, investable_base, 1.0, already_short=False, limiting_year=None,
        )

    # lo survives, hi fails. Track the first shortfall year at the failing side.
    lo, hi = 0.0, 1.0
    limiting_year: int | None = None
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        ok, rows = survives(mid)
        if ok:
            lo = mid
        else:
            hi = mid
            limiting_year = _first_shortfall_year(rows)
        if hi - lo < tolerance:
            break

    return LossCapacityResult(
        investable_base=investable_base,
        max_absorbable_loss=investable_base * lo,
        max_absorbable_pct=lo,
        already_short=False,
        limiting_year=limiting_year,
    )
