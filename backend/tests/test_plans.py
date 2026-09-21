"""Plan math, the plan API, and the derived /api/demand feed — against a throwaway DB, with the
Depot and Reckon clients stubbed so nothing here needs another app running."""

import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="goodplan-test-")

import pytest  # noqa: E402

import depot_client  # noqa: E402
import reckon_client  # noqa: E402
from app import create_app  # noqa: E402
from plan_math import monday_of  # noqa: E402

PROJECT = {"id": "proj-1", "name": "Test Program", "portfolio_name": "Test Portfolio", "phase": "pursuit"}
RATES = {
    "Machinist": {"avg_rate": 40.0, "burden_factor": 1.5, "basis_hours": 1000},
    "Program Manager": {"avg_rate": 80.0, "burden_factor": 2.0, "basis_hours": 500},
}


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))  # a fresh database per test
    monkeypatch.setattr(depot_client, "fetch_project", lambda pid: PROJECT if pid == "proj-1" else None)
    monkeypatch.setattr(depot_client, "fetch_projects", lambda: [PROJECT])
    monkeypatch.setattr(reckon_client, "fetch_rates", lambda: (RATES, True))
    monkeypatch.setattr(
        reckon_client, "fetch_burden",
        lambda: ({"material": 1.1, "subcontract": 1.05, "services": 1.05, "travel": 1.05, "other": 1.05}, True),
    )
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _plan(client):
    return client.post("/api/plans", json={"depot_project_id": "proj-1"}).get_json()


def _line(client, plan_id, category="Machinist"):
    view = client.post(f"/api/plans/{plan_id}/lines", json={"category": category}).get_json()
    return view["lines"][-1]["id"]


def test_create_plan_from_depot_project_is_idempotent(client):
    a = client.post("/api/plans", json={"depot_project_id": "proj-1"})
    assert a.status_code == 201 and a.get_json()["project_name"] == "Test Program"
    b = client.post("/api/plans", json={"depot_project_id": "proj-1"})
    assert b.status_code == 200 and b.get_json()["id"] == a.get_json()["id"]
    assert client.post("/api/plans", json={"depot_project_id": "nope"}).status_code == 404


def test_spread_prices_with_burden_by_default(client):
    plan = _plan(client)
    line_id = _line(client, plan["id"])
    start = plan["weeks"][0]
    end = plan["weeks"][3]  # four weeks
    view = client.post(f"/api/lines/{line_id}/spread", json={"fte": 2, "start": start, "end": end}).get_json()
    line = view["lines"][0]
    assert line["total_hours"] == 2 * 40 * 4
    assert line["effective_rate"] == 60.0  # 40 direct x 1.5 burden
    assert view["totals"]["cost"] == 320 * 60


def test_burden_toggle_and_rate_override(client):
    plan = _plan(client)
    line_id = _line(client, plan["id"])
    client.put(f"/api/lines/{line_id}/weeks", json={"weeks": {plan["weeks"][0]: 100}})
    off = client.put(f"/api/plans/{plan['id']}", json={"include_burden": False}).get_json()
    assert off["lines"][0]["effective_rate"] == 40.0 and off["totals"]["cost"] == 4000
    over = client.put(f"/api/lines/{line_id}", json={"rate_override": 50}).get_json()
    assert over["lines"][0]["effective_rate"] == 50.0 and over["totals"]["cost"] == 5000


def _cost_6000(client):
    """A plan whose labor costs exactly $6,000 (100 h x $40 x 1.5 burden)."""
    plan = _plan(client)
    line_id = _line(client, plan["id"])
    client.put(f"/api/lines/{line_id}/weeks", json={"weeks": {plan["weeks"][0]: 100}})
    return plan


def test_new_plans_default_to_cpff(client):
    plan = _plan(client)
    assert plan["contract_type"] == "cpff" and plan["fee_percent"] == 8.0 and plan["award_fee_percent"] == 0.0


