# Meridian

**Financial planning for Ireland — with a tax/pension engine that actually knows the rules.**

Meridian is a personal-finance forecasting app built around an in-house Ireland 2026 tax & pension engine. Model your household 30+ years out, see how income tax, USC, PRSI, PRSA contributions, ARF drawdowns, CGT, ETF exit tax and CAT interact, and compare scenarios side-by-side with Monte Carlo probability bands.

Inspired by Voyant AdviserGo. Not affiliated with Voyant Inc.

**Repository:** https://github.com/RichardCByrne/meridian-financial-planning

---

## Why it exists

Most retail financial planners either ignore Irish tax entirely or apply a flat "effective rate" approximation. Meridian models the real thing:

- **Income tax bands & credits, USC, PRSI** per Budget 2026 — single-source-of-truth `TaxConfig` dataclass.
- **Age-based pension contribution caps** (15%–40%, €115k earnings cap) with PRSA/occupational wrapper auto-creation.
- **Retirement crystallisation**: 25% tax-free lump sum (with band logic — €200k free / next €300k @ 20% / above @ marginal) plus 75% ARF with imputed minimum drawdown (4%/5%/6%).
- **State pension** auto-injected at the configured age.
- **CGT, ETF exit tax, CAT/inheritance** on disposals and bequests.
- **Monte Carlo**: 200 (configurable 10–1,000) independent simulations with per-asset-class Gaussian shocks. Outputs p5/p10/p25/p50/p75/p90/p95 net-worth bands and a shortfall probability.

Tax knobs live in `backend/app/config/tax_ie_2026.py` — change a rate, re-run the year and every projection picks it up.

---

## What you can do with it

1. Create a **plan** for your household (base year, horizon, inflation/earnings-growth assumptions).
2. Add **people** with DOBs, retirement ages, pension contribution %, state-pension entitlement.
3. Add **income sources, expenses, assets** (cash / ETF / equities / property / pension wrappers / ARF), and **liabilities** (mortgages amortise year-by-year).
4. Add **goals** (net-worth-by-year, retirement-income, lump-sum events) and grade them against accessible net worth.
5. Define **scenarios** as JSON-Patch overlays on the base plan, and compare projections on one chart.
6. Toggle **Probability bands** on the Let's See chart for the Monte Carlo fan view.
7. Share plans with other users in `owner` / `editor` / `viewer` roles (Firebase Auth in prod, dev-auth bypass for local).

---

## Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.x, Pydantic v2, Alembic |
| Engine | Pure Python — no ORM imports, fully unit-testable |
| Database | SQLite (local dev), Neon serverless Postgres (prod, free tier) |
| Frontend | Vite, React 19, TypeScript, react-query, zustand, recharts |
| Auth | Firebase Auth (prod) / seeded dev user (local) |
| Hosting | Cloud Run (API) + Firebase Hosting (static frontend) |
| Tests | 132 pytest tests, `tsc --noEmit` + `vite build` + audits in CI |

---

## Quickstart

### Prerequisites
- **Python 3.11+** (CI + production run on 3.13)
- **Node.js 18+ with npm** (the dev runner uses `fnm` to pin Node LTS)

### First-time setup

```powershell
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -e ".[dev]"

# Frontend
cd ..\frontend
npm install
```

### Run

```powershell
.\dev.ps1
```

Starts FastAPI on `:8000` and Vite on `:5173` with `/api` proxied to the backend. Open http://localhost:5173.

OpenAPI docs: http://127.0.0.1:8000/docs

### Test

```powershell
cd backend
.\.venv\Scripts\python -m pytest -v        # ~5s, 184 tests

cd ..\frontend
npm run lint                               # tsc --noEmit
npm run build
```

---

## Try the golden-path demo (5 min)

1. Create plan **Murphy household** — base year 2026, 30 years.
2. **People** → `Liam`, DOB 1985-03-12, primary, retirement age 65.
3. **Income** → on Liam, `Software engineer`, employment, €80,000, start 2026, 3% escalation, 10% pension contribution.
4. **Expenses** → `Living` (basic, €24k, 2.5%), `Holidays` (discretionary, €5k, 2.5%), `Mortgage` (basic, €18k, 2026–2050).
5. **Assets** → `Current account` (cash, €15,000), `Investment ETF` (etf_fund, €50,000, 6% growth).
6. **Let's See** → switch chart modes, hover any year for the breakdown card, toggle **Probability bands** for the Monte Carlo fan.
7. **Assumptions** → bump inflation to 3%, save → curve and expense bars react.

---

## Project layout

