# Meridian backend — Cloud Run image.
#
# Multi-stage so the runtime layer doesn't carry pip / wheel cache. The runtime
# stage runs `alembic upgrade head` before starting uvicorn so a deploy never
# serves traffic against a half-migrated DB.
#
# Python 3.14. The native deps (psycopg, cryptography, pydantic-core, grpcio via
# firebase-admin, uvloop/httptools via uvicorn[standard]) ship manylinux cp314
# wheels, so pip skips source compilation and the cold build stays fast. If a
# future dep bump lacks a cp314 wheel, pip will try to compile from source and
# fail on this slim image (no toolchain) — pin that dep back or add build-essential.

FROM python:3.14-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Install deps once, keyed only on pyproject.toml. A stub `app/` package lets
# `pip install .` resolve the local project without pulling in the real source
# yet — so the deps layer stays cached across app-code changes. Without this,
# every commit busts the pip-install layer (which reinstalls fastapi /
# sqlalchemy / psycopg / firebase-admin etc. from scratch).
COPY pyproject.toml ./
RUN mkdir -p app && touch app/__init__.py && \
    pip install --upgrade pip && pip install .

# Real source — layered AFTER deps so app-code changes don't invalidate the
# install layer. site-packages still holds the empty stub; the runtime stage
# below copies the real `app/` to /app/app, which sits earlier on sys.path
# (CWD wins over site-packages) so imports resolve to the real code.
COPY app ./app

# ----------

FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

WORKDIR /app

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

# Non-root user for least-privilege.
RUN useradd --no-create-home --uid 1000 meridian && chown -R meridian:meridian /app
USER meridian

EXPOSE 8000

# Run migrations, then start the app. `exec` lets SIGTERM from Cloud Run reach uvicorn.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
