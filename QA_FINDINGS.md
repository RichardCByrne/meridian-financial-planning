# Meridian — Site-Wide QA Findings

**Auditor role:** Web QA engineer, 20 yrs.
**Date:** 2026-05-13.
**Branch under audit:** `main` @ `cbac672`.
**Scope:** All frontend (`frontend/src/**`) + backend (`backend/app/**`) + build/CI surfaces. Static analysis + targeted reads. Live UI probing not performed (no dev server in this audit; recommended as follow-up).

## Context

Whole-site QA pass requested. User wants this document as a triage record only — no fixes in this branch. Remediation will land later as one branch per category, matching the repo's branch-per-phase convention (`feedback_branch_per_phase.md`).

## Baseline health

| Check | Result |
|---|---|
| `pytest` (backend) | **132/132 pass** in 5.14s |
| `tsc --noEmit` (frontend lint) | **clean** |
| `vite build` | succeeds — **single 1.02 MB bundle (287 KB gzip)**; chunk-size warning raised |
| `ruff check app` | **3 F401** unused-import errors (auto-fixable) |
| `pip-audit` / `npm audit` | not re-run; CI runs both |

---

## Findings

Severity guide:
- **P0** — bug, data loss, security, or blocking UX in golden path.
- **P1** — meaningful UX/a11y/correctness issue users will hit.
- **P2** — polish, type-hygiene, minor edge cases.

### Security / info-disclosure

| ID | Sev | Location | Issue | Fix sketch |
|---|---|---|---|---|
| S1 | P0 | `frontend/src/components/ErrorBoundary.tsx:39-42` | Raw `error.stack` shown to end users in prod build. Stack reveals source paths / minified symbols / app internals. | Show `error.message` only in prod; `import.meta.env.DEV` gate the stack. |
| S2 | P1 | `backend/app/main.py:251` | `/api/health` returns raw DB exception text (`detail=f"DB not reachable: {e}"`). DSN / driver internals could leak. | Log full error server-side, return generic 503 detail. |
| S3 | P1 | `backend/app/routers/projections.py:179` | `except Exception: return None` swallows tax-config load errors silently. | Log with `logger.exception` before swallow. |
| S4 | P2 | `backend/app/main.py:235-241` | CORS `allow_methods=["*"]`, `allow_headers=["*"]`. Origin whitelist mitigates, but wildcards are over-broad. | Enumerate methods (GET/POST/PATCH/PUT/DELETE/OPTIONS) + needed headers. |
| S5 | P1 | `backend/app/routers/members.py:86` | `assert target is not None` — production runs typically pass `-O`, stripping asserts. Even without `-O`, an AssertionError surfaces as 500, not 404. | Replace with `raise HTTPException(404, "member not found")`. |

### Bugs / correctness

| ID | Sev | Location | Issue | Fix sketch |
|---|---|---|---|---|
| B1 | P1 | `frontend/src/pages/panes/LetsSeePane.tsx:441` | `Math.min(...retYears)` on potentially empty array → `Infinity`. Downstream chart math may NaN. | Guard `if (!retYears.length) return null`. |
| B2 | P1 | `frontend/src/pages/panes/ComparePane.tsx:54` | `data.b.projection.years[i]` indexed without length check — undefined when scenarios diverge in horizon length. | Use `Math.min(a.length, b.length)` and pad/skip explicitly. |
| B3 | P1 | `frontend/src/pages/panes/ScenariosPane.tsx:96` | `Number(raw)` on unknown user input — yields `NaN` silently, persisted into patch JSON. | Validate with `Number.isFinite` before submit. |
| B4 | P2 | `frontend/src/pages/panes/LetsSeePane.tsx:60-74` | RNG seed parsed via `Number()`; `NaN` accepted and stored to localStorage. | Same: `Number.isFinite` guard. |
| B5 | P2 | `frontend/src/api/hooks.ts:504` | Query key includes seed; seed change invalidation path looks inconsistent vs other mutation hooks. Confirm with live probe. | Re-verify after fixing B4. |
| B6 | P2 | `frontend/src/pages/AcceptInvitePage.tsx:62` | `new Date(expires_at)` accepts garbage → "Invalid Date" rendered. | Validate ISO before `new Date`. |
| B7 | P0 | `backend/app/routers/projections.py` (no cache decorator) | **CLAUDE.md claims `/projection/montecarlo` is cached 60s server-side** — `grep cache\|lru_cache` returns 0 matches. Each request runs N independent simulations. | Either implement TTL cache, or correct CLAUDE.md. Untrue invariant is worse than no cache. |

### Input validation gaps (backend)

All P1. Inputs reach engine without bounds — `NaN`/`inf`/negative-year/2150-base-year all accepted today.

