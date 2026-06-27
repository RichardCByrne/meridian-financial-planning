"""Plan ↔ JSON round-trip used by clone, export, and import.

Serialisation strategy: dump the Plan and every child row by ORM column,
strip primary keys + cross-row FKs (people-id, plan-id, etc.) and emit a
deterministic dict shape. On import / clone we map the old ids onto fresh
ones during insert so foreign keys still resolve.

This is the simplest serialisation that survives schema additions: any new
column on a model is automatically picked up via SQLAlchemy column
introspection. No hand-maintained list of fields per model.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    Asset,
    Assumptions,
    Benefit,
    Bequest,
    Child,
    Expense,
    Goal,
    IncomeSource,
    Liability,
    LiabilityAdjustment,
    Person,
    Plan,
    Scenario,
)

# Format version. Bump when the export format changes incompatibly.
EXPORT_FORMAT_VERSION = 1


def _columns(obj: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for col in obj.__table__.columns:
        v = getattr(obj, col.name)
        if isinstance(v, (date, datetime)):
            v = v.isoformat()
        out[col.name] = v
    return out


def serialise_plan(plan: Plan) -> dict[str, Any]:
    """Deep-dump a plan + all children to a JSON-serialisable dict.

    People are dumped with their incomes nested so the serialiser doesn't
    rely on cross-table queries. Other children are flat lists.
    """
    return {
        "format_version": EXPORT_FORMAT_VERSION,
        "plan": _strip_ids(_columns(plan), drop=["id"]),
        "people": [
            {
                **_strip_ids(_columns(p), drop=["id", "plan_id"]),
                "_local_id": p.id,
                "income_sources": [
                    _strip_ids(_columns(i), drop=["id", "person_id"])
                    for i in p.income_sources
                ],
            }
            for p in plan.people
        ],
        "expenses": [
            _strip_ids(_columns(e), drop=["id", "plan_id", "owner_person_id"])
            for e in plan.expenses
        ],
        "assets": [
            {
                **_strip_ids(
                    _columns(a), drop=["id", "plan_id", "owner_person_id", "linked_liability_id"]
                ),
                "_owner_local_id": a.owner_person_id,
                "_linked_liability_local_id": a.linked_liability_id,
            }
            for a in plan.assets
        ],
        "liabilities": [
            {
                **_strip_ids(_columns(li), drop=["id", "plan_id"]),
                "_local_id": li.id,
                "adjustments": [
                    _strip_ids(_columns(adj), drop=["id", "liability_id"])
                    for adj in li.adjustments
                ],
            }
            for li in plan.liabilities
        ],
        "goals": [
            {
                **_strip_ids(_columns(g), drop=["id", "plan_id", "linked_person_id"]),
                "_linked_person_local_id": g.linked_person_id,
            }
            for g in plan.goals
        ],
        "scenarios": [
            _strip_ids(_columns(s), drop=["id", "plan_id", "parent_scenario_id"])
            for s in plan.scenarios
        ],
        "bequests": [
            {
                **_strip_ids(
                    _columns(b),
                    drop=["id", "plan_id", "from_person_id", "to_person_id"],
                ),
                "_from_person_local_id": b.from_person_id,
                "_to_person_local_id": b.to_person_id,
            }
            for b in plan.bequests
        ],
        "benefits": [
            {
                **_strip_ids(_columns(b), drop=["id", "plan_id", "person_id"]),
                "_person_local_id": b.person_id,
            }
            for b in plan.benefits
        ],
        "children": [
            {
                **_strip_ids(_columns(c), drop=["id", "plan_id", "primary_carer_id"]),
                "_carer_local_id": c.primary_carer_id,
            }
            for c in plan.children
        ],
        "assumptions": (
            _strip_ids(_columns(plan.assumptions), drop=["id", "plan_id"])
            if plan.assumptions
            else None
        ),
    }


def _strip_ids(d: dict[str, Any], drop: list[str]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k not in drop}


def hydrate_plan(payload: dict[str, Any], db: Session, *, name_override: str | None = None) -> Plan:
    """Create a Plan + children from a serialised dict. Returns the persisted Plan."""
    if payload.get("format_version") != EXPORT_FORMAT_VERSION:
        raise ValueError(
            f"Unsupported export format_version: {payload.get('format_version')!r}"
        )

    plan_fields = dict(payload["plan"])
    plan_fields.pop("created_at", None)
    if name_override is not None:
        plan_fields["name"] = name_override
    plan = Plan(**plan_fields)
    db.add(plan)
    db.flush()  # populate plan.id

    # People + nested income sources. Track local-id → new-id so other rows
    # can resolve owner_person_id / linked_person_id references.
    person_id_map: dict[int, int] = {}
    for p_payload in payload.get("people", []):
        p_local_id = p_payload.pop("_local_id", None)
        income_payloads = p_payload.pop("income_sources", [])
        person_fields = {**p_payload, "plan_id": plan.id}
        if isinstance(person_fields.get("dob"), str):
            person_fields["dob"] = date.fromisoformat(person_fields["dob"])
        person = Person(**person_fields)
        db.add(person)
        db.flush()
        if p_local_id is not None:
            person_id_map[p_local_id] = person.id
        for inc_payload in income_payloads:
            db.add(IncomeSource(**inc_payload, person_id=person.id))

    for e_payload in payload.get("expenses", []):
        db.add(Expense(**e_payload, plan_id=plan.id))

    # Liabilities before assets so an asset can resolve its linked mortgage
    # (Phase 2 property transactions) to the freshly-minted liability id.
    liability_id_map: dict[int, int] = {}
    for li_payload in payload.get("liabilities", []):
        li_local_id = li_payload.pop("_local_id", None)
        adj_payloads = li_payload.pop("adjustments", [])
        liability = Liability(**li_payload, plan_id=plan.id)
        liability.adjustments = [LiabilityAdjustment(**a) for a in adj_payloads]
        db.add(liability)
        db.flush()  # populate liability.id
        if li_local_id is not None:
            liability_id_map[li_local_id] = liability.id

    for a_payload in payload.get("assets", []):
        owner_local = a_payload.pop("_owner_local_id", None)
        owner_id = person_id_map.get(owner_local) if owner_local is not None else None
        linked_local = a_payload.pop("_linked_liability_local_id", None)
        linked_id = liability_id_map.get(linked_local) if linked_local is not None else None
        db.add(
            Asset(
                **a_payload,
                plan_id=plan.id,
                owner_person_id=owner_id,
                linked_liability_id=linked_id,
            )
        )

    for g_payload in payload.get("goals", []):
        linked_local = g_payload.pop("_linked_person_local_id", None)
        linked_id = person_id_map.get(linked_local) if linked_local is not None else None
        db.add(Goal(**g_payload, plan_id=plan.id, linked_person_id=linked_id))

    for s_payload in payload.get("scenarios", []):
        db.add(Scenario(**s_payload, plan_id=plan.id))

    for b_payload in payload.get("bequests", []):
        from_local = b_payload.pop("_from_person_local_id", None)
        to_local = b_payload.pop("_to_person_local_id", None)
        from_id = person_id_map.get(from_local) if from_local is not None else None
        to_id = person_id_map.get(to_local) if to_local is not None else None
        if from_id is not None:
            db.add(Bequest(**b_payload, plan_id=plan.id, from_person_id=from_id, to_person_id=to_id))

    for ben_payload in payload.get("benefits", []):
        person_local = ben_payload.pop("_person_local_id", None)
        person_id = person_id_map.get(person_local) if person_local is not None else None
        if person_id is not None:
            db.add(Benefit(**ben_payload, plan_id=plan.id, person_id=person_id))

    for c_payload in payload.get("children", []):
        carer_local = c_payload.pop("_carer_local_id", None)
        carer_id = person_id_map.get(carer_local) if carer_local is not None else None
        if isinstance(c_payload.get("dob"), str):
            c_payload["dob"] = date.fromisoformat(c_payload["dob"])
        db.add(Child(**c_payload, plan_id=plan.id, primary_carer_id=carer_id))

    a_payload = payload.get("assumptions")
    if a_payload:
        db.add(Assumptions(**a_payload, plan_id=plan.id))
    else:
        db.add(Assumptions(plan_id=plan.id))

    db.commit()
    db.refresh(plan)
    return plan
