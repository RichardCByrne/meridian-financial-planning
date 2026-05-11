"""Monte Carlo simulator — wraps simulate() with perturbed growth assumptions.

Runs N independent simulations, each time drawing per-run shocks to every
asset's growth rate and to the household's inflation and earnings-growth
assumptions. Returns per-year net-worth percentile bands and the probability
of at least one shortfall occurring.

Design notes
------------
Shocks are drawn once per run (not per year), modelling persistent regime
differences rather than year-by-year noise. This is the approach most
financial-planning tools use and is interpretable as "what if real returns
end up being consistently higher or lower than expected?"

Cash and deposit assets receive no shock (σ=0). Equity and mixed funds
receive σ ≈ 10–12%. No numpy dependency — percentiles use linear
interpolation on sorted lists.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from app.engine.simulator import PlanInput, simulate

# Annual volatility (σ) by asset kind.
SIGMA_BY_KIND: dict[str, float] = {
    "cash": 0.0,
    "deposit": 0.005,
    "investment_unwrapped": 0.12,
    "etf_fund": 0.12,
    "prsa": 0.10,
    "occupational_pension": 0.10,
    "arf": 0.10,
    "property_primary": 0.06,
    "property_btl": 0.07,
}

SIGMA_INFLATION = 0.008
SIGMA_EARNINGS_GROWTH = 0.008


@dataclass
class MonteCarloYearResult:
    year: int
    p5: float
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    p95: float


@dataclass
class MonteCarloResult:
    runs: int
    years: list[MonteCarloYearResult]
    shortfall_probability: float
    median_final_net_worth: float


def _percentile(sorted_vals: list[float], p: float) -> float:
    """Linear-interpolation percentile on a sorted list. `p` is in [0, 100]."""
    if not sorted_vals:
        return 0.0
    n = len(sorted_vals)
    idx = p / 100.0 * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return sorted_vals[lo] + frac * (sorted_vals[hi] - sorted_vals[lo])


def _perturb(plan: PlanInput, rng: random.Random) -> PlanInput:
    """Return a shallow copy of `plan` with randomised growth rates."""
    new_assets = []
    for asset in plan.assets:
        sigma = SIGMA_BY_KIND.get(asset.kind, 0.08)
        if sigma == 0.0:
            new_assets.append(asset)
        else:
            delta = rng.gauss(0.0, sigma)
            new_rate = max(-0.5, min(2.0, asset.growth_rate + delta))
            new_assets.append(replace(asset, growth_rate=new_rate))

    new_assumptions = replace(
        plan.assumptions,
        inflation_rate=max(0.0, plan.assumptions.inflation_rate + rng.gauss(0.0, SIGMA_INFLATION)),
        earnings_growth=max(
            -0.1, plan.assumptions.earnings_growth + rng.gauss(0.0, SIGMA_EARNINGS_GROWTH)
        ),
    )
    return replace(plan, assets=new_assets, assumptions=new_assumptions)


def run(plan: PlanInput, n_runs: int = 200, seed: int | None = None) -> MonteCarloResult:
    """Execute `n_runs` perturbed simulations and return percentile bands."""
    rng = random.Random(seed)
    n_years = plan.projection_years

    # nw_matrix[year_idx] accumulates net worths across all runs for that year
    nw_matrix: list[list[float]] = [[] for _ in range(n_years)]
    shortfall_count = 0

    for _ in range(n_runs):
        perturbed = _perturb(plan, rng)
        rows = simulate(perturbed)
        run_had_shortfall = False
        for yr_idx, row in enumerate(rows[:n_years]):
            nw_matrix[yr_idx].append(row.net_worth)
            if row.had_shortfall:
                run_had_shortfall = True
        if run_had_shortfall:
            shortfall_count += 1

    year_results: list[MonteCarloYearResult] = []
    for yr_idx in range(n_years):
        vals = sorted(nw_matrix[yr_idx])
        year_results.append(
            MonteCarloYearResult(
                year=plan.base_year + yr_idx,
                p5=round(_percentile(vals, 5), 2),
                p10=round(_percentile(vals, 10), 2),
                p25=round(_percentile(vals, 25), 2),
                p50=round(_percentile(vals, 50), 2),
                p75=round(_percentile(vals, 75), 2),
                p90=round(_percentile(vals, 90), 2),
                p95=round(_percentile(vals, 95), 2),
            )
        )

    return MonteCarloResult(
        runs=n_runs,
        years=year_results,
        shortfall_probability=round(shortfall_count / n_runs, 4) if n_runs > 0 else 0.0,
        median_final_net_worth=year_results[-1].p50 if year_results else 0.0,
    )
