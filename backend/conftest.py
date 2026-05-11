"""Root conftest — runs before `app/tests/conftest.py`.

Forces the test suite onto a dedicated SQLite file so the per-test `_clean_db`
wipe in `app/tests/conftest.py` does not nuke the dev database
(`backend/meridian.db`) that the running dev server uses.

`app/db.py` reads `DATABASE_URL` at import time, so the env var must be set
before any `app.*` module is imported. Pytest discovers root conftests before
subdirectory conftests, satisfying that ordering.

We also create the full schema up-front. Engine-only tests
(`test_tax_ie.py`, `test_pension_ie.py`, `test_simulator.py`) never enter
`TestClient(app)` and so never run the FastAPI lifespan that would call
`Base.metadata.create_all`. Without the bootstrap below, the autouse
`_clean_db` fixture would try to `DELETE FROM <table>` against tables that
don't exist yet and explode.
"""

from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_meridian.db")

# Imports must come AFTER the env var so the engine is built against the test DB.
from app.db import Base, engine  # noqa: E402
from app import models  # noqa: E402,F401  -- registers all ORM tables on Base.metadata

Base.metadata.create_all(bind=engine)
