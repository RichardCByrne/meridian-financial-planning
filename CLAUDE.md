# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Repo: https://github.com/RichardCByrne/meridian-financial-planning

Meridian is a single-repo financial planning app for Ireland with an in-house tax/pension engine (Budget 2026). FastAPI + SQLAlchemy backend, Vite + React 19 + TypeScript frontend. Local dev uses SQLite; production runs on Cloud Run with **Neon** serverless Postgres (free tier, autosuspends on idle) and Firebase Hosting for the static frontend. Cloud SQL is documented as a one-secret swap in `DEPLOY.md` Appendix A but not the default.

The project is organised as numbered phases (1–13 done; Phase 14 = AI walkthrough is next), but **tests are grouped by scope/functionality, not by phase**. Backend tests live under `backend/app/tests/test_<area>.py` — e.g. `test_pension.py`, `test_state_pension.py`, `test_child_benefit.py`, `test_liabilities.py`, `test_disposal_tax.py`, `test_goals.py`, `test_scenarios.py`, `test_plan_io.py`, `test_auth.py`, `test_invites_members.py`, `test_tax_config.py`, `test_cat_estate.py`, `test_montecarlo.py`, `test_plan_settings.py` — plus pure engine-level unit tests (`test_tax_ie.py`, `test_pension_ie.py`, `test_simulator.py`, `test_engine_edge_cases.py`, `test_schema_validation.py`). Test count target: keep `pytest` green (currently 211/211).

## Commands

Dev runner (starts backend on :8000 and frontend on :5173 with proxy):

```powershell
.\dev.ps1
```

The script uses `fnm` to switch to the latest installed Node LTS (`fnm use lts-latest`).

