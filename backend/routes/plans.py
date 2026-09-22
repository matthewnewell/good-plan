from datetime import date, timedelta

from flask import Blueprint, jsonify, request

import depot_client
import org_charts_client
import reckon_client
from db import db
import json

from models import COST_KINDS, CONTRACT_TYPES, CostLine, CostPhase, LaborLine, LaborWeek, Plan
from plan_math import monday_of, plan_view, window_weeks

bp = Blueprint("plans", __name__, url_prefix="/api")


def _float(value, field, minimum=None):
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a number")
    if minimum is not None and f < minimum:
        raise ValueError(f"{field} must be at least {minimum}")
    return f


def _pricing():
    """(labor rates, burden by cost type, Reckon reachable) — one read of everything Reckon prices."""
    rates, ok_rates = reckon_client.fetch_rates()
    burden, ok_burden = reckon_client.fetch_burden()
    return rates, burden, ok_rates and ok_burden


def _view(plan: Plan) -> dict:
    rates, burden, reachable = _pricing()
    data = plan_view(plan, rates, burden)
    data["rates_reachable"] = reachable
    return data


# ── Depot-aware project list ─────────────────────────────────────────────────────────────────
@bp.get("/projects")
def list_projects():
    """Every Depot project (any phase — a pursuit's plan is its bid estimate), each with whether
    it has a plan yet and, if so, the headline numbers. The Depot is the source for what a
    project is; this app never keeps its own copy. Unreachable Depot -> `depot_reachable: false`."""
    projects = depot_client.fetch_projects()
    plans = {p.depot_project_id: p for p in Plan.query.all()}
    rates, burden, rates_ok = _pricing()

    out = []
    if projects is not None:
        for p in projects:
            plan = plans.get(p["id"])
            row = {
                "depot_project_id": p["id"],
                "name": p["name"],
                "phase": p.get("phase"),
                "portfolio_name": p.get("portfolio_name"),
                "plan_id": plan.id if plan else None,
            }
            if plan:
                t = plan_view(plan, rates, burden)["totals"]
                row.update(
                    hours=t["hours"], cost=t["cost"], contract_value=plan.contract_value,
                    contract_type=plan.contract_type, undistributed=t["undistributed"],
                    undistributed_pct=t["undistributed_pct"],
                )
            out.append(row)
    return jsonify({"projects": out, "depot_reachable": projects is not None, "rates_reachable": rates_ok})


@bp.get("/positions")
def list_positions():
    """Every labor line as a POSITION a functional manager can fill with a named person — the feed
    Labor Supply & Demand reads. A position is generic on purpose (a category, not a name): the
    project requests "a Machinist", the functional manager decides who. Each carries its weekly
    hours so the staffing side can compute load. `?project_id=` limits to one Depot project. (When
    baselines exist this will serve the approved baseline only, not drafts.)"""
    phases = {p["id"]: p.get("phase") for p in (depot_client.fetch_projects() or [])}
    plans = Plan.query.order_by(Plan.project_name).all()
    if project_id := request.args.get("project_id"):
        plans = [p for p in plans if p.depot_project_id == project_id]

    out = []
    for plan in plans:
        totals = {}
        for line in plan.lines:
            totals[line.category] = totals.get(line.category, 0) + 1
        seen = {}
        for line in plan.lines:
            seen[line.category] = seen.get(line.category, 0) + 1
            weeks = {w.week_start.isoformat(): w.hours for w in line.weeks if w.hours > 0}
            if not weeks:
                continue
            ordinal = f" #{seen[line.category]}" if totals[line.category] > 1 else ""
            out.append({
                "id": line.id,
                "plan_id": plan.id,
                "depot_project_id": plan.depot_project_id,
                "project_name": plan.project_name,
                "portfolio_name": plan.portfolio_name,
                "phase": phases.get(plan.depot_project_id),
                "category": line.category,
                "label": f"{line.category}{ordinal}",
                "wbs": line.wbs,
                "note": line.note,
                "weeks": weeks,
                "total_hours": round(sum(weeks.values()), 2),
                "first_week": min(weeks),
                "last_week": max(weeks),
            })
    return jsonify(out)


@bp.get("/rates")
def list_rates():
    """Reckon's labor-rate table, passed through (server-to-server) so the browser only ever talks
    to this app. Powers the grid's category picker; `reachable: false` means Reckon is down and
    the list is whatever loaded last (possibly empty)."""
    rates, reachable = reckon_client.fetch_rates()
    rows = [{"name": n, **r, "loaded_rate": round(r["avg_rate"] * r["burden_factor"], 2)} for n, r in sorted(rates.items())]
    return jsonify({"rates": rows, "reachable": reachable})


@bp.get("/functions")
def list_functions():
    """Org Charts' functional taxonomy, passed through — powers the "pick a role" form as a
    Function, then a category inside it, instead of free-typing a category name."""
    functions, reachable = org_charts_client.fetch_functions()
    return jsonify({"functions": functions, "reachable": reachable})


