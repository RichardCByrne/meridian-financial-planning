"""Scenario overrides applied to a PlanInput.

Overrides are stored as a JSON object keyed by entity bucket. Each bucket maps
the entity's primary-key id (as a string, since JSON object keys are strings)
to a partial dict of fields to overwrite. The `assumptions` bucket is a flat
dict (singleton). Each non-assumptions bucket may also contain an `_added`
key whose value is a list of new entity dicts to append to the simulator input
— this is how scenarios model promotions, windfalls, one-off events that don't
exist in the base plan.

Shape:
    {
      "people":      {"<id>": {"retirement_age": 60, ...}},
      "incomes":     {"<id>": {"gross_amount": 95000, ...},
                      "_added": [{"person_id": 1, "name": "Promotion bump",
                                  "kind": "employment", "gross_amount": 40000,
                                  "start_year": 2030}]},
      "expenses":    {"<id>": {"amount": 30000, ...},
                      "_added": [{"name": "Wedding", "category": "single_year",
                                  "amount": 20000, "start_year": 2029}]},
      ...
      "assumptions": {"inflation_rate": 0.03, ...}
    }

Unknown keys, unknown ids, and `_added` entries missing required fields are
silently dropped — scenarios pre-date or post-date entity edits and we never
want a stale override to 500 the projection.
"""

from dataclasses import fields as dataclass_fields, replace
from typing import Any

from app.engine.simulator import ExpenseInput, IncomeInput, PlanInput

_BUCKETS: tuple[str, ...] = (
    "people",
    "incomes",
    "expenses",
    "assets",
    "liabilities",
    "goals",
)


def _patch_dataclass(instance: Any, patch: dict[str, Any]) -> Any:
    valid = {f.name for f in dataclass_fields(instance)}
    clean = {k: v for k, v in patch.items() if k in valid and v is not None}
    if not clean:
        return instance
    return replace(instance, **clean)


def _next_synthetic_id(items: list[Any]) -> int:
    used = {item.id for item in items if hasattr(item, "id")}
    candidate = -1
    while candidate in used:
        candidate -= 1
    return candidate


def _build_added_income(payload: dict[str, Any], synthetic_id: int) -> IncomeInput | None:
    try:
        return IncomeInput(
            id=synthetic_id,
            person_id=int(payload["person_id"]),
            kind=str(payload.get("kind", "employment")),
            name=str(payload.get("name", "Added income")),
            gross_amount=float(payload["gross_amount"]),
            start_year=int(payload["start_year"]),
            end_year=int(payload["end_year"]) if payload.get("end_year") not in (None, "") else None,
            escalation_rate=float(payload.get("escalation_rate", 0.0)),
            pays_prsi=bool(payload.get("pays_prsi", True)),
            pays_usc=bool(payload.get("pays_usc", True)),
            pension_contribution_pct=float(payload.get("pension_contribution_pct", 0.0)),
            employer_pension_contribution_pct=float(
                payload.get("employer_pension_contribution_pct", 0.0)
            ),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _build_added_expense(payload: dict[str, Any], synthetic_id: int) -> ExpenseInput | None:
    try:
        return ExpenseInput(
            id=synthetic_id,
            name=str(payload.get("name", "Added expense")),
            category=str(payload.get("category", "single_year")),
            amount=float(payload["amount"]),
            start_year=int(payload["start_year"]),
            end_year=int(payload["end_year"]) if payload.get("end_year") not in (None, "") else None,
            escalation_rate=float(payload.get("escalation_rate", 0.0)),
        )
    except (KeyError, TypeError, ValueError):
        return None


_ADDED_BUILDERS = {
    "incomes": _build_added_income,
    "expenses": _build_added_expense,
}


def apply_overrides(plan: PlanInput, overrides: dict[str, Any] | None) -> PlanInput:
    """Return a new PlanInput with field-level overrides applied.

    The input plan is not mutated.
    """
    if not overrides:
        return plan

    new_lists: dict[str, list[Any]] = {}
    for bucket in _BUCKETS:
        items = list(getattr(plan, bucket))
        bucket_patches = overrides.get(bucket) or {}
        if isinstance(bucket_patches, dict) and bucket_patches:
            for idx, item in enumerate(items):
                key = str(item.id)
                if key in bucket_patches and isinstance(bucket_patches[key], dict):
                    items[idx] = _patch_dataclass(item, bucket_patches[key])
            added_payloads = bucket_patches.get("_added") or []
            builder = _ADDED_BUILDERS.get(bucket)
            if builder and isinstance(added_payloads, list):
                for raw in added_payloads:
                    if not isinstance(raw, dict):
                        continue
                    new_id = _next_synthetic_id(items)
                    built = builder(raw, new_id)
                    if built is not None:
                        items.append(built)
        new_lists[bucket] = items

    new_assumptions = plan.assumptions
    a_patch = overrides.get("assumptions") or {}
    if a_patch:
        new_assumptions = _patch_dataclass(plan.assumptions, a_patch)

    return replace(
        plan,
        people=new_lists["people"],
        incomes=new_lists["incomes"],
        expenses=new_lists["expenses"],
        assets=new_lists["assets"],
        liabilities=new_lists["liabilities"],
        goals=new_lists["goals"],
        assumptions=new_assumptions,
    )
