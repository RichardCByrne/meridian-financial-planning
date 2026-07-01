"""Plan I/O: clone + JSON export / import round-trip."""

from fastapi.testclient import TestClient

from app.main import app


def _seed_plan(client: TestClient) -> int:
    p = client.post(
        "/api/plans",
        json={"name": "Original household", "base_year": 2026, "projection_years": 10},
    ).json()
    pid = p["id"]
    person = client.post(
        f"/api/plans/{pid}/people",
        json={"name": "Liam", "dob": "1990-01-01", "is_primary": True, "retirement_age": 66},
    ).json()
    client.post(
        f"/api/people/{person['id']}/income",
        json={"kind": "employment", "name": "Salary", "gross_amount": 80_000, "start_year": 2026},
    )
    client.post(
        f"/api/plans/{pid}/expenses",
        json={"name": "Living", "category": "basic", "amount": 30_000, "start_year": 2026},
    )
    client.post(
        f"/api/plans/{pid}/assets",
        json={
            "name": "Cash",
            "kind": "cash",
            "value": 20_000,
            "growth_rate": 0.0,
            "owner_person_id": person["id"],
        },
    )
    client.post(
        f"/api/plans/{pid}/goals",
        json={
            "kind": "milestone",
            "name": "Car",
            "target_amount": 25_000,
            "target_year": 2030,
            "linked_person_id": person["id"],
        },
    )
    client.post(
        f"/api/plans/{pid}/scenarios",
        json={"name": "Boost", "overrides": {"assumptions": {"inflation_rate": 0.04}}},
    )
    client.post(
        f"/api/plans/{pid}/children",
        json={"name": "Saoirse", "dob": "2020-01-01", "primary_carer_id": person["id"]},
    )
    return pid


def test_children_survive_export_import_with_carer_remap():
    with TestClient(app) as client:
        src_id = _seed_plan(client)
        export = client.get(f"/api/plans/{src_id}/export").json()
        assert len(export["children"]) == 1
        assert "_carer_local_id" in export["children"][0]
        # FK columns are stripped from the dumped row.
        assert "primary_carer_id" not in export["children"][0]

        imported = client.post("/api/plans/import", json=export).json()
        new_id = imported["id"]
        kids = client.get(f"/api/plans/{new_id}/children").json()
        assert len(kids) == 1
        assert kids[0]["name"] == "Saoirse"
        # Carer FK is remapped onto the imported plan's own person.
        new_people = client.get(f"/api/plans/{new_id}/people").json()
        assert kids[0]["primary_carer_id"] == new_people[0]["id"]


def test_children_survive_clone():
    with TestClient(app) as client:
        src_id = _seed_plan(client)
        new_id = client.post(f"/api/plans/{src_id}/clone").json()["id"]
        kids = client.get(f"/api/plans/{new_id}/children").json()
        new_people = client.get(f"/api/plans/{new_id}/people").json()
        assert len(kids) == 1
        assert kids[0]["primary_carer_id"] == new_people[0]["id"]


def test_clone_creates_independent_plan_with_same_projection():
    with TestClient(app) as client:
        src_id = _seed_plan(client)
        src_proj = client.get(f"/api/plans/{src_id}/projection").json()
        clone_resp = client.post(f"/api/plans/{src_id}/clone", json={"name": "Cloned"})
        assert clone_resp.status_code == 201
        new_id = clone_resp.json()["id"]
        assert new_id != src_id
        assert clone_resp.json()["name"] == "Cloned"
        # Same projection numbers.
        new_proj = client.get(f"/api/plans/{new_id}/projection").json()
        assert new_proj["summary"]["final_net_worth"] == src_proj["summary"]["final_net_worth"]
        # Mutating the clone does not affect the source.
        clone_assets = client.get(f"/api/plans/{new_id}/assets").json()
        client.delete(f"/api/assets/{clone_assets[0]['id']}")
        src_assets_after = client.get(f"/api/plans/{src_id}/assets").json()
        assert len(src_assets_after) == 1