Backend (from `backend/`, venv at `.venv`):

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000 --host 127.0.0.1
.\.venv\Scripts\python -m pytest                        # full suite
.\.venv\Scripts\python -m pytest app/tests/test_montecarlo.py -v   # single file
.\.venv\Scripts\python -m pytest -k montecarlo -v       # by keyword
.\.venv\Scripts\python -m ruff check app                # lint
```

Frontend (from `frontend/`):

```powershell
npm run dev       # vite dev server, proxies /api → :8000
npm run lint      # tsc --noEmit (this is the lint step CI runs)
npm run build     # tsc -b && vite build
```

CI (`.github/workflows/test.yml`) runs pytest + `pip-audit` on the backend and `tsc --noEmit` + `vite build` + `npm audit` on the frontend. Match these before claiming green.

## Architecture

### Backend layering

`backend/app/` follows a strict pure-engine ↔ ORM-layer split:

- **`engine/`** — pure functions, no SQLAlchemy. The simulator takes domain dataclasses (`PersonInput`, `IncomeInput`, etc. defined in `simulator.py`), not ORM rows. This is the layer to touch for any tax/pension/projection logic change.
  - `tax_ie.py` — income tax bands, USC, PRSI. Driven by a `TaxConfig` dataclass. Exports `progressive_tax(amount, bands)` — generic `(upper, rate)` band walker reused by `usc` here and by `lump_sum_tax` in `pension_ie.py`.
  - `pension_ie.py` — age-based contribution caps (€115k earnings cap), lump-sum bands (€200k tax-free / next €300k @ 20% / above @ marginal), ARF imputed drawdown %.
  - `simulator.py` — year-by-year orchestration: age people → grow assets → income → tax → expenses → liquidate to cover shortfalls → amortise liabilities → goals → emit `YearRow`. Per-asset simulator state lives in a single `dict[int, AssetState]` (`AssetState` is a mutable dataclass with `kind`/`balance`/`growth`/`basis`/`acquired`/`owner`); synthetic ids `-1` (cash), `-1000-pid` (PRSA), `-2000-pid` (ARF) are reserved for implicit wrappers the simulator auto-creates. `YearRow` exposes both `net_worth` (raw total) and `accessible_net_worth` (net worth minus PRSA/occupational/AVC balances of pre-retirement owners — ARFs stay accessible). `net_worth`-kind goals are graded against `accessible_net_worth` so a high pre-retirement pension balance can't falsely satisfy a liquid-wealth target.
  - `liquidation.py` — `LIQUIDATION_ORDER` plus `withdraw_with_tax` which applies CGT / ETF exit tax at disposal.
  - `cat_ie.py` — Capital Acquisitions Tax / inheritance modelling (Phase 12).
  - `montecarlo.py` — wraps `simulate()` with N runs and per-asset Gaussian shocks (σ: equities/ETF 12%, pension 10%, property 6%, cash 0%) plus inflation/earnings-growth shocks. Returns p5/p10/p25/p50/p75/p90/p95 net-worth bands and shortfall probability. Uses `YearRow.had_shortfall: bool` (typed flag, not a `notes` string-grep).
  - `scenario.py` — applies JSON-Patch overrides to `PlanInput` before `simulate()`. Uses `dataclasses.replace(plan, ...)` so unspecified `PlanInput` fields (bequests, tax_config, filing_status) survive — do NOT switch back to explicit `PlanInput(...)` reconstruction.
  - `tax_config.py` — the `TaxConfig` dataclass that parameterises everything in `tax_ie.py`. `app/config/tax_ie_2026.py` defines the seeded `IRELAND_2026_OFFICIAL` instance. Exports `resolve(tax_config: TaxConfig | None) -> TaxConfig` — the single defaulting helper used by every engine module (do not re-implement per-module `_config` shims).

- **`models/__init__.py`** — every SQLAlchemy ORM table in one file (`Plan`, `Person`, `IncomeSource`, `Expense`, `Asset`, `Liability`, `Goal`, `Scenario`, `Bequest`, `Assumptions`, `User`, `PlanMember`, `PlanInvite`, `TaxConfigRow`). Pension wrappers/ARFs are `Asset` rows with specific `kind` values; the simulator auto-creates implicit ones.

- **`routers/`** — FastAPI routers, one per resource. Every endpoint depends on `get_current_user` and gates writes via `require_role("editor"|"owner")` from `auth.py`. Shared `routers/_helpers.py::get_or_404(Model, pk, db, name=)` replaces the per-router `_X_or_404` pattern.

- **`schemas/`** — Pydantic v2 DTOs. Keep request/response shapes here; never leak ORM objects through the API.

- **`services/serialisation.py`** — converts ORM rows → engine dataclasses for projections.

- **`config/tax_ie_2026.py`** — single source of truth for Budget 2026 numbers. Seeded into `tax_configs` table on app startup (lifespan hook in `main.py`).

### Auth

`backend/app/auth.py` has two modes:

- **Dev** (`MERIDIAN_DEV_AUTH=true`, the default): every request resolves to a seeded `dev-local` user. No Firebase project needed. CI runs in this mode.
- **Prod** (`MERIDIAN_DEV_AUTH=false`): verifies Firebase ID tokens via firebase-admin (`FIREBASE_SERVICE_ACCOUNT_PATH`).

Authorisation is `PlanMember` rows with `viewer < editor < owner`. `require_plan_access` returns **404 (not 403)** for non-members, deliberately, to avoid leaking plan IDs.

### Schema migrations

Two-track:

- **Production**: Alembic. The Dockerfile entrypoint runs `alembic upgrade head` before serving.
- **Local dev**: `_apply_lightweight_migrations()` in `main.py` lifespan hook — `Base.metadata.create_all` plus a series of idempotent `ALTER TABLE` statements that bridge pre-Alembic SQLite files. After patching it `alembic stamp head` so future migrations apply cleanly.

When adding a new column on an existing table: add it to the model, write an Alembic revision, **and** add an idempotent `ALTER TABLE` to `_apply_lightweight_migrations` so existing dev SQLite files don't break.

### Frontend

- `src/api/` — single typed client (`client.ts`), shared `types.ts`, react-query hooks (`hooks.ts`).
- `src/pages/PlanEditor.tsx` — the tabbed editor; each tab is a "pane" under `pages/panes/` (`PeoplePane`, `IncomePane`, `AssetsPane`, `LetsSeePane`, etc.). To add a new editable concept, mirror an existing pane.
- `src/auth/` — Firebase web SDK wrapper with the same dev-mode bypass (`VITE_DEV_AUTH=true`).
- State: react-query for server state, zustand for any client-only state. No Redux.
- Charts: recharts. The probability fan-chart in `LetsSeePane` is stacked Area layers p5→p25→p75→p95 with a median line overlaid.

### Projections cache

`/api/plans/{id}/projection/montecarlo?n=200` is cached for 60s server-side because each call runs N independent simulations. Don't remove that cache without thinking through cost.

## Conventions worth knowing

- **Money is float, not Decimal.** Tax engine constants live in `TaxConfig`; never hardcode rates inside routers or simulator branches.
- **Never put ORM imports inside `engine/`.** If you need a new piece of plan data in the simulator, add it to the relevant `*Input` dataclass and map it in `services/serialisation.py` AND `routers/projections.py::_load_plan_input` (the ORM→dataclass copy is still by-hand — see deferred refactor below).
- Pension wrappers and ARFs are not separate tables — they are `Asset` rows with `kind` values like `prsa` / `occupational_pension` / `arf`. The simulator auto-creates them via `_person_pension_target` / `_person_arf_target` / `_cash_target` on first need; do not duplicate that logic inline.
- The API/integration tests (e.g. `test_auth.py`, `test_scenarios.py`, `test_plan_io.py`, `test_tax_config.py`, `test_cat_estate.py`, `test_invites_members.py`, `test_plan_settings.py`, `test_montecarlo.py`) are *integration-ish*: they spin up the FastAPI app against a dedicated `backend/test_meridian.db` SQLite file (forced by `backend/conftest.py` setting `DATABASE_URL` before any `app.*` import) and exercise endpoints. An autouse `_clean_db` fixture in `app/tests/conftest.py` wipes every data table after each test — that wipe targets the test DB only, NOT the dev `meridian.db`. Do not remove the root `backend/conftest.py` or the dev DB will get nuked on every `pytest` run. Engine tests are pure unit tests against the dataclasses.
- `claims_rent_credit` and `filing_status` are recent (Phase 14 prep) — cohabiting couples are taxed individually under Irish law, so don't infer married filing from "2 people in plan".
- Use `app.db.utcnow()` for created/updated timestamps, never `datetime.utcnow()` (deprecated). The helper returns a naive UTC datetime so existing `DateTime` columns work unchanged.
- SQLAlchemy: prefer `db.execute(select(...))` / `update(...)` over the legacy `db.query()` API. Production code is migrated; older test helpers still use `db.query` and that's OK.

### Deferred refactors

Two architectural items intentionally not done — both have explicit triggers documented in commit history. Don't pre-emptively pick them up unless you hit the trigger.

- **`_load_plan_input` introspection.** The 130-line ORM→dataclass mapping in `routers/projections.py` is mechanical but explicit. Replacing it with a `dataclasses.fields()` introspection helper saves lines but moves rename-mismatch failures from write-time to runtime. Trigger to revisit: when a new entity gets added, or column counts cross ~20 per dataclass.
- **`simulate()` per-phase pure functions.** ~590 lines orchestrating 7 phases over shared mutable state (`states` dict, `liability_balances`, `retired_persons`, etc.). Splitting into `(SimState, year) -> SimState` phase functions is the right end state but needs ~600 lines of rewriting across 30 mutation sites with no current pain. Trigger to revisit: first time a new feature needs to run *between* existing phases and can't be localised.