# ── plans ────────────────────────────────────────────────────────────────────────────────────
@bp.post("/plans")
def create_plan():
    body = request.get_json(force=True) or {}
    project_id = body.get("depot_project_id")
    if not project_id:
        return jsonify({"error": "depot_project_id is required"}), 400
    existing = Plan.query.filter_by(depot_project_id=project_id).first()
    if existing:
        return jsonify(_view(existing)), 200

    project = depot_client.fetch_project(project_id)
    if project is None:
        return jsonify({"error": "that project wasn't found in Conway's Depot (or the Depot is unreachable)"}), 404

    plan = Plan(
        depot_project_id=project_id,
        project_name=project["name"],
        portfolio_name=project.get("portfolio_name"),
        start_week=monday_of(date.today()),
        week_count=26,
        contract_type="cpff",  # most of our work is cost plus fixed fee
        fee_percent=8.0,
    )
    db.session.add(plan)
    db.session.commit()
    return jsonify(_view(plan)), 201


@bp.get("/plans/<plan_id>")
def get_plan(plan_id):
    return jsonify(_view(Plan.query.get_or_404(plan_id)))


@bp.put("/plans/<plan_id>")
def update_plan(plan_id):
    plan = Plan.query.get_or_404(plan_id)
    body = request.get_json(force=True) or {}
    try:
        if "contract_value" in body:
            cv = body["contract_value"]
            plan.contract_value = None if cv in (None, "") else _float(cv, "contract_value", 0)
        if "contract_type" in body:
            if body["contract_type"] not in CONTRACT_TYPES:
                return jsonify({"error": f"contract_type must be one of {', '.join(CONTRACT_TYPES)}"}), 400
            plan.contract_type = body["contract_type"]
        if "include_burden" in body:
            plan.include_burden = bool(body["include_burden"])
        if "fee_percent" in body:
            plan.fee_percent = min(_float(body["fee_percent"], "fee_percent", 0), 100.0)
        if "award_fee_percent" in body:
            plan.award_fee_percent = min(_float(body["award_fee_percent"], "award_fee_percent", 0), 100.0)
        if "hours_per_fte_week" in body:
            plan.hours_per_fte_week = _float(body["hours_per_fte_week"], "hours_per_fte_week", 1)
        if "week_count" in body:
            count = int(_float(body["week_count"], "week_count", 1))
            plan.week_count = min(count, 156)
        if "start_week" in body:
            plan.start_week = monday_of(date.fromisoformat(body["start_week"]))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    db.session.commit()
    return jsonify(_view(plan))


@bp.delete("/plans/<plan_id>")
def delete_plan(plan_id):
    db.session.delete(Plan.query.get_or_404(plan_id))
    db.session.commit()
    return "", 204


# ── labor lines ──────────────────────────────────────────────────────────────────────────────
@bp.post("/plans/<plan_id>/lines")
def add_line(plan_id):
    plan = Plan.query.get_or_404(plan_id)
    body = request.get_json(force=True) or {}
    category = (body.get("category") or "").strip()
    if not category:
        return jsonify({"error": "category is required"}), 400
    position = max((l.position for l in plan.lines), default=-1) + 1
    line = LaborLine(plan_id=plan.id, category=category, wbs=(body.get("wbs") or "").strip() or None, position=position)
    db.session.add(line)
    db.session.commit()
    return jsonify(_view(plan)), 201


@bp.put("/lines/<line_id>")
def update_line(line_id):
    line = LaborLine.query.get_or_404(line_id)
    body = request.get_json(force=True) or {}
    try:
        if "category" in body:
            category = (body["category"] or "").strip()
            if not category:
                return jsonify({"error": "category cannot be empty"}), 400
            line.category = category
        if "wbs" in body:
            line.wbs = (body["wbs"] or "").strip() or None
        if "note" in body:
            line.note = (body["note"] or "").strip() or None
        if "rate_override" in body:
            ro = body["rate_override"]
            line.rate_override = None if ro in (None, "") else _float(ro, "rate_override", 0.01)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    db.session.commit()
    return jsonify(_view(line.plan))


@bp.delete("/lines/<line_id>")
def delete_line(line_id):
    line = LaborLine.query.get_or_404(line_id)
    plan = line.plan
    db.session.delete(line)
    db.session.commit()
    return jsonify(_view(plan))


def _set_week(line: LaborLine, week: date, hours: float):
    existing = next((w for w in line.weeks if w.week_start == week), None)
    if hours <= 0:
        if existing:
            db.session.delete(existing)
    elif existing:
        existing.hours = hours
    else:
        db.session.add(LaborWeek(line_id=line.id, week_start=week, hours=hours))