def test_income_is_bonus_persists_and_survives_clone():
    with TestClient(app) as client:
        pid = client.post(
            "/api/plans",
            json={"name": "Bonus household", "base_year": 2026, "projection_years": 5},
        ).json()["id"]
        person = client.post(
            f"/api/plans/{pid}/people",
            json={"name": "Niamh", "dob": "1990-01-01", "is_primary": True},
        ).json()
        inc = client.post(
            f"/api/people/{person['id']}/income",
            json={
                "kind": "other", "name": "2026 bonus", "gross_amount": 8_000,
                "start_year": 2026, "end_year": 2026, "is_bonus": True,
            },
        ).json()
        assert inc["is_bonus"] is True
        # Default stays False.
        plain = client.post(
            f"/api/people/{person['id']}/income",
            json={"kind": "employment", "name": "Salary", "gross_amount": 60_000, "start_year": 2026},
        ).json()
        assert plain["is_bonus"] is False
        # Clone preserves the flag.
        cid = client.post(f"/api/plans/{pid}/clone").json()["id"]
        new_people = client.get(f"/api/plans/{cid}/people").json()
        rows = client.get(f"/api/people/{new_people[0]['id']}/income").json()
        assert {r["name"]: r["is_bonus"] for r in rows} == {"2026 bonus": True, "Salary": False}


def test_clone_default_name_appends_copy():
    with TestClient(app) as client:
        src_id = _seed_plan(client)
        clone = client.post(f"/api/plans/{src_id}/clone").json()
        assert clone["name"].endswith("(copy)")


def test_export_then_import_reproduces_projection():
    with TestClient(app) as client:
        src_id = _seed_plan(client)
        src_proj = client.get(f"/api/plans/{src_id}/projection").json()
        export = client.get(f"/api/plans/{src_id}/export").json()
        assert export["format_version"] == 1
        assert len(export["people"]) == 1
        assert len(export["people"][0]["income_sources"]) == 1
        assert len(export["assets"]) == 1
        assert len(export["scenarios"]) == 1
        # Import as a new plan.
        imported = client.post("/api/plans/import", json=export).json()
        new_proj = client.get(f"/api/plans/{imported['id']}/projection").json()
        assert new_proj["summary"]["final_net_worth"] == src_proj["summary"]["final_net_worth"]
        # Goal linked_person_id was remapped to the new person id, not stale.
        new_goals = client.get(f"/api/plans/{imported['id']}/goals").json()
        new_people = client.get(f"/api/plans/{imported['id']}/people").json()
        assert new_goals[0]["linked_person_id"] == new_people[0]["id"]


def test_import_rejects_unknown_format_version():
    with TestClient(app) as client:
        bad = {"format_version": 999, "plan": {"name": "X", "base_year": 2026, "projection_years": 10}}
        resp = client.post("/api/plans/import", json=bad)
        assert resp.status_code == 400


def test_life_policy_and_death_year_survive_clone():
    """Protection data (person.death_year + a term policy) round-trips through a
    clone, with the policy's person_id remapped to the cloned person."""
    with TestClient(app) as client:
        pid = client.post(
            "/api/plans",
            json={"name": "Protected", "base_year": 2026, "projection_years": 10},
        ).json()["id"]
        person = client.post(
            f"/api/plans/{pid}/people",
            json={"name": "Aoife", "dob": "1985-01-01", "is_primary": True, "death_year": 2040},
        ).json()
        assert person["death_year"] == 2040
        client.post(
            f"/api/plans/{pid}/life-policies",
            json={
                "person_id": person["id"], "name": "Term cover",
                "sum_assured": 300_000, "premium_annual": 700,
                "start_year": 2026, "end_year": 2045,
            },
        )
        new_id = client.post(f"/api/plans/{pid}/clone").json()["id"]
        new_people = client.get(f"/api/plans/{new_id}/people").json()
        assert new_people[0]["death_year"] == 2040
        policies = client.get(f"/api/plans/{new_id}/life-policies").json()
        assert len(policies) == 1
        assert policies[0]["sum_assured"] == 300_000
        # person_id remapped to the cloned plan's own person, not the source's.
        assert policies[0]["person_id"] == new_people[0]["id"]


def test_db_pension_survives_clone():
    """A defined-benefit pension round-trips through a clone with its person_id
    remapped to the cloned person."""
    with TestClient(app) as client:
        pid = client.post(
            "/api/plans",
            json={"name": "DB household", "base_year": 2026, "projection_years": 10},
        ).json()["id"]
        person = client.post(
            f"/api/plans/{pid}/people",
            json={"name": "Sean", "dob": "1965-01-01", "is_primary": True},
        ).json()
        client.post(
            f"/api/plans/{pid}/db-pensions",
            json={
                "person_id": person["id"], "name": "Public service",
                "accrual_rate": 0.0125, "service_years": 35, "final_salary": 55_000,
                "revaluation_rate": 0.02, "normal_retirement_age": 65,
                "tax_free_lump_sum": 80_000,
            },
        )
        new_id = client.post(f"/api/plans/{pid}/clone").json()["id"]
        new_people = client.get(f"/api/plans/{new_id}/people").json()
        pensions = client.get(f"/api/plans/{new_id}/db-pensions").json()
        assert len(pensions) == 1
        assert pensions[0]["final_salary"] == 55_000
        assert pensions[0]["tax_free_lump_sum"] == 80_000
        assert pensions[0]["person_id"] == new_people[0]["id"]


