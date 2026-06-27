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
      "children":    {"<id>": {"active": false},   # drop a child from this scenario
                      "_added": [{"name": "Third child", "dob": "2028-01-01"}]},
      "assets":      {"<id>": {"growth_rate": 0.04, ...},
                      "_added": [{"name": "BTL flat", "kind": "property_btl",
                                  "value": 350000, "purchase_year": 2029,
                                  "deposit": 105000, "stamp_duty_pct": 0.075,
                                  "growth_rate": 0.03, "owner_person_id": 1,
                                  "_linked_liability_ref": "btl-mortgage"}]},
      "liabilities": {"<id>": {"interest_rate": 0.045, ...},
                      "_added": [{"_ref": "btl-mortgage", "name": "BTL mortgage",
                                  "kind": "mortgage", "principal": 245000,
                                  "interest_rate": 0.055, "term_months": 300,
                                  "start_year": 2029}]},   # monthly_payment auto-computed
      ...
      "assumptions": {"inflation_rate": 0.03, ...},
      "filing_status": "married",   # plan-level scalar override (optional)
      "marriage_year": 2030          # plan-level scalar override (optional)
    }

The two plan-level scalars are not bucketed: `filing_status` flips the whole
projection's tax treatment; `marriage_year` flips it to jointly-assessed married
from that calendar year onward (earlier years keep the base status) — this is how
a scenario models "getting married in year N".