@bp.put("/lines/<line_id>/weeks")
def set_weeks(line_id):
    """Upsert hours for several weeks at once: `{weeks: {"2026-09-21": 40, "2026-09-28": 0}}`
    (0 clears a week). Keys must be Mondays inside the plan's window."""
    line = LaborLine.query.get_or_404(line_id)
    plan = line.plan
    body = request.get_json(force=True) or {}
    weeks = body.get("weeks")
    if not isinstance(weeks, dict):
        return jsonify({"error": "weeks must be an object of {date: hours}"}), 400
    allowed = set(window_weeks(plan))
    try:
        parsed = {}
        for key, value in weeks.items():
            d = date.fromisoformat(key)
            if d not in allowed:
                return jsonify({"error": f"{key} is not a Monday inside this plan's window"}), 400
            parsed[d] = _float(value, "hours", 0)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    for d, hours in parsed.items():
        _set_week(line, d, hours)
    db.session.commit()
    return jsonify(_view(plan))


@bp.post("/lines/<line_id>/spread")
def spread(line_id):
    """Fill weeks with a steady FTE: `{fte, start, end}` sets every Monday in [start, end]
    (clipped to the plan's window) to fte x hours_per_fte_week. `fte: 0` clears that range."""
    line = LaborLine.query.get_or_404(line_id)
    plan = line.plan
    body = request.get_json(force=True) or {}
    try:
        fte = _float(body.get("fte"), "fte", 0)
        start = date.fromisoformat(body.get("start"))
        end = date.fromisoformat(body.get("end"))
    except (TypeError, ValueError) as e:
        return jsonify({"error": str(e) if str(e) else "fte, start and end are required"}), 400
    if end < start:
        return jsonify({"error": "end cannot be before start"}), 400
    hours = fte * plan.hours_per_fte_week
    for week in window_weeks(plan):
        if start - timedelta(days=6) <= week <= end and week + timedelta(days=6) >= start:
            _set_week(line, week, hours)
    db.session.commit()
    return jsonify(_view(plan))


# ── materials and other direct costs ─────────────────────────────────────────────────────────
def _date_or_none(value):
    return None if value in (None, "") else date.fromisoformat(value)


@bp.post("/plans/<plan_id>/costs")
def add_cost(plan_id):
    plan = Plan.query.get_or_404(plan_id)
    body = request.get_json(force=True) or {}
    kind = body.get("kind")
    if kind not in COST_KINDS:
        return jsonify({"error": f"kind must be one of {', '.join(COST_KINDS)}"}), 400
    position = max((c.position for c in plan.cost_lines), default=-1) + 1
    line = CostLine(
        plan_id=plan.id, kind=kind, description=(body.get("description") or "").strip(),
        # A new line lands a month into the plan so it shows on the chart straight away.
        need_date=plan.start_week + timedelta(weeks=4), position=position,
    )
    db.session.add(line)
    db.session.commit()
    return jsonify(_view(plan)), 201


@bp.put("/costs/<cost_id>")
def update_cost(cost_id):
    line = CostLine.query.get_or_404(cost_id)
    body = request.get_json(force=True) or {}
    try:
        if "description" in body:
            line.description = (body["description"] or "").strip()
        if "vendor" in body:
            line.vendor = (body["vendor"] or "").strip() or None
        if "wbs" in body:
            line.wbs = (body["wbs"] or "").strip() or None
        if "note" in body:
            line.note = (body["note"] or "").strip() or None
        if "qty" in body:
            line.qty = _float(body["qty"], "qty", 0)
        if "unit_cost" in body:
            line.unit_cost = _float(body["unit_cost"], "unit_cost", 0)
        if "need_date" in body:
            line.need_date = _date_or_none(body["need_date"])
        if "detail" in body:
            d = body["detail"]
            line.detail = None if d in (None, "") else (d if isinstance(d, str) else json.dumps(d))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    db.session.commit()
    return jsonify(_view(line.plan))


@bp.delete("/costs/<cost_id>")
def delete_cost(cost_id):
    line = CostLine.query.get_or_404(cost_id)
    plan = line.plan
    db.session.delete(line)
    db.session.commit()
    return jsonify(_view(plan))


@bp.put("/costs/<cost_id>/phases")
def set_phases(cost_id):
    """Replace a line's milestones: `{phases: [{date, percent}]}`. The percents must sum to 100 (an
    empty list clears them, and the line falls back to its single need date)."""
    line = CostLine.query.get_or_404(cost_id)
    body = request.get_json(force=True) or {}
    phases = body.get("phases")
    if not isinstance(phases, list):
        return jsonify({"error": "phases must be a list of {date, percent}"}), 400
    try:
        parsed = [(date.fromisoformat(p["date"]), _float(p["percent"], "percent", 0)) for p in phases]
    except (KeyError, TypeError, ValueError) as e:
        return jsonify({"error": str(e) or "each phase needs a date and a percent"}), 400
    if parsed and abs(sum(pc for _, pc in parsed) - 100.0) > 0.01:
        return jsonify({"error": "milestone percents must add up to 100"}), 400
    for existing in list(line.phases):
        db.session.delete(existing)
    db.session.flush()
    for when, pct in parsed:
        db.session.add(CostPhase(line_id=line.id, date=when, percent=pct))
    db.session.commit()
    return jsonify(_view(line.plan))