def test_cpff_fee_is_fixed_and_undistributed_budget_moves(client):
    plan = _cost_6000(client)
    # value 10,800 at 8% fixed fee -> budget base 10,000, fee 800; undistributed = 10,000 - 6,000
    t = client.put(f"/api/plans/{plan['id']}", json={"contract_value": 10800}).get_json()["totals"]
    assert t["cost"] == 6000 and t["contract_budget_base"] == 10000 and t["fee"] == 800
    assert t["undistributed"] == 4000 and t["undistributed_pct"] == 40.0
    assert t["award_fee"] == 0
    # more planned cost changes the undistributed budget, never the fee
    line_id = plan["lines"][0]["id"] if plan["lines"] else client.get(f"/api/plans/{plan['id']}").get_json()["lines"][0]["id"]
    t2 = client.put(f"/api/lines/{line_id}/weeks", json={"weeks": {plan["weeks"][1]: 100}}).get_json()["totals"]
    assert t2["fee"] == 800 and t2["undistributed"] == 10000 - 12000


def test_cpaf_splits_base_fee_and_award_pool(client):
    plan = _cost_6000(client)
    view = client.put(
        f"/api/plans/{plan['id']}",
        json={"contract_type": "cpaf", "contract_value": 11000, "fee_percent": 6, "award_fee_percent": 4},
    ).get_json()
    t = view["totals"]
    assert t["contract_budget_base"] == 10000 and t["fee"] == 600 and t["award_fee"] == 400
    assert t["undistributed"] == 4000


def test_ffp_uses_target_profit_and_reports_margin(client):
    plan = _cost_6000(client)
    t = client.put(f"/api/plans/{plan['id']}", json={"contract_type": "ffp", "contract_value": 11000, "fee_percent": 10}).get_json()["totals"]
    assert t["contract_budget_base"] == 10000 and t["fee"] == 1000
    assert t["margin"] == 5000 and t["margin_pct"] == round(5000 / 11000 * 100, 1)


def test_internal_has_no_fee_even_if_a_percent_is_set(client):
    plan = _cost_6000(client)
    t = client.put(f"/api/plans/{plan['id']}", json={"contract_type": "internal", "contract_value": 10000, "fee_percent": 8}).get_json()["totals"]
    assert t["contract_budget_base"] == 10000 and t["fee"] == 0 and t["undistributed"] == 4000


def test_rejects_an_unknown_contract_type(client):
    plan = _plan(client)
    assert client.put(f"/api/plans/{plan['id']}", json={"contract_type": "t&m"}).status_code == 400


def test_undistributed_is_null_without_a_contract_value(client):
    plan = _cost_6000(client)
    t = client.get(f"/api/plans/{plan['id']}").get_json()["totals"]
    assert t["contract_budget_base"] is None and t["undistributed"] is None and t["fee"] is None


def test_unknown_category_without_override_is_unpriced(client):
    plan = _plan(client)
    line_id = _line(client, plan["id"], "Astronaut")
    view = client.put(f"/api/lines/{line_id}/weeks", json={"weeks": {plan["weeks"][0]: 40}}).get_json()
    assert view["lines"][0]["effective_rate"] is None
    assert view["totals"]["unpriced_hours"] == 40 and view["totals"]["cost"] == 0


def test_weeks_must_be_mondays_inside_window(client):
    plan = _plan(client)
    line_id = _line(client, plan["id"])
    outside = (date.fromisoformat(plan["weeks"][-1]) + timedelta(weeks=5)).isoformat()
    assert client.put(f"/api/lines/{line_id}/weeks", json={"weeks": {outside: 10}}).status_code == 400
    not_monday = (date.fromisoformat(plan["weeks"][0]) + timedelta(days=2)).isoformat()
    assert client.put(f"/api/lines/{line_id}/weeks", json={"weeks": {not_monday: 10}}).status_code == 400


def test_zero_hours_clears_a_week(client):
    plan = _plan(client)
    line_id = _line(client, plan["id"])
    w = plan["weeks"][0]
    client.put(f"/api/lines/{line_id}/weeks", json={"weeks": {w: 40}})
    view = client.put(f"/api/lines/{line_id}/weeks", json={"weeks": {w: 0}}).get_json()
    assert view["lines"][0]["hours"] == {}