```
meridian-financial-planning/
├── backend/                 # FastAPI + SQLAlchemy
│   ├── app/
│   │   ├── main.py          # app factory, lifespan, CORS, routers
│   │   ├── db.py            # engine, SessionLocal, utcnow()
│   │   ├── auth.py          # Firebase verify + dev bypass + role gates
│   │   ├── models/          # ORM (one file, all tables)
│   │   ├── schemas/         # Pydantic v2 DTOs
│   │   ├── routers/         # plans, people, assets, projections, scenarios, …
│   │   ├── engine/          # PURE — tax_ie, pension_ie, simulator, montecarlo, cat_ie, scenario
│   │   ├── services/        # ORM ↔ engine dataclass serialisation
│   │   ├── config/          # tax_ie_2026.py (seeded into DB on startup)
│   │   ├── alembic/         # production migrations
│   │   └── tests/           # test_phase1..13.py + engine unit tests
│   ├── pyproject.toml
│   └── meridian.db          # local SQLite, gitignored
├── frontend/                # Vite + React 19 + TypeScript
│   ├── src/
│   │   ├── api/             # typed client + react-query hooks
│   │   ├── pages/           # PlansList, PlanEditor, panes/*
│   │   ├── auth/            # Firebase web SDK + dev bypass
│   │   ├── components/      # shared UI
│   │   └── store/           # zustand client state
│   └── vite.config.ts
├── cloudbuild.yaml          # Cloud Run deploy pipeline
├── firebase.json            # Firebase Hosting config
├── dev.ps1                  # one-shot local runner
├── CLAUDE.md                # architecture/conventions (for Claude Code & humans)
├── DEPLOY.md                # full prod-deploy walkthrough
└── QA_FINDINGS.md           # standing QA notes
```

---

## Architecture in one paragraph

The backend enforces a hard split between an **ORM layer** (`models/`, `routers/`, `schemas/`) and a **pure engine** (`engine/`). The engine consumes plain dataclasses (`PlanInput`, `PersonInput`, …) and emits `YearRow` records — no SQLAlchemy import is allowed under `engine/`. The simulator orchestrates seven phases per year (age → grow → income → tax → expenses → liquidate → liabilities/goals) over a shared mutable state. Monte Carlo wraps the same `simulate()` with per-run Gaussian shocks. Scenarios are JSON-Patch overlays applied to `PlanInput` before simulation. All tax knobs flow through one `TaxConfig` dataclass seeded from `config/tax_ie_2026.py`.

Read **[CLAUDE.md](./CLAUDE.md)** for the deeper architecture guide (layering rules, deferred refactors, conventions, gotchas).

---

## Auth modes

**Local dev (default):** `MERIDIAN_DEV_AUTH=true` + `VITE_DEV_AUTH=true` → every request resolves to a seeded `dev-local` user. No Firebase project needed.

**Production:** flip both flags to `false` and supply Firebase credentials (service-account JSON for the backend, `VITE_FIREBASE_*` env vars for the frontend). Authorisation is `PlanMember` rows with `viewer < editor < owner`. Non-members see **404 (not 403)** on plan endpoints — deliberate, so plan IDs don't leak.

---

## Production deploy

Meridian runs as a single Cloud Run service (FastAPI + Alembic) on **Neon serverless Postgres** (free tier, autosuspends on idle), with the frontend on Firebase Hosting.

See **[DEPLOY.md](./DEPLOY.md)** for the full walkthrough — GCP project setup, Neon, Firebase Auth wiring, Cloud Run deploy, frontend deploy, troubleshooting. Cloud SQL Postgres is documented as a one-secret swap in Appendix A.

Quick reference once secrets are configured:

```powershell
gcloud builds submit --config cloudbuild.yaml `
  --substitutions "_REGION=europe-west1,_REPO=meridian,_SERVICE=meridian-api"

cd frontend; npm run build; firebase deploy --only hosting
```

---

## Status & roadmap

**Phase 13 complete.** 132/132 backend tests passing. Phase 14 (AI walkthrough) is next.

| Phase | Scope | Status |
|---|---|---|
| 1 | Foundations + CRUD for plan/people/assumptions | ✅ |
| 2 | Ireland 2026 tax engine + cash-flow simulator + Let's See | ✅ |
| 3 | Liabilities (mortgage amortisation) + ETF exit tax + CGT | ✅ |
| 4 | Pension lifecycle (PRSA / ARF / annuity / state pension) | ✅ |
| 4.5 | UX polish: inline edit, tooltips, employer pension % | ✅ |
| 5 | Goals + draggable Timeline | ✅ |
| 6 | Scenarios as JSON-Patch + Compare view | ✅ |
| 7 | Rebrand to Meridian + UX polish + clone/export | ✅ |
| 8 | Firebase Auth + multi-user backbone | ✅ |
| 9 | Postgres + Alembic + Docker + Cloud Run | ✅ |
| 10 | Plan-sharing UX (share-link invites) | ✅ |
| 11 | Multi-tax-year configurable rules | ✅ |
| 12 | CAT / inheritance / legacy | ✅ |
| 13 | Monte Carlo (probability bands) | ✅ |
| 14 | AI walkthrough | 🔜 |

Deferred: PDF export, AI chatbot.

---

## Where to read next

- **[CLAUDE.md](./CLAUDE.md)** — architecture, conventions, layering rules, deferred refactors.
- **[DEPLOY.md](./DEPLOY.md)** — production deploy walkthrough.
- **`backend/app/engine/`** — the tax/pension/simulator code. Start with `tax_ie.py` then `simulator.py`.
- **`backend/app/tests/`** — per-phase integration tests + engine unit tests. Good map of what each phase added.

---

## Licence & attribution

Inspired by Voyant AdviserGo. No Voyant code or assets are included. This is a personal project, not affiliated with Voyant Inc.
