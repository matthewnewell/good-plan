"""The WBS a plan budgets against: a pursuit's draft here, or Scope Manager's once it has one, and
the rule that every line sits on a work package. Depot, Reckon and Scope Manager are stubbed."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="goodplan-wbs-test-")

import pytest  # noqa: E402

import depot_client  # noqa: E402
import reckon_client  # noqa: E402
import scope_client  # noqa: E402
from app import create_app  # noqa: E402

PROJECT = {"id": "proj-1", "name": "Test Program", "portfolio_name": "Test Portfolio", "phase": "pursuit"}
SM_WBS = [
    {"id": "e1", "code": "1", "title": "Engineering", "parent_id": None, "leaf": False, "charge_number": None, "percent_complete": 0, "status": "not_started"},
    {"id": "e11", "code": "1.1", "title": "PM", "parent_id": "e1", "leaf": True, "charge_number": "CN-1-11", "percent_complete": 20, "status": "in_progress"},
]


@pytest.fixture()
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    state = {"sm": [], "imported": None}
    monkeypatch.setattr(depot_client, "fetch_project", lambda pid: PROJECT if pid == "proj-1" else None)
    monkeypatch.setattr(depot_client, "fetch_projects", lambda: [PROJECT])
    monkeypatch.setattr(reckon_client, "fetch_rates", lambda: ({}, True))
    monkeypatch.setattr(reckon_client, "fetch_burden", lambda: ({}, True))
    monkeypatch.setattr(scope_client, "fetch_wbs", lambda pid: state["sm"])

    def fake_import(project_id, project, portfolio, elements, author):
        state["imported"] = elements
        return elements, None

    monkeypatch.setattr(scope_client, "import_wbs", fake_import)
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c, state
    PROJECT["phase"] = "pursuit"


def _plan(c):
    return c.post("/api/plans", json={"depot_project_id": "proj-1"}).get_json()


def _line(c, plan_id):
    return c.post(f"/api/plans/{plan_id}/lines", json={"category": "Machinist"}).get_json()["lines"][-1]["id"]


def test_a_line_needs_a_wbs_before_it_can_carry_a_code(env):
    c, _ = env
    plan = _plan(c)
    assert c.get(f"/api/plans/{plan['id']}/wbs").get_json()["source"] == "none"
    res = c.put(f"/api/lines/{_line(c, plan['id'])}", json={"wbs": "1.1"})
    assert res.status_code == 400 and "no WBS yet" in res.get_json()["error"]


def test_draft_codes_follow_the_tree_and_lines_go_on_work_packages_only(env):
    c, _ = env
    plan = _plan(c)
    c.post(f"/api/plans/{plan['id']}/wbs", json={"title": "Engineering"})
    wbs = c.post(f"/api/plans/{plan['id']}/wbs", json={"title": "Design", "parent_code": "1"}).get_json()
    assert [(e["code"], e["leaf"]) for e in wbs["elements"]] == [("1", False), ("1.1", True)]
    assert wbs["source"] == "draft" and wbs["editable"] and not wbs["can_promote"]

    line = _line(c, plan["id"])
    assert c.put(f"/api/lines/{line}", json={"wbs": "1"}).status_code == 400  # a grouping element
    assert c.put(f"/api/lines/{line}", json={"wbs": "9.9"}).status_code == 400  # not in the WBS
    assert c.put(f"/api/lines/{line}", json={"wbs": "1.1"}).get_json()["lines"][0]["wbs"] == "1.1"

    cost = c.post(f"/api/plans/{plan['id']}/costs", json={"kind": "material"}).get_json()["costs"][-1]["id"]
    assert c.put(f"/api/costs/{cost}", json={"wbs": "1"}).status_code == 400
    assert c.put(f"/api/costs/{cost}", json={"wbs": "1.1"}).status_code == 200


def test_a_work_package_with_budget_cant_be_split_or_deleted(env):
    c, _ = env
    plan = _plan(c)
    c.post(f"/api/plans/{plan['id']}/wbs", json={"title": "Engineering"})
    wbs = c.post(f"/api/plans/{plan['id']}/wbs", json={"title": "Design", "parent_code": "1"}).get_json()
    c.put(f"/api/lines/{_line(c, plan['id'])}", json={"wbs": "1.1"})
    assert c.post(f"/api/plans/{plan['id']}/wbs", json={"title": "Sub", "parent_code": "1.1"}).status_code == 400
    leaf = next(e for e in wbs["elements"] if e["code"] == "1.1")
    top = next(e for e in wbs["elements"] if e["code"] == "1")
    assert c.delete(f"/api/plans/{plan['id']}/wbs/{leaf['id']}").status_code == 400
    assert c.delete(f"/api/plans/{plan['id']}/wbs/{top['id']}").status_code == 400


def test_scope_managers_wbs_wins_and_isnt_edited_here(env):
    c, state = env
    plan = _plan(c)
    state["sm"] = SM_WBS
    wbs = c.get(f"/api/plans/{plan['id']}/wbs").get_json()
    assert wbs["source"] == "scope_manager" and not wbs["editable"]
    assert wbs["elements"][1]["parent_code"] == "1" and wbs["elements"][1]["charge_number"] == "CN-1-11"
    assert c.post(f"/api/plans/{plan['id']}/wbs", json={"title": "X"}).status_code == 409
    line = _line(c, plan["id"])
    assert c.put(f"/api/lines/{line}", json={"wbs": "1"}).status_code == 400
    assert c.put(f"/api/lines/{line}", json={"wbs": "1.1"}).status_code == 200


def test_the_draft_goes_to_scope_manager_only_once_awarded(env):
    c, state = env
    plan = _plan(c)
    c.post(f"/api/plans/{plan['id']}/wbs", json={"title": "Engineering"})
    c.post(f"/api/plans/{plan['id']}/wbs", json={"title": "Design", "parent_code": "1"})
    assert c.post(f"/api/plans/{plan['id']}/wbs/promote").status_code == 409  # still a pursuit
    PROJECT["phase"] = "execution"
    assert c.get(f"/api/plans/{plan['id']}/wbs").get_json()["can_promote"]
    assert c.post(f"/api/plans/{plan['id']}/wbs/promote").status_code == 200
    assert state["imported"] == [{"code": "1", "title": "Engineering"}, {"code": "1.1", "title": "Design"}]


def test_a_pursuit_shows_its_bp_charge_number_from_the_depot(env):
    c, _ = env
    plan = _plan(c)
    assert c.get(f"/api/plans/{plan['id']}/wbs").get_json()["bp_charge_number"] is None
    PROJECT["external_ids"] = [{"system": "S4 B&P", "external_id": "B&P-26-0417"}]
    try:
        assert c.get(f"/api/plans/{plan['id']}/wbs").get_json()["bp_charge_number"] == "B&P-26-0417"
    finally:
        PROJECT.pop("external_ids")


def test_budget_is_time_phased_by_wbs_and_sums_to_bac(env):
    c, _ = env
    plan = _plan(c)
    c.post(f"/api/plans/{plan['id']}/wbs", json={"title": "Engineering"})
    c.post(f"/api/plans/{plan['id']}/wbs", json={"title": "Design", "parent_code": "1"})
    line = _line(c, plan["id"])
    c.put(f"/api/lines/{line}", json={"wbs": "1.1", "rate_override": 50})
    c.put(f"/api/lines/{line}/weeks", json={"weeks": {plan["weeks"][0]: 10, plan["weeks"][1]: 20}})
    cost = c.post(f"/api/plans/{plan['id']}/costs", json={"kind": "material"}).get_json()["costs"][-1]["id"]
    c.put(f"/api/costs/{cost}", json={"qty": 1, "unit_cost": 1000})
    b = c.get("/api/budget?project_id=proj-1").get_json()
    assert b["by_wbs"]["1.1"] == {plan["weeks"][0]: 500.0, plan["weeks"][1]: 1000.0}
    total = sum(v for row in b["by_wbs"].values() for v in row.values()) + sum(b["undated"].values())
    assert round(total, 2) == round(b["bac"], 2)
    assert c.get("/api/budget?project_id=nope").status_code == 404
