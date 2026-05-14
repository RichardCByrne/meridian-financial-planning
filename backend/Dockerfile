# Meridian backend — Cloud Run image.
#
# Multi-stage so the runtime layer doesn't carry pip / wheel cache. The runtime
# stage runs `alembic upgrade head` before starting uvicorn so a deploy never
# serves traffic against a half-migrated DB.

FROM python:3.14-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Copy only the manifest first so the layer cache survives app-code changes.
COPY pyproject.toml ./
COPY app ./app
RUN pip install --upgrade pip && pip install .

# ----------

FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
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
