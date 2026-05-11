# Meridian — Financial Planning App (Ireland)

A financial-planning app with an **Ireland 2026** tax/pension engine. Inspired by Voyant AdviserGo. Currently single-user / local; multi-user with shared plans and Cloud Run deployment is the next phase.

## Status: Phase 13 complete — Monte Carlo probability bands

Phase 12 added CAT / inheritance modelling. Phase 13 adds probabilistic outcomes via Monte Carlo. A new `engine/montecarlo.py` module wraps `simulate()` and runs N independent simulations (default 200), each time applying a once-per-run Gaussian shock to every asset's growth rate (σ by asset kind: 12% for equities/ETFs, 10% for pensions, 6% for property, 0% for cash) and to the household's inflation and earnings-growth assumptions. Per-year net-worth values are collected across all runs and the 5th/10th/25th/50th/75th/90th/95th percentiles are returned alongside the probability of at least one shortfall occurring. The new `GET /plans/{id}/projection/montecarlo?n=200` endpoint accepts 10–1,000 runs and respects scenario overrides. The Let's See chart gains a **Probability bands** toggle: when active it switches to a fan chart (stacked Area layers p5→p25→p75→p95 with two shades of blue) overlaid with a median line and the original deterministic dashed line. Two new summary stats appear: median final net worth and shortfall probability. The MC query is cached for 60 seconds (re-running on demand is expensive). **127/127 backend tests passing**. Phase 14 (AI walkthrough) is next.

Post-Phase-13 quality pass (no behaviour change): fixed a scenario-override bug that silently dropped bequests / `tax_config` / `filing_status`; collapsed six parallel per-asset dicts in the simulator into a single `dict[int, AssetState]`; consolidated `TaxConfig` defaulting into one `resolve()` helper; extracted a `progressive_tax(amount, bands)` helper reused by USC and pension lump-sum tax; replaced `notes` string-grepping for shortfall detection with a typed `YearRow.had_shortfall` flag; centralised `_X_or_404` patterns into `routers/_helpers.py::get_or_404`; migrated `db.query()` → `db.execute(select(...))` in production code; replaced deprecated `datetime.utcnow()` with an `app.db.utcnow()` helper.

- **Tax engine (`backend/app/engine/tax_ie.py`)** — Income tax bands & credits, USC, PRSI per Budget 2026. 13 golden-number pytest cases.
- **Pension engine (`backend/app/engine/pension_ie.py`)** — Age-based contribution caps (15%–40% with €115k earnings cap), lump-sum tax bands (€200k tax-free / next €300k @ 20% / above @ marginal), ARF minimum drawdown percentages (4% / 5% / 6%).
- **Simulator (`backend/app/engine/simulator.py`)** — Per-year, per-person:
  - Pre-retirement: pension contribution capped per `pension_ie`, deducted from taxable income, routed to a PRSA/occupational wrapper (auto-creates implicit one if none exists).
  - At retirement age: pension wrappers crystallise → 25% lump sum (taxed per bands, net to cash) + 75% ARF (auto-created).
  - Post-retirement: ARF imputed minimum drawdown taxed as PAYE income; state pension auto-injected from `state_pension_age`.
- **`/api/plans/{id}/projection`** — `YearRow` adds `pension_contributions`, `pension_lump_sum`, `pension_lump_sum_tax`, `arf_drawdowns`, `state_pension_total`.
- **Let's See page** — Year-detail card surfaces pension contribution, ARF drawdown, state pension, and one-shot retirement lump sum events.
- Frontend forms: **People** captures `retirement_age`, **Income** captures `pension_contribution_pct`, **Assets** binds pension wrappers to an owner, **Assumptions** sets state-pension annual amount.

Roadmap: Phase 8 (Firebase Auth + multi-user backbone), Phase 9 (Postgres + Alembic + Docker + Cloud Run), Phase 10 (plan-sharing UX), Phases 11–13 (multi-tax-year config, CAT / inheritance, Monte Carlo).

## Prerequisites

- **Python 3.11+** (tested on 3.14.2).
- **Node.js 18.x with npm** (tested on v18.6.0).

> **Note:** `nvm` users — make sure your active Node has npm bundled. Node 25.x as installed on this machine ships without npm, so the dev runner uses Node 18 explicitly.

## First-time setup

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

## Run dev servers

Two terminals, or use the provided runner:

```powershell
# Terminal 1 — backend on :8000
cd backend
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000 --host 127.0.0.1

# Terminal 2 — frontend on :5173 (proxies /api to backend)
cd frontend
npm run dev
```

Or start both with one command:

```powershell
.\dev.ps1
```

Open http://localhost:5173 in your browser.

## Phase 2 verification

End-to-end golden path:

1. Visit http://localhost:5173 → `/plans`. Create plan **Murphy household** (base year 2026, 30 years).
2. **People** tab → add `Liam`, DOB 1985-03-12, primary.
3. **Income** tab → on Liam, add `Software engineer`, employment, €80,000, start 2026, 3% escalation.
4. **Expenses** tab → add `Living` (basic, €24k, 2.5% escalation), `Holidays` (discretionary, €5k, 2.5%), `Mortgage` (basic, €18k, 2026–2050).
5. **Assets** tab → add `Current account` (cash, €15,000) and `Investment ETF` (etf_fund, €50,000, 6% growth).
6. **Let's See** tab → chart loads. Dropdown switches between Net worth (area), Cash flow (bar+line), Income breakdown (stacked bar), Tax breakdown (stacked bar).
7. Hover any year → year-detail card updates with income/tax/expense/asset breakdown.
8. **Assumptions** → bump inflation to 3%, save → return to Let's See, expense bars and net-worth curve change.

Run the test suite:

```powershell
cd backend
.\.venv\Scripts\python -m pytest -v   # 132 tests, ~5s
```

Backend smoke check:

```powershell
curl http://127.0.0.1:8000/api/health
# {"status":"ok"}
```

OpenAPI is published at http://127.0.0.1:8000/docs.

## Project layout

```
meridian-financial-planning/
├── backend/                 # FastAPI + SQLAlchemy + SQLite
│   ├── app/
│   │   ├── main.py          # FastAPI app factory, CORS, router registration
│   │   ├── db.py            # engine, SessionLocal, Base
│   │   ├── models/          # SQLAlchemy ORM
│   │   ├── schemas/         # Pydantic v2 DTOs
│   │   ├── routers/         # plans, people, assumptions (more in later phases)
│   │   ├── engine/          # (Phase 2) pure calc engine
│   │   ├── config/          # (Phase 2) tax_ie_2026.py
│   │   └── tests/           # pytest
│   ├── pyproject.toml
│   └── meridian.db          # local SQLite — created on first run, gitignored
└── frontend/                # Vite + React + TypeScript
    ├── src/
    │   ├── api/             # client + react-query hooks
    │   ├── pages/           # PlansList, PlanEditor, panes/*
    │   ├── components/      # shared UI (Phase 2+)
    │   ├── store/           # zustand stores (Phase 2+)
    │   └── lib/             # money/date helpers
    ├── index.html
    ├── vite.config.ts
    └── package.json
```

## Roadmap (multi-month)

| Phase | Scope                                                    | Status     |
| ----- | -------------------------------------------------------- | ---------- |
| 1     | Foundations + CRUD for plan/people/assumptions           | ✅ Done    |
| 2     | Ireland 2026 tax engine + cash flow simulator + Let's See | ✅ Done    |
| 3     | Liabilities (mortgage amortisation) + ETF exit tax + CGT | ✅ Done    |
| 4     | Pension lifecycle (PRSA / ARF / annuity / state pension) | ✅ Done    |
| 4.5   | UX polish: inline edit, tooltips, employer pension %     | ✅ Done    |
| 5     | Goals + draggable Timeline                               | ✅ Done    |
| 6     | Scenarios as JSON-Patch + Compare view                   | ✅ Done    |
| 7     | Rebrand to Meridian + UX polish + clone/export           | ✅ Done    |
| 8     | Firebase Auth + multi-user backbone (User, PlanMember)   | ✅ Done    |
| 9     | Postgres + Alembic + Docker + Cloud Run deploy           | ✅ Done    |
| 10    | Plan-sharing UX (share-link invites)                     | ✅ Done    |
| 11    | Multi-tax-year configurable rules                        | ✅ Done    |
| 12    | CAT / inheritance / legacy                               | ✅ Done    |
| 13    | Monte Carlo (probability bands)                          | ✅ Done    |

Deferred: PDF export, AI walkthrough, AI chatbot.

## Notes

