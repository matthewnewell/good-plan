"""
The Launchpad's app-summary contract for Good Plan — the tile on a project's page in Conway's
Depot (see the Depot's routes/applications.py; it renders these fields opaquely). `project_id` is
the Depot's own project id, which is exactly what a Plan is keyed on.

Headline is the plan's labor hours; the label gives the planned cost and, when a contract value is
set, how much of the budget is still undistributed (not yet planned into work). Red only when the
plan costs MORE than the contract funds — a large undistributed budget is normal while a plan is
still being built out, not a warning.
"""

import os

from flask import Blueprint, jsonify, request

import reckon_client
from models import Plan
from plan_math import plan_view

bp = Blueprint("summary", __name__, url_prefix="/api")

FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "http://localhost:5178")


def _money(n: float) -> str:
    return f"${n / 1_000_000:.2f}M" if n >= 1_000_000 else f"${n / 1_000:.0f}K" if n >= 1_000 else f"${n:.0f}"


@bp.get("/summary")
def summary():
    project_id = request.args.get("project_id")
    plan = Plan.query.filter_by(depot_project_id=project_id).first() if project_id else None
    if plan is None:
        return jsonify({"headline": None, "label": "No plan yet", "status": None, "href": f"{FRONTEND_BASE_URL}/"})

    rates, _ = reckon_client.fetch_rates()
    burden, _ = reckon_client.fetch_burden()
    t = plan_view(plan, rates, burden)["totals"]
    label = f"labor hours · {_money(t['cost'])} planned (all costs)"
    status = "ok"
    if t["undistributed"] is not None:
        label += f" · {_money(abs(t['undistributed']))} " + ("over budget" if t["undistributed"] < 0 else "undistributed")
        status = "critical" if t["undistributed"] < 0 else "ok"
    return jsonify({
        "headline": f"{t['hours']:,.0f}",
        "label": label,
        "status": status,
        "href": f"{FRONTEND_BASE_URL}/plans/{plan.id}",
    })
