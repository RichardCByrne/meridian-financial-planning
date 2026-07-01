# Testing Gap Analysis — Meridian

_Date: 2026-07-01 · Baseline: 291 backend tests, 94% backend coverage (5412 stmts, 328 missed) · Frontend: 0 tests_

## Summary

Backend is well covered (94%) with a strong pure-engine test base. The **frontend has no test tooling and no tests at all**, and a cluster of backend CRUD routers leave their write/authz paths uncovered. Below: findings ranked by value, each with a level-of-effort estimate.

Effort scale: **S** = <½ day · **M** = ½–2 days · **L** = 2–5 days · **XL** = >1 week.

---

## Findings

### 1. Frontend has zero tests 🔴 Critical — Effort: L (bootstrap S, meaningful coverage L)

- 68 TS/TSX files, 16 editor panes, typed API client, react-query hooks, recharts fan-chart, Firebase auth wrapper — **no test runner** (no Vitest/Jest/Playwright in `frontend/package.json`).
- `npm run lint` is only `tsc --noEmit`. Type-checking is not behaviour testing.
- Highest-risk untested logic:
  - `src/api/client.ts` — error→message mapping. Project rule requires generic user-facing errors (enumeration risk); nothing enforces it in test.
  - `src/api/hooks.ts` — react-query cache/mutation behaviour.
  - `LetsSeePane` fan-chart — stacked Area layer order (p5→p25→p75→p95) + median overlay; silent visual regression risk.
  - Pane form validation across 16 panes.
- **Move:** add Vitest + React Testing Library (bootstrap = S). Start narrow: `client.ts` error-mapping unit test + one smoke render per pane. Add Playwright e2e for plan→projection happy path later.

### 2. CRUD router write/authz paths under-covered 🟠 High — Effort: S–M

No dedicated router-CRUD test files for `people / income / expenses / assets / assumptions`; exercised only indirectly. Uncovered lines are the **write endpoints and authz guards** (`require_role`, `get_or_404`, 403/404 branches).

| Router | Coverage | Missing |
|--------|----------|---------|
| `assumptions.py` | **35%** | GET auto-create, PUT insert-vs-update, viewer/editor gates — near-total |
| `goals.py` | 65% | update/delete + 404 paths |
| `expenses.py` | 68% | update/delete + guards |
| `people.py` | 68% | update/delete + guards |
| `income.py` | 71% | update/delete + guards |
| `assets.py` | 79% | error paths |

- `assumptions.py` (35%) is worst and highest-value: it feeds engine inputs (growth/inflation) yet both endpoints and all authz gates are untested. One small `test_assumptions.py` gives the biggest coverage jump per line written (**S**).
- Broken `require_role` = silent privilege escalation. These are the security boundary. Full sweep of all five routers = **M**.

### 3. Plan-import cross-person re-linking untested 🟠 High (correctness) — Effort: S

- `services/serialisation.py` lines 213–225 uncovered: bequest/benefit person-link resolution on plan import.
- Bequest branch **silently drops** the row when `from_id is None` (`if from_id is not None:`). `test_plan_io` round-trip does not cover bequests/benefits carrying person links → potential silent data loss on import, currently invisible.
- **Move:** add a plan export→import round-trip test with a bequest and a benefit that reference people; assert they survive.

### 4. Simulator edge branches 🟡 Medium — Effort: M

- `engine/simulator.py` — 94% but 733 stmts, 43 uncovered. Missing lines cluster in liquidation shortfall paths (952–967, 1220–1241) and pension edges — the money-correctness branches.
- Not a hole, but worth **targeted edge tests** (forced shortfall triggering property-preservation, pension cap boundaries) rather than blanket coverage chasing.

### 5. Smaller engine/router gaps 🟢 Low — Effort: S each

- `engine/bik_ie.py` 88% (lines 62, 67, 96), `engine/liquidation.py` 84% (74, 85, 90–92), `routers/tax_configs.py` 69% (delete/validation paths). Opportunistic — fold into related work.

---

## Recommended order (value × effort)

1. **`test_assumptions.py`** — S — kills the 35% hole, covers an engine input + authz gates.
2. **Router CRUD authz sweep** (people/income/expenses/assets/goals) — M — asserts 403/404 + editor gates; locks the security boundary.
3. **Frontend Vitest + RTL bootstrap** — S bootstrap / L for real coverage — biggest strategic gap; start with `client.ts` error mapping + pane smoke renders.
4. **Plan-io bequest/benefit round-trip test** — S — catches the silent-drop bug in finding 3.
5. **Simulator edge tests** — M — liquidation/pension boundaries.
6. **Playwright e2e happy path** — M — after frontend unit base exists.

---

## Notes

- Backend coverage measured via `pytest-cov` (installed then removed; not added to deps).
- All findings from static + coverage analysis only. No code changed.