- **Multi-user with role-based shared plans.** Every endpoint is gated by `Depends(get_current_user)` (Firebase Auth) and an `owner`/`editor`/`viewer` membership check. Sharing UX (invite flow) lands in Phase 10; the substrate is in place now.
- **Dev-auth mode is the default for local development.** `MERIDIAN_DEV_AUTH=true` (backend) + `VITE_DEV_AUTH=true` (frontend) bypass Firebase and use a seeded "Local Dev User" — no Firebase project needed to run `./dev.ps1`. Flip both to `false` and configure `FIREBASE_SERVICE_ACCOUNT_PATH` + the `VITE_FIREBASE_*` env vars for production.
- **Schema is managed by `Base.metadata.create_all`** + lightweight ALTER TABLE in the FastAPI lifespan. Alembic comes in Phase 9.
- **Inspired by Voyant AdviserGo, not affiliated with Voyant Inc.** No Voyant code or assets are included.

## Production deploy (GCP)

Meridian deploys as a single Cloud Run service (FastAPI + Alembic) backed by Cloud SQL Postgres, with the static frontend on Firebase Hosting. The `cloudbuild.yaml` and `firebase.json` configs are wired in this repo; you supply the GCP project and secrets.

### One-time GCP setup
1. Create a Firebase project (which is also a GCP project). Enable Authentication → Google + Email/Password.
2. **Cloud SQL Postgres**: create a small instance (`db-f1-micro` for dev, `db-g1-small`+ for shared traffic). Note the connection name — it looks like `myproject:europe-west1:meridian-db`. Create a database (e.g. `meridian`) and a user.
3. **Artifact Registry**: create a Docker repo (e.g. `meridian` in `europe-west1`).
4. **Secret Manager**: create three secrets and grant the Cloud Run service account read access:
   - `DATABASE_URL` → `postgresql+psycopg://USER:PASSWORD@/meridian?host=/cloudsql/PROJECT:REGION:INSTANCE`
   - `FIREBASE_SERVICE_ACCOUNT_JSON` → contents of the service-account JSON (downloaded from Firebase console → Project Settings → Service Accounts)
   - `ALLOWED_ORIGINS` → comma-separated list, e.g. `https://meridian.example.com`
5. Enable the **Cloud SQL Admin API** and **Cloud Run API** for the project.

### Backend deploy (Cloud Build → Cloud Run)
```bash
gcloud builds submit --config cloudbuild.yaml \
  --substitutions \
    _REGION=europe-west1,\
_REPO=meridian,\
_SERVICE=meridian-api,\
_CLOUD_SQL_INSTANCE=PROJECT:europe-west1:meridian-db
```
The build runs `alembic upgrade head` from the Dockerfile entrypoint, so each release migrates before serving.

### Frontend deploy (Firebase Hosting)
```bash
cd frontend
# Set production env (creates .env.production, gitignored).
cat > .env.production <<EOF
VITE_DEV_AUTH=false
VITE_API_URL=https://meridian-api-XXXX-ew.a.run.app/api
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=...
VITE_FIREBASE_PROJECT_ID=...
VITE_FIREBASE_APP_ID=...
EOF

npm run build
firebase login            # one-time
firebase use YOUR_PROJECT  # writes to .firebaserc
firebase deploy --only hosting
```

### Verify
- `curl https://YOUR_API/api/health` → `{"status":"ok","db":"ok"}` (or `503` if Cloud SQL is unreachable).
- Sign in via the Firebase Hosting URL with Google; create a plan; confirm the chip in the sidebar shows your real name/email.
- Check Cloud Run logs for `Phase 8 migration: assigned ... orphan plan(s)` — should be `0` on a fresh prod DB.

## Firebase setup (local dev with real Firebase Auth)

1. In the Firebase console, create a project and enable Authentication → "Sign-in method" → Google + Email/Password.
2. Project settings → "Service accounts" → generate a new private key JSON. Save it somewhere safe (don't commit it).
3. Backend env vars:
   - `MERIDIAN_DEV_AUTH=false`
   - `FIREBASE_SERVICE_ACCOUNT_PATH=/path/to/service-account.json`
4. Frontend env vars (copy `frontend/.env.example` to `.env.local` and fill in):
   - `VITE_DEV_AUTH=false`
   - `VITE_FIREBASE_API_KEY=…`
   - `VITE_FIREBASE_AUTH_DOMAIN=…`
   - `VITE_FIREBASE_PROJECT_ID=…`
   - `VITE_FIREBASE_APP_ID=…`
