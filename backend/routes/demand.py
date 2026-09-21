from flask import Blueprint, jsonify, request

from models import Plan
from plan_math import demand_runs

bp = Blueprint("demand", __name__, url_prefix="/api")


@bp.get("/demand")
def list_demand():
    """The demand feed Labor Supply & Demand reads — kept in its original shape (`project`,
    `portfolio`, `role`, `fte`, `start_date`, `end_date`, `note`) so that app didn't have to
    change when Good Plan grew from hand-entered FTE lines into weekly plans. It is now DERIVED:
    each labor line's weekly hours become one row per run of consecutive weeks at the same FTE.
    Read-only — plans are edited through /api/plans. `?project=` / `?portfolio=` filter by name.
    (A later slice moves Labor Supply & Demand to weekly hours directly, and to baselines only.)"""
    project = request.args.get("project")
    portfolio = request.args.get("portfolio")
    rows = []
    for plan in Plan.query.order_by(Plan.project_name).all():
        if project and plan.project_name != project:
            continue
        if portfolio and plan.portfolio_name != portfolio:
            continue
        rows.extend(demand_runs(plan))
    rows.sort(key=lambda r: (r["start_date"], r["project"], r["role"]))
    return jsonify(rows)
