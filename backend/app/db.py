import os
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


def utcnow() -> datetime:
    """Naive UTC datetime. Replaces deprecated `datetime.utcnow()`.

    Stored in DateTime (without tz) columns to avoid a schema migration; the
    instant is unambiguously UTC by construction.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)

_DB_DIR = Path(__file__).resolve().parent.parent
DB_PATH = _DB_DIR / "meridian.db"
# Migrate from the pre-rename filename if present.
_legacy = _DB_DIR / "voyant.db"
if _legacy.exists() and not DB_PATH.exists():
    _legacy.rename(DB_PATH)
    _legacy_journal = _DB_DIR / "voyant.db-journal"
    if _legacy_journal.exists():
        _legacy_journal.rename(_DB_DIR / "meridian.db-journal")

# DATABASE_URL drives the connection. Defaults to local SQLite so `pytest` and
# `dev.ps1` keep working without configuration. In Cloud Run, set this to the
# Cloud SQL connection URL (postgresql+psycopg://user:pass@/db?host=/cloudsql/...).
DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite:///{DB_PATH}"

# Force psycopg v3 driver for any bare postgres URL. Neon's copy-paste URL is
# `postgresql://...` which SQLAlchemy maps to the legacy `psycopg2` driver — not
# installed (we ship `psycopg[binary]` v3 in pyproject.toml).
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]

# SQLite needs check_same_thread=False because FastAPI dependency injection
# may pass the session across threads. Postgres has no such requirement.
_connect_args: dict = (
    {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    future=True,
    pool_pre_ping=True,  # avoid stale Cloud SQL connections after idle timeout
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
