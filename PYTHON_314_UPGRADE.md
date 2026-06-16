# Backend Python 3.14 upgrade — findings

Branch: `chore/python-3.14` (off `main`). Date: 2026-06-16.

## Outcome

Backend upgraded from Python 3.13 → **3.14**. Full test suite (210 passed), `ruff`,
and app import are green on **CPython 3.14.2** locally. Only one dependency change
was required (see uvicorn below).

## What changed

| File | Change |
|------|--------|
| `backend/pyproject.toml` | `requires-python` `>=3.11` → `>=3.14`; ruff `target-version` `py311` → `py314`; `uvicorn[standard]` → plain `uvicorn` |
| `.github/workflows/test.yml` | backend `python-version` `3.13` → `3.14` |
| `backend/Dockerfile` | base image `python:3.13-slim` → `python:3.14-slim` (both stages); site-packages path `python3.13` → `python3.14`; rationale comment rewritten |

## Compatibility

Native/compiled deps verified importable on 3.14.2:

- `pydantic_core` 2.46.4, `psycopg` 3.3.4, `cryptography` 48.0.0,
  `firebase_admin` 7.4.0, `grpcio` 1.80.0 — all have cp314 wheels.

## The one blocker: uvicorn speed extras

`uvicorn[standard]` pulls **uvloop** and **httptools** (Linux-only C extensions).
As of 2026-06-16 neither publishes a `cp314` wheel on PyPI (uvloop 0.22.1,
httptools 0.8.0 — latest). On `python:3.14-slim` pip would fall back to a source
compile and fail (no build toolchain in the slim image).

**Resolution:** switched to plain `uvicorn` (pure-Python asyncio loop + h11). This
is a one-line revert back to `uvicorn[standard]` once uvloop/httptools ship cp314
wheels. Plain uvicorn is sufficient for this Cloud Run service; dev `--reload`
still works via uvicorn's StatReload fallback (no watchfiles needed).

Why not compile in Docker instead: adding `build-essential` makes the image bigger
and the cold build slower, the C extensions may not compile cleanly on 3.14 yet,
and you'd have to remove the toolchain again once wheels land — more churn now and
later for no upside, since re-adding `[standard]` is trivial.

## Not validated locally

The Docker image build on `python:3.14-slim` (Linux/manylinux cp314 wheels) was
**not** built here — the Docker daemon was unavailable. Confidence is high (all
required deps have cp314 manylinux wheels and uvloop/httptools are now removed),
but a `docker build backend/` (or a Cloud Build / CI run) should confirm before
deploy.

## Out of scope (pre-existing, not caused by this upgrade)

`pip-audit` flags **starlette 1.0.0** CVEs (transitive via `fastapi==0.136.1`):
PYSEC-2026-161, CVE-2026-48818/48817/54283/54282. These exist on `main`
independent of the Python version. Track as a separate dependency-bump branch.
