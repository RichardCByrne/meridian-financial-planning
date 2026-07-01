"""Monte Carlo simulator — wraps simulate() with perturbed returns.

Two modes:

- **gaussian** (default): each run draws one persistent shock per asset growth
  rate and to the macro assumptions, modelling regime differences ("what if
  real returns end up consistently higher or lower than expected?"). Shocks are
  normal, so tails are thin.

- **historic**: each run draws a *year-by-year* return path by block-bootstrapping
  an illustrative historical annual-return series per asset class. This captures
  the fat tails and, crucially, the sequence-of-returns risk (a crash early in
  retirement hurts far more than the same crash late) that a single normal draw
  understates. Shocks are centred on each series' own mean, so the plan's assumed
  growth stays the central expectation — only the dispersion and ordering come
  from history.

Both modes return the same p5…p95 net-worth bands and shortfall probability, so
the frontend fan-chart is identical.

No numpy dependency — percentiles use linear interpolation on sorted lists.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from app.engine.simulator import PlanInput, simulate

# Annual volatility (σ) by asset kind — gaussian mode.
SIGMA_BY_KIND: dict[str, float] = {
    "cash": 0.0,
    "deposit": 0.005,
    "investment_unwrapped": 0.12,
    "etf_fund": 0.12,
    "investment_bond": 0.12,
    "prsa": 0.10,
    "occupational_pension": 0.10,
    "arf": 0.10,
    "property_primary": 0.06,
    "property_btl": 0.07,
}

SIGMA_INFLATION = 0.008
SIGMA_EARNINGS_GROWTH = 0.008

# Asset kind → broad return class for the historic bootstrap. Cash/deposit are
# omitted (no market shock).
KIND_TO_CLASS: dict[str, str] = {
    "investment_unwrapped": "equity",
    "etf_fund": "equity",
    "investment_bond": "equity",
    "prsa": "equity",
    "occupational_pension": "equity",
    "arf": "equity",
    "property_primary": "property",
    "property_btl": "property",
}

# Illustrative representative annual real-return series per class (30 entries).
# NOT sourced market data — a plausible dispersion/sequence including drawdowns.
# Only the deviations from each series' mean are used (see _historic_shocks), so
# the absolute level doesn't bias the projection.
HISTORICAL_RETURNS: dict[str, list[float]] = {
    "equity": [
        0.18, 0.12, -0.05, 0.22, 0.08, -0.38, 0.26, 0.15, 0.02, 0.16,
        0.32, 0.13, -0.10, 0.11, 0.24, -0.02, 0.19, -0.44, 0.28, 0.14,
        0.06, 0.21, -0.18, 0.09, 0.25, 0.17, -0.06, 0.23, 0.10, 0.20,
    ],
    "property": [
        0.08, 0.05, 0.02, 0.10, 0.06, -0.18, 0.03, 0.07, 0.04, 0.09,
        0.12, 0.05, -0.05, 0.06, 0.08, 0.01, 0.07, -0.12, 0.09, 0.05,
        0.03, 0.08, -0.08, 0.04, 0.10, 0.06, 0.00, 0.07, 0.05, 0.06,
    ],
}

_BLOCK_LEN = 5  # block-bootstrap length — preserves short-run autocorrelation.


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
    mode: str = "gaussian"


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
    """Gaussian mode — a shallow copy of `plan` with one randomised growth rate
    per asset plus macro shocks, drawn once for the whole run."""
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


def _class_means() -> dict[str, float]:
    return {cls: sum(vals) / len(vals) for cls, vals in HISTORICAL_RETURNS.items()}


def _historic_shocks(
    rng: random.Random, n_years: int, means: dict[str, float]
) -> list[dict[str, float]]:
    """Block-bootstrap a per-year `{asset_kind: growth_delta}` path from the
    historical series. Deltas are centred on each class' mean, so the run's
    central expectation matches the plan's assumed growth while dispersion and
    sequence come from history. One shared time index per year drives every
    class, preserving cross-asset correlation within a historical year."""
    series_len = len(next(iter(HISTORICAL_RETURNS.values())))
    idxs: list[int] = []
    while len(idxs) < n_years:
        start = rng.randrange(series_len)
        for k in range(_BLOCK_LEN):
            idxs.append((start + k) % series_len)
    idxs = idxs[:n_years]

    shocks: list[dict[str, float]] = []
    for t in range(n_years):
        i = idxs[t]
        year_shock: dict[str, float] = {}
        for kind, cls in KIND_TO_CLASS.items():
            year_shock[kind] = HISTORICAL_RETURNS[cls][i] - means[cls]
        shocks.append(year_shock)
    return shocks


def run(
    plan: PlanInput, n_runs: int = 200, seed: int | None = None, mode: str = "gaussian"
) -> MonteCarloResult:
    """Execute `n_runs` simulations and return percentile bands.

    mode="gaussian" (default) perturbs each run's growth once; mode="historic"
    block-bootstraps a year-by-year return path from the historical series.
    """
    rng = random.Random(seed)
    n_years = plan.projection_years
    historic = mode == "historic"
    means = _class_means() if historic else {}

    # nw_matrix[year_idx] accumulates net worths across all runs for that year
    nw_matrix: list[list[float]] = [[] for _ in range(n_years)]
    shortfall_count = 0

    for _ in range(n_runs):
        if historic:
            rows = simulate(plan, annual_shocks=_historic_shocks(rng, n_years, means))
        else:
            rows = simulate(_perturb(plan, rng))
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
        mode=mode,
    )