def test_demand_feed_groups_runs_of_equal_fte(client):
    plan = _plan(client)
    line_id = _line(client, plan["id"])
    w = plan["weeks"]
    client.post(f"/api/lines/{line_id}/spread", json={"fte": 1, "start": w[0], "end": w[2]})
    client.post(f"/api/lines/{line_id}/spread", json={"fte": 2, "start": w[3], "end": w[4]})
    rows = client.get("/api/demand?project=Test Program").get_json()
    assert [(r["fte"], r["start_date"], r["end_date"]) for r in rows] == [
        (1.0, w[0], (date.fromisoformat(w[2]) + timedelta(days=6)).isoformat()),
        (2.0, w[3], (date.fromisoformat(w[4]) + timedelta(days=6)).isoformat()),
    ]
    assert rows[0]["role"] == "Machinist" and rows[0]["portfolio"] == "Test Portfolio"
    assert client.get("/api/demand?project=Other").get_json() == []


def test_projects_list_shows_plan_status(client):
    before = client.get("/api/projects").get_json()["projects"][0]
    assert before["plan_id"] is None
    plan = _plan(client)
    after = client.get("/api/projects").get_json()["projects"][0]
    assert after["plan_id"] == plan["id"]


def test_summary_for_depot_tile(client):
    assert client.get("/api/summary?project_id=proj-1").get_json()["headline"] is None
    plan = _cost_6000(client)
    # plenty of undistributed budget: fine (a plan still being built out), not a warning
    client.put(f"/api/plans/{plan['id']}", json={"contract_value": 10800})
    s = client.get("/api/summary?project_id=proj-1").get_json()
    assert s["headline"] == "100" and s["status"] == "ok" and "undistributed" in s["label"]
    # planned cost above what the contract funds: critical
    client.put(f"/api/plans/{plan['id']}", json={"contract_value": 5400})  # budget base 5,000 < 6,000
    s = client.get("/api/summary?project_id=proj-1").get_json()
    assert s["status"] == "critical" and "over budget" in s["label"]


def test_new_plan_starts_this_monday(client):
    assert _plan(client)["start_week"] == monday_of(date.today()).isoformat()


def test_rates_passthrough(client):
    d = client.get("/api/rates").get_json()
    assert d["reachable"] is True
    machinist = next(r for r in d["rates"] if r["name"] == "Machinist")
    assert machinist["loaded_rate"] == 60.0


# ── materials and other direct costs ─────────────────────────────────────────────────────────
def _cost(client, plan, kind="material", **fields):
    view = client.post(f"/api/plans/{plan['id']}/costs", json={"kind": kind}).get_json()
    cid = view["costs"][-1]["id"]
    return client.put(f"/api/costs/{cid}", json=fields).get_json(), cid


def test_material_line_prices_with_its_kinds_burden_and_lands_on_its_week(client):
    plan = _plan(client)
    when = plan["weeks"][3]
    view, _ = _cost(client, plan, "material", description="Bar stock", qty=10, unit_cost=100, need_date=when)
    c = view["costs"][0]
    assert c["total"] == 1000 and c["factor"] == 1.1 and c["loaded_total"] == 1100
    assert view["totals"]["material_cost"] == 1100 and view["totals"]["cost"] == 1100
    assert view["totals"]["cost_by_week"][when] == 1100
    assert view["totals"]["cost_by_week_kind"]["material"][when] == 1100


def test_burden_off_leaves_costs_unburdened(client):
    plan = _plan(client)
    _cost(client, plan, "subcontract", qty=1, unit_cost=1000, need_date=plan["weeks"][2])
    view = client.put(f"/api/plans/{plan['id']}", json={"include_burden": False}).get_json()
    assert view["costs"][0]["factor"] == 1.0 and view["totals"]["subcontract_cost"] == 1000


