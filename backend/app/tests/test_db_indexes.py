"""Guards the indexes on frequently-filtered foreign-key columns (Alembic 0023).

SQLAlchemy doesn't auto-index FK columns, but nearly every read filters by one
(plan_id / person_id / liability_id / user_id). These assertions fail if a
model loses its `index=True`, so the Postgres query plans don't silently
regress to sequential scans.
"""

from app.models import Base

# (table, column) pairs that must carry an index for the hot read paths.
_EXPECTED = {
    ("people", "plan_id"),
    ("income_sources", "person_id"),
    ("expenses", "plan_id"),
    ("assets", "plan_id"),
    ("liabilities", "plan_id"),
    ("liability_adjustments", "liability_id"),
    ("goals", "plan_id"),
    ("scenarios", "plan_id"),
    ("bequests", "plan_id"),
    ("benefits", "plan_id"),
    ("children", "plan_id"),
    ("plan_invites", "plan_id"),
    ("plan_members", "user_id"),
}


def _indexed_columns() -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for table in Base.metadata.tables.values():
        # Single-column indexes (index=True or explicit Index) ...
        for idx in table.indexes:
            for col in idx.columns:
                pairs.add((table.name, col.name))
        # ... plus columns covered by a UNIQUE constraint (also an index).
        for col in table.columns:
            if col.unique:
                pairs.add((table.name, col.name))
    return pairs


def test_hot_fk_columns_are_indexed():
    indexed = _indexed_columns()
    missing = _EXPECTED - indexed
    assert not missing, f"foreign-key columns missing an index: {sorted(missing)}"