| ID | Location | Field | Suggested constraint |
|---|---|---|---|
| V1 | `backend/app/schemas/plan.py:19` | `base_year` (PlanUpdate) | `ge=1900, le=2200` |
| V2 | `backend/app/schemas/income.py:18,31` | `start_year` | `ge=1900, le=2200` |
| V3 | `backend/app/schemas/income.py` | `end_year` | `ge=1900, le=2200`, `>= start_year` |
| V4 | `backend/app/schemas/income.py:20,33` | `escalation_rate` | `ge=-0.5, le=0.5` |
| V5 | `backend/app/schemas/expense.py:10,20` | `start_year` | as V2 |
| V6 | `backend/app/schemas/expense.py:12,22` | `escalation_rate` | as V4 |
| V7 | (cross-cut) | money fields | `ge=0` where applicable (income amount, expense amount, asset balance) |
| V8 | (cross-cut) | person `date_of_birth` | not in future, not >120 yrs ago |

Engine also lacks `math.isfinite` guards on incoming floats — Monte-Carlo will happily propagate `NaN` if any input is bad.

### UX — blocking modals

CLAUDE.md style note + modern UX both prefer non-blocking patterns. The repo already has a `Toast` system and an `EditModal`.

| ID | Sev | Location | Issue |
|---|---|---|---|
| U1 | P1 | `frontend/src/pages/PlansList.tsx:56` | `alert()` on seed-sample failure → replace with toast. |
| U2 | P1 | `frontend/src/pages/PlansList.tsx:68` | `alert("That file isn't valid JSON.")` → toast. |
| U3 | P1 | `frontend/src/pages/PlansList.tsx:74` | `alert("Import failed: …")` → toast. |
| U4 | P1 | `frontend/src/pages/PlansList.tsx:207` | `confirm("Delete plan …")` → use `EditModal`-style confirm dialog so it's keyboard/focus-trapped and themable. |
| U5 | P1 | `frontend/src/pages/panes/TaxRulesPane.tsx:72` | `window.prompt()` for tax-rule import → custom modal. |
| U6 | P1 | `frontend/src/pages/panes/TaxRulesPane.tsx:98` | `confirm()` → custom modal. |

### Accessibility (WCAG 2.1)

| ID | Sev | Location | Issue |
|---|---|---|---|
| A1 | P1 | `frontend/src/components/EditModal.tsx:30-36` | Focus moved via `setTimeout(0)` then a `querySelector` — fragile when modal body hasn't mounted. No focus trap on Tab, no Escape-to-close. |
| A2 | P1 | `frontend/src/components/EditModal.tsx:41` | Focus restoration on close is best-effort (`?.focus?.()`) — no fallback to body if previously-focused element is gone. |
| A3 | P1 | `frontend/src/pages/LoginPage.tsx:87,91` | `<label>Email</label><input …>` — implicit only. Missing `htmlFor`/`id` pair. SR users don't get the label. |
| A4 | P1 | `frontend/src/pages/panes/PeoplePane.tsx:38-47` | Validation errors not exposed via `aria-invalid` / `aria-describedby`. SR users get no error feedback. |
| A5 | P2 | `frontend/src/pages/PlansList.tsx:207` | `confirm()` is not keyboard-friendly in all SR/browser combos. Folds into U4. |
| A6 | P2 | `frontend/src/components/Toast.tsx` (check needed) | Confirm toasts have `role="status"` or `aria-live="polite"`. Not verified in this pass. |
| A7 | P2 | `frontend/src/pages/PlanEditor.tsx:272` (`<nav className="tabnav">`) | Verify tabs expose `role="tab"`/`aria-selected` or use semantic nav. Currently just `<NavLink>` — works for nav semantics but doesn't read as a tablist. |

### Mobile / responsive

| ID | Sev | Location | Issue |
|---|---|---|---|
| M1 | P2 | `frontend/src/pages/panes/TimelinePane.tsx:70-101` | Pointer-drag handlers lack `touch-action: none` CSS hint → scroll/drag conflict on iOS. |
| M2 | P2 | `frontend/src/pages/panes/LetsSeePane.tsx:303` | Chart heights hardcoded `240px mobile / 380px desktop`. No fluid scaling between breakpoints — tablet portrait gets the mobile value. |
| M3 | P2 | `frontend/src/pages/panes/LetsSeePane.tsx:215-237` | Nested `<details>` with absolutely-positioned overlay can overflow viewport on mobile; missing `max-height`/`overflow: auto`. |
| M4 | P1 | `frontend/src/pages/PlanEditor.tsx:71-108` | Plan-name edit row uses `flexWrap: wrap` but no min-width on the inputs — on iPhone-class viewports the number inputs collapse to ~50 px. |

### Type safety

| ID | Sev | Location | Issue |
|---|---|---|---|
| T1 | P2 | `frontend/src/pages/panes/LetsSeePane.tsx:309,340` | `onMouseMove={(s: any) => …}` — recharts has typed handlers. |
| T2 | P2 | `frontend/src/pages/panes/LetsSeePane.tsx:908-909` | `McTooltip` accepts `payload?: any[]` — define `TooltipPayload`. |