def _seed_two_person_plan_with_bequest_and_benefit(client: TestClient) -> tuple[int, int, int]:
    """Plan with two people, a bequest from A→B, and a medical-insurance BIK on A.

    Returns (plan_id, person_a_id, person_b_id).
    """
    pid = client.post(
        "/api/plans",
        json={"name": "Estate household", "base_year": 2026, "projection_years": 10},
    ).json()["id"]
    a = client.post(
        f"/api/plans/{pid}/people",
        json={"name": "Aoife", "dob": "1980-01-01", "is_primary": True, "death_year": 2050},
    ).json()
    b = client.post(
        f"/api/plans/{pid}/people",
        json={"name": "Cormac", "dob": "1982-01-01", "is_primary": False},
    ).json()
    client.post(
        f"/api/plans/{pid}/bequests",
        json={
            "from_person_id": a["id"],
            "to_person_id": b["id"],
            "cat_group": "A",
            "share_pct": 1.0,
        },
    )
    client.post(
        f"/api/plans/{pid}/benefits",
        json={
            "person_id": a["id"],
            "kind": "medical_insurance",
            "name": "VHI",
            "start_year": 2026,
            "amount": 1_400,
        },
    )
    return pid, a["id"], b["id"]


def test_bequest_survives_export_import_with_person_remap():
    """Covers the bequest re-linking branch in serialisation (from/to person ids
    resolved through person_id_map on import)."""
    with TestClient(app) as client:
        src_id, _, _ = _seed_two_person_plan_with_bequest_and_benefit(client)
        export = client.get(f"/api/plans/{src_id}/export").json()
        assert len(export["bequests"]) == 1
        beq = export["bequests"][0]
        # FK columns stripped, local-id links present for re-mapping.
        assert "from_person_id" not in beq
        assert "to_person_id" not in beq
        assert "_from_person_local_id" in beq
        assert "_to_person_local_id" in beq

        imported = client.post("/api/plans/import", json=export).json()
        new_id = imported["id"]
        new_bequests = client.get(f"/api/plans/{new_id}/bequests").json()
        new_people = client.get(f"/api/plans/{new_id}/people").json()
        names = {p["id"]: p["name"] for p in new_people}
        assert len(new_bequests) == 1
        # from/to remapped onto the imported plan's own people, not stale source ids.
        assert names[new_bequests[0]["from_person_id"]] == "Aoife"
        assert names[new_bequests[0]["to_person_id"]] == "Cormac"
        assert new_bequests[0]["share_pct"] == 1.0


def test_benefit_survives_export_import_with_person_remap():
    """Covers the benefit re-linking branch in serialisation."""
    with TestClient(app) as client:
        src_id, _, _ = _seed_two_person_plan_with_bequest_and_benefit(client)
        export = client.get(f"/api/plans/{src_id}/export").json()
        assert len(export["benefits"]) == 1
        ben = export["benefits"][0]
        assert "person_id" not in ben
        assert "_person_local_id" in ben

        imported = client.post("/api/plans/import", json=export).json()
        new_id = imported["id"]
        new_benefits = client.get(f"/api/plans/{new_id}/benefits").json()
        new_people = client.get(f"/api/plans/{new_id}/people").json()
        names = {p["id"]: p["name"] for p in new_people}
        assert len(new_benefits) == 1
        assert new_benefits[0]["kind"] == "medical_insurance"
        # person_id remapped onto the imported plan's own person.
        assert names[new_benefits[0]["person_id"]] == "Aoife"


def test_bequest_and_benefit_survive_clone():
    with TestClient(app) as client:
        src_id, _, _ = _seed_two_person_plan_with_bequest_and_benefit(client)
        new_id = client.post(f"/api/plans/{src_id}/clone").json()["id"]
        new_people = client.get(f"/api/plans/{new_id}/people").json()
        names = {p["id"]: p["name"] for p in new_people}
        bequests = client.get(f"/api/plans/{new_id}/bequests").json()
        benefits = client.get(f"/api/plans/{new_id}/benefits").json()
        assert len(bequests) == 1
        assert len(benefits) == 1
        assert names[bequests[0]["from_person_id"]] == "Aoife"
        assert names[bequests[0]["to_person_id"]] == "Cormac"
        assert names[benefits[0]["person_id"]] == "Aoife"
