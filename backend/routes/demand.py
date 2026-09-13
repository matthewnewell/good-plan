from datetime import date

from flask import Blueprint, jsonify, request

from db import db
from models import DemandLine

bp = Blueprint("demand", __name__, url_prefix="/api")


def _parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be an ISO date (YYYY-MM-DD)")


@bp.get("/demand")
def list_demand():
    """Every demand line. `?project=`/`?portfolio=` scope it — a project sees its own plan, a
    portfolio owner (or nobody, the default) sees everything to compare across projects. No
    computed rollup here on purpose: summing FTE across lines with different date ranges would
    imply a peak-concurrent-headcount number this app doesn't actually know — the frontend
    groups and sorts the raw lines instead of pretending to a precision they don't have."""
    q = DemandLine.query
    if project := request.args.get("project"):
        q = q.filter(DemandLine.project == project)
    if portfolio := request.args.get("portfolio"):
        q = q.filter(DemandLine.portfolio == portfolio)
    lines = q.order_by(DemandLine.start_date).all()
    return jsonify([d.to_dict() for d in lines])


@bp.post("/demand")
def create_demand():
    body = request.get_json(force=True) or {}
    project = (body.get("project") or "").strip()
    role = (body.get("role") or "").strip()
    if not project:
        return jsonify({"error": "project is required"}), 400
    if not role:
        return jsonify({"error": "role is required"}), 400
    try:
        fte = float(body.get("fte"))
    except (TypeError, ValueError):
        return jsonify({"error": "fte must be a number"}), 400
    if fte <= 0:
        return jsonify({"error": "fte must be greater than 0"}), 400

    try:
        start_date = _parse_date(body.get("start_date"), "start_date")
        end_date = _parse_date(body.get("end_date"), "end_date")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if end_date < start_date:
        return jsonify({"error": "end_date cannot be before start_date"}), 400

    line = DemandLine(
        project=project,
        portfolio=(body.get("portfolio") or "").strip() or None,
        role=role,
        fte=fte,
        start_date=start_date,
        end_date=end_date,
        note=(body.get("note") or "").strip() or None,
    )
    db.session.add(line)
    db.session.commit()
    return jsonify(line.to_dict()), 201


@bp.put("/demand/<line_id>")
def update_demand(line_id):
    line = DemandLine.query.get_or_404(line_id)
    body = request.get_json(force=True) or {}

    if "project" in body:
        project = (body["project"] or "").strip()
        if not project:
            return jsonify({"error": "project cannot be empty"}), 400
        line.project = project
    if "portfolio" in body:
        line.portfolio = (body["portfolio"] or "").strip() or None
    if "role" in body:
        role = (body["role"] or "").strip()
        if not role:
            return jsonify({"error": "role cannot be empty"}), 400
        line.role = role
    if "fte" in body:
        try:
            fte = float(body["fte"])
        except (TypeError, ValueError):
            return jsonify({"error": "fte must be a number"}), 400
        if fte <= 0:
            return jsonify({"error": "fte must be greater than 0"}), 400
        line.fte = fte
    if "start_date" in body:
        try:
            line.start_date = _parse_date(body["start_date"], "start_date")
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    if "end_date" in body:
        try:
            line.end_date = _parse_date(body["end_date"], "end_date")
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    if line.end_date < line.start_date:
        return jsonify({"error": "end_date cannot be before start_date"}), 400
    if "note" in body:
        line.note = (body["note"] or "").strip() or None

    db.session.commit()
    return jsonify(line.to_dict())


@bp.delete("/demand/<line_id>")
def delete_demand(line_id):
    line = DemandLine.query.get_or_404(line_id)
    db.session.delete(line)
    db.session.commit()
    return "", 204


@bp.get("/projects")
def list_projects():
    rows = db.session.query(DemandLine.project).distinct().all()
    return jsonify(sorted({r[0] for r in rows}))


@bp.get("/portfolios")
def list_portfolios():
    rows = db.session.query(DemandLine.portfolio).filter(DemandLine.portfolio.isnot(None)).distinct().all()
    return jsonify(sorted({r[0] for r in rows}))


@bp.get("/roles")
def list_roles():
    """Distinct role labels already in use — powers an autocomplete-ish datalist so "Mechanical
    Engineer" and "Mech Engineer" don't quietly become two different roles by typo."""
    rows = db.session.query(DemandLine.role).distinct().all()
    return jsonify(sorted({r[0] for r in rows}))