### Error recovery / observability

| ID | Sev | Location | Issue |
|---|---|---|---|
| E1 | P1 | `frontend/src/api/client.ts:29-32` | 401 → `window.location.assign("/login")` with no toast / no return-to-where-you-were. Aggressive: any background 401 (token refresh race) bounces the user. |
| E2 | P1 | `frontend/src/pages/panes/LetsSeePane.tsx:166-167` | Error render dumps `String(error)`. No retry button. |
| E3 | P2 | `frontend/src/components/ErrorBoundary.tsx:12-14` | `console.error` only. No Sentry / structured logging hook. Comment says "Phase 9 wires structured logging" — confirm if Phase 9 is still pending. |

### Build / perf

| ID | Sev | Location | Issue |
|---|---|---|---|
| P1 | P1 | `frontend/vite.config.ts` (no `manualChunks`) | Single 1.02 MB bundle (287 KB gzip). recharts + firebase + react-query bundled together. First paint cost on mobile is significant. |
| P2 | P2 | `frontend/src/main.tsx:19` | `staleTime: 5_000` for every query — including `usePlans()` which rarely changes. Tune per-query. |
| P3 | P2 | `backend/app/routers/projections.py` | No server cache for monte-carlo (B7). N=200 sims per call is expensive on autosuspending Neon. |

### Lint / dead code

| ID | Sev | Location | Issue |
|---|---|---|---|
| L1 | P2 | `backend/app/tests/test_phase6.py:11,15` (et al) | 3× ruff `F401` unused imports — auto-fixable via `ruff check --fix`. |
| L2 | P2 | `frontend/src/pages/panes/LetsSeePane.tsx:865-866` | `void Cell;` — workaround for unused import. Either consume or remove. |

### Tests — coverage gaps spotted

| ID | Area | Gap |
|---|---|---|
| TG1 | Engine | No explicit `NaN`/`inf` propagation test in `test_simulator.py`. |
| TG2 | Engine | No "zero people" plan test (simulator behaviour undefined-looking). |
| TG3 | Engine | No ages > life-expectancy edge test. |
| TG4 | API | Validation-bounds tests would be added with V1–V8. |
| TG5 | Frontend | No component tests at all (Vitest/RTL not configured). High-leverage gap for QA. |

---

## Suggested branch grouping (when remediation begins)

Per the repo's branch-per-category convention. Order suggests dependency / risk:

1. **`qa/security`** — S1, S2, S3, S5. Small surface, ship first.
2. **`qa/validation`** — V1–V8 + add `math.isfinite` guards in engine entrypoints. Includes new schema tests.
3. **`qa/ux-blocking-modals`** — U1–U6. Build/reuse a `<ConfirmDialog>` on top of `EditModal`; route `alert/prompt/confirm` callsites through it + `emitToast`.
4. **`qa/correctness`** — B1, B2, B3, B4, B6.
5. **`qa/a11y-modal-focus`** — A1, A2, A3, A4. Touches `EditModal`, `LoginPage`, `PeoplePane`.
6. **`qa/error-recovery`** — E1 (toast + soft-redirect), E2 (retry button), E3 (decide on Sentry).
7. **`qa/mobile-polish`** — M1, M2, M3, M4.
8. **`qa/perf-bundle`** — P1 (manualChunks: recharts, firebase, vendor), P3 (montecarlo TTL cache) + **fix CLAUDE.md monte-carlo claim if cache deferred** (B7).
9. **`qa/types-and-lint`** — T1, T2, L1, L2.
10. **`qa/test-coverage`** — TG1–TG5, optionally introduce Vitest+RTL skeleton.

CORS tightening (S4) folds into `qa/security` once deploy origins are confirmed in `DEPLOY.md`.

## Follow-ups not in scope of this static pass

- **Live browser smoke**: golden-path click-through (create plan → seed sample → edit → projection → Monte-Carlo → export → delete) on Chrome, Firefox, Safari, mobile Safari.
- **Lighthouse / axe-core** automated a11y + perf scan.
- **`npm audit` / `pip-audit`** rerun on current lockfiles.
- **Cloud Run cold-start** measurement after Neon autosuspend; current monte-carlo cost makes this user-facing.

## Verification (when fixes land)

For every branch:
- `cd backend; .\.venv\Scripts\python -m pytest` → 132+ pass (new tests grow this).
- `cd backend; .\.venv\Scripts\python -m ruff check app` → 0 errors.
- `cd frontend; npm run lint && npm run build` → tsc clean, build under 500 KB main chunk (after P1).
- Manual: dev server (`.\dev.ps1`), exercise the affected pane, check toast/modal behaviour with keyboard only, then with VoiceOver/NVDA for a11y branches.
- For `qa/perf-bundle`: confirm Network tab shows split vendor chunks; cold-load on throttled 4G under 3 s.