def test_milestones_split_a_cost_across_dates_and_must_total_100(client):
    plan = _plan(client)
    _, cid = _cost(client, plan, "subcontract", qty=1, unit_cost=1000)
    w1, w2 = plan["weeks"][2], plan["weeks"][6]
    view = client.put(f"/api/costs/{cid}/phases", json={"phases": [{"date": w1, "percent": 30}, {"date": w2, "percent": 70}]}).get_json()
    by_week = view["totals"]["cost_by_week"]
    assert by_week[w1] == 315 and by_week[w2] == 735  # 1000 x 1.05 burden, split 30/70
    assert client.put(f"/api/costs/{cid}/phases", json={"phases": [{"date": w1, "percent": 60}]}).status_code == 400
    cleared = client.put(f"/api/costs/{cid}/phases", json={"phases": []}).get_json()
    assert cleared["costs"][0]["phases"] == []  # falls back to the need date


def test_undated_and_out_of_window_costs_are_counted_but_flagged(client):
    plan = _plan(client)
    _cost(client, plan, "services", qty=1, unit_cost=1000, need_date=None)
    far = (date.fromisoformat(plan["weeks"][-1]) + timedelta(weeks=20)).isoformat()
    view, _ = _cost(client, plan, "travel", qty=1, unit_cost=2000, need_date=far)
    t = view["totals"]
    assert t["cost"] == 1050 + 2100  # both in the total
    assert t["cost_unscheduled"] == 1050 and t["cost_outside_window"] == 2100
    assert sum(t["cost_by_week"].values()) == 0  # neither lands on a plotted week


def test_other_direct_costs_roll_up_and_all_cost_types_use_the_budget(client):
    plan = _cost_6000(client)  # labor: $6,000
    _cost(client, plan, "material", qty=1, unit_cost=1000, need_date=plan["weeks"][1])  # 1,100 burdened
    _cost(client, plan, "subcontract", qty=1, unit_cost=1000, need_date=plan["weeks"][1])  # 1,050
    _cost(client, plan, "travel", qty=2, unit_cost=500, need_date=plan["weeks"][1])  # 1,050
    view = client.put(f"/api/plans/{plan['id']}", json={"contract_value": 10800}).get_json()
    t = view["totals"]
    assert t["labor_cost"] == 6000 and t["material_cost"] == 1100 and t["odc_cost"] == 2100
    assert t["cost"] == 9200
    assert t["contract_budget_base"] == 10000 and t["undistributed"] == 800  # 10,000 - 9,200


def test_cost_line_validation_and_delete(client):
    plan = _plan(client)
    assert client.post(f"/api/plans/{plan['id']}/costs", json={"kind": "bribes"}).status_code == 400
    _, cid = _cost(client, plan, "other", qty=1, unit_cost=50, need_date=plan["weeks"][0])
    assert client.put(f"/api/costs/{cid}", json={"qty": -1}).status_code == 400
    assert client.delete(f"/api/costs/{cid}").get_json()["costs"] == []


# ── positions feed (Labor Supply & Demand) ───────────────────────────────────────────────────
def test_positions_publish_each_labor_line_with_weekly_hours(client):
    plan = _plan(client)
    a = _line(client, plan["id"], "Machinist")
    b = _line(client, plan["id"], "Machinist")
    c = _line(client, plan["id"], "Program Manager")
    w = plan["weeks"]
    client.put(f"/api/lines/{a}/weeks", json={"weeks": {w[0]: 40, w[1]: 40}})
    client.put(f"/api/lines/{b}/weeks", json={"weeks": {w[1]: 20}})
    client.put(f"/api/lines/{c}/weeks", json={"weeks": {w[2]: 10}})
    pos = client.get("/api/positions?project_id=proj-1").get_json()
    labels = sorted(p["label"] for p in pos)
    assert labels == ["Machinist #1", "Machinist #2", "Program Manager"]  # numbered only when a category repeats
    first = next(p for p in pos if p["label"] == "Machinist #1")
    assert first["weeks"] == {w[0]: 40, w[1]: 40} and first["total_hours"] == 80
    assert first["first_week"] == w[0] and first["last_week"] == w[1]
    assert first["depot_project_id"] == "proj-1" and first["phase"] == "pursuit"


def test_positions_skip_empty_lines_and_filter_by_project(client):
    plan = _plan(client)
    _line(client, plan["id"], "Machinist")  # no hours yet -> not a position
    assert client.get("/api/positions?project_id=proj-1").get_json() == []
    assert client.get("/api/positions?project_id=other").get_json() == []