Unknown keys, unknown ids, and `_added` entries missing required fields are
silently dropped — scenarios pre-date or post-date entity edits and we never
want a stale override to 500 the projection.
"""

from dataclasses import fields as dataclass_fields, replace
from datetime import date
from typing import Any

from app.engine.simulator import (
    AssetInput,
    BenefitInput,
    ChildInput,
    ExpenseInput,
    IncomeInput,
    LiabilityInput,
    PlanInput,
    _amortised_payment,
)

_BUCKETS: tuple[str, ...] = (
    "people",
    "incomes",
    "expenses",
    "assets",
    "liabilities",
    "goals",
    "benefits",
    "children",
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


def _build_added_benefit(payload: dict[str, Any], synthetic_id: int) -> BenefitInput | None:
    try:
        return BenefitInput(
            id=synthetic_id,
            person_id=int(payload["person_id"]),
            kind=str(payload.get("kind", "other")),
            name=str(payload.get("name", "Added benefit")),
            start_year=int(payload["start_year"]),
            end_year=int(payload["end_year"]) if payload.get("end_year") not in (None, "") else None,
            escalation_rate=float(payload.get("escalation_rate", 0.0)),
            amount=float(payload.get("amount", 0.0)),
            omv=float(payload.get("omv", 0.0)),
            rate=float(payload.get("rate", 0.0)),
            loan_is_qualifying=bool(payload.get("loan_is_qualifying", False)),
            relief_adults=int(payload.get("relief_adults", 1)),
            relief_children=int(payload.get("relief_children", 0)),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _build_added_child(payload: dict[str, Any], synthetic_id: int) -> ChildInput | None:
    try:
        dob_raw = payload["dob"]
        dob = dob_raw if isinstance(dob_raw, date) else date.fromisoformat(str(dob_raw))
        carer = payload.get("primary_carer_id")
        return ChildInput(
            id=synthetic_id,
            name=str(payload.get("name", "Added child")),
            dob=dob,
            primary_carer_id=int(carer) if carer not in (None, "") else None,
        )
    except (KeyError, TypeError, ValueError):
        return None


def _build_added_liability(payload: dict[str, Any], synthetic_id: int) -> LiabilityInput | None:
    try:
        principal = float(payload["principal"])
        rate = float(payload.get("interest_rate", 0.0))
        term = int(payload.get("term_months", 0))
        mp_raw = payload.get("monthly_payment")
        # Auto-derive the contracted payment from principal/rate/term when the
        # caller doesn't supply one — a scenario typically only knows price,
        # deposit, rate and term, not the exact monthly figure.
        monthly_payment = (
            float(mp_raw) if mp_raw not in (None, "")
            else _amortised_payment(principal, rate, term)
        )
        return LiabilityInput(
            id=synthetic_id,
            name=str(payload.get("name", "Added liability")),
            kind=str(payload.get("kind", "mortgage")),
            principal=principal,
            interest_rate=rate,
            term_months=term,
            start_year=int(payload["start_year"]),
            monthly_payment=monthly_payment,
            monthly_overpayment=float(payload.get("monthly_overpayment", 0.0)),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _build_added_asset(
    payload: dict[str, Any],
    synthetic_id: int,
    liability_ref_map: dict[str, int],
) -> AssetInput | None:
    try:
        # Resolve the mortgage link: prefer a ref to a same-scenario _added
        # liability, else an explicit numeric id of a base-plan liability.
        linked: int | None = None
        ref = payload.get("_linked_liability_ref")
        if isinstance(ref, str) and ref in liability_ref_map:
            linked = liability_ref_map[ref]
        elif payload.get("linked_liability_id") not in (None, ""):
            linked = int(payload["linked_liability_id"])
        value = float(payload["value"])
        return AssetInput(
            id=synthetic_id,
            name=str(payload.get("name", "Added asset")),
            kind=str(payload.get("kind", "property_btl")),
            value=value,
            growth_rate=float(payload.get("growth_rate", 0.0)),
            # Property basis defaults to the purchase price for CGT on disposal.
            cost_basis=float(payload.get("cost_basis", value)),
            acquired_year=int(payload["acquired_year"])
            if payload.get("acquired_year") not in (None, "") else None,
            owner_person_id=int(payload["owner_person_id"])
            if payload.get("owner_person_id") not in (None, "") else None,
            purchase_year=int(payload["purchase_year"])
            if payload.get("purchase_year") not in (None, "") else None,
            deposit=float(payload.get("deposit", 0.0)),
            disposal_year=int(payload["disposal_year"])
            if payload.get("disposal_year") not in (None, "") else None,
            linked_liability_id=linked,
            stamp_duty_pct=float(payload.get("stamp_duty_pct", 0.0)),
            selling_cost_pct=float(payload.get("selling_cost_pct", 0.0)),
        )
    except (KeyError, TypeError, ValueError):
        return None


_ADDED_BUILDERS = {
    "incomes": _build_added_income,
    "expenses": _build_added_expense,
    "benefits": _build_added_benefit,
    "children": _build_added_child,
}

# Scenario-added assets get ids well below the simulator's reserved synthetic
# asset ids (cash = -1, implicit PRSA = -1000-pid, implicit ARF = -2000-pid) so
# they never alias an auto-created wrapper. Liabilities have no reserved
# negatives, so they reuse the generic -1, -2, ... allocator.
_SCENARIO_ASSET_ID_BASE = -1_000_000


def _next_synthetic_asset_id(items: list[Any]) -> int:
    used = {item.id for item in items if hasattr(item, "id")}
    candidate = _SCENARIO_ASSET_ID_BASE
    while candidate in used:
        candidate -= 1
    return candidate


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

    # Assets and liabilities support `_added` too, but an added asset can be
    # financed by an added liability (a buy-to-let property + its new mortgage),
    # so they're built here with cross-reference resolution rather than via the
    # generic single-bucket builders above. Liabilities first so an asset can
    # resolve its mortgage by `_ref`.
    liability_ref_map: dict[str, int] = {}
    liab_added = (overrides.get("liabilities") or {}).get("_added")
    if isinstance(liab_added, list):
        for raw in liab_added:
            if not isinstance(raw, dict):
                continue
            new_id = _next_synthetic_id(new_lists["liabilities"])
            built = _build_added_liability(raw, new_id)
            if built is None:
                continue
            new_lists["liabilities"].append(built)
            ref = raw.get("_ref")
            if isinstance(ref, str) and ref:
                liability_ref_map[ref] = new_id

    asset_added = (overrides.get("assets") or {}).get("_added")
    if isinstance(asset_added, list):
        for raw in asset_added:
            if not isinstance(raw, dict):
                continue
            new_id = _next_synthetic_asset_id(new_lists["assets"])
            built = _build_added_asset(raw, new_id, liability_ref_map)
            if built is not None:
                new_lists["assets"].append(built)

    new_assumptions = plan.assumptions
    a_patch = overrides.get("assumptions") or {}
    if a_patch:
        new_assumptions = _patch_dataclass(plan.assumptions, a_patch)

    # Plan-level scalar overrides (not bucketed). Validated/coerced here and
    # silently dropped if malformed, matching the bucket policy of never letting
    # a stale override 500 a projection.
    plan_scalars: dict[str, Any] = {}
    fs = overrides.get("filing_status")
    if isinstance(fs, str) and fs in ("single", "married", "cohabiting"):
        plan_scalars["filing_status"] = fs
    my = overrides.get("marriage_year")
    if my not in (None, ""):
        try:
            plan_scalars["marriage_year"] = int(my)
        except (TypeError, ValueError):
            pass

    return replace(
        plan,
        people=new_lists["people"],
        incomes=new_lists["incomes"],
        expenses=new_lists["expenses"],
        assets=new_lists["assets"],
        liabilities=new_lists["liabilities"],
        goals=new_lists["goals"],
        benefits=new_lists["benefits"],
        children=new_lists["children"],
        assumptions=new_assumptions,
        **plan_scalars,
    )
