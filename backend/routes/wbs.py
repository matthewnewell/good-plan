"""
A plan's WBS: the one it budgets against (Scope Manager's, or the plan's own draft for a pursuit),
editing that draft, and sending it to Scope Manager at award.
"""

from flask import Blueprint, jsonify, request

import depot_client
import scope_client
from db import db
from models import Plan, WbsElement
from wbs import active_wbs, code_key, lines_on, parent_code

bp = Blueprint("wbs", __name__, url_prefix="/api/plans/<plan_id>/wbs")


def _phase(plan: Plan) -> str | None:
    project = depot_client.fetch_project(plan.depot_project_id)
    return project.get("phase") if project else None


def _bp_charge_number(project: dict | None) -> str | None:
    """A pursuit's Bid & Proposal charge number from S4, kept on the Depot project's crosswalk
    (system "S4 B&P"). Capture and proposal effort charges there, not to the draft WBS."""
    for e in (project or {}).get("external_ids") or []:
        if e.get("system") == "S4 B&P":
            return e.get("external_id")
    return None


def _payload(plan: Plan) -> dict:
    wbs = active_wbs(plan)
    project = depot_client.fetch_project(plan.depot_project_id)
    phase = project.get("phase") if project else None
    return {
        **wbs,
        "phase": phase,
        "editable": wbs["source"] in ("draft", "none"),
        # Sending the draft over is for awarded work; a pursuit keeps its draft here.
        "can_promote": wbs["source"] == "draft" and phase not in (None, "pursuit"),
        "bp_charge_number": _bp_charge_number(project),
        "scope_manager_url": scope_client.tree_url(plan.depot_project_id),
    }


@bp.get("")
def get_wbs(plan_id):
    return jsonify(_payload(Plan.query.get_or_404(plan_id)))


def _editable(plan: Plan):
    if active_wbs(plan)["source"] == "scope_manager":
        return jsonify({"error": "This project's WBS lives in Scope Manager now. Edit it there."}), 409
    return None


@bp.post("")
def add_element(plan_id):
    """`{title, parent_code?, code?}`. Without a code, the next free one under the parent."""
    plan = Plan.query.get_or_404(plan_id)
    if (blocked := _editable(plan)) is not None:
        return blocked
    body = request.get_json(force=True) or {}
    title = (body.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    existing = {e.code: e for e in WbsElement.query.filter_by(plan_id=plan.id).all()}
    parent = (body.get("parent_code") or "").strip() or None
    if parent and parent not in existing:
        return jsonify({"error": f"WBS {parent} isn't in the draft"}), 400
    if parent and lines_on(plan, parent):
        return jsonify({
            "error": f"WBS {parent} has budget on it ({lines_on(plan, parent)} lines). Move those lines to "
                     "another work package before splitting it, or budget would sit on a grouping element.",
        }), 400
    code = (body.get("code") or "").strip()
    if not code:
        prefix = f"{parent}." if parent else ""
        used = [int(c[len(prefix):]) for c in existing if c.startswith(prefix) and c[len(prefix):].isdigit()]
        code = f"{prefix}{max(used, default=0) + 1}"
    if code in existing:
        return jsonify({"error": f"WBS {code} is already in the draft"}), 400
    if parent_code(code) and parent_code(code) not in existing:
        return jsonify({"error": f"WBS {code} needs its parent {parent_code(code)} first"}), 400
    db.session.add(WbsElement(plan_id=plan.id, code=code, title=title))
    db.session.commit()
    return jsonify(_payload(plan)), 201


@bp.put("/<element_id>")
def rename_element(plan_id, element_id):
    plan = Plan.query.get_or_404(plan_id)
    if (blocked := _editable(plan)) is not None:
        return blocked
    el = WbsElement.query.filter_by(plan_id=plan.id, id=element_id).first_or_404()
    title = ((request.get_json(force=True) or {}).get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    el.title = title
    db.session.commit()
    return jsonify(_payload(plan))


@bp.delete("/<element_id>")
def delete_element(plan_id, element_id):
    plan = Plan.query.get_or_404(plan_id)
    if (blocked := _editable(plan)) is not None:
        return blocked
    el = WbsElement.query.filter_by(plan_id=plan.id, id=element_id).first_or_404()
    if any(e.code.startswith(el.code + ".") for e in WbsElement.query.filter_by(plan_id=plan.id).all()):
        return jsonify({"error": f"WBS {el.code} has elements under it. Remove those first."}), 400
    if n := lines_on(plan, el.code):
        return jsonify({"error": f"WBS {el.code} has {n} line{'' if n == 1 else 's'} on it. Move them first."}), 400
    db.session.delete(el)
    db.session.commit()
    return jsonify(_payload(plan))


@bp.post("/promote")
def promote(plan_id):
    """Send the draft to Scope Manager, which owns the WBS from then on. For awarded work only;
    the lines keep their codes, so nothing on the plan moves."""
    plan = Plan.query.get_or_404(plan_id)
    wbs = active_wbs(plan)
    if wbs["source"] != "draft":
        return jsonify({"error": "There's no draft WBS to send."}), 409
    phase = _phase(plan)
    if phase is None:
        return jsonify({"error": "Conway's Depot isn't reachable, so the project's phase can't be checked."}), 503
    if phase == "pursuit":
        return jsonify({"error": "This project is still a pursuit. Its WBS moves to Scope Manager once the work is awarded."}), 409
    body = request.get_json(force=True, silent=True) or {}
    elements = [{"code": e["code"], "title": e["title"]} for e in sorted(wbs["elements"], key=lambda e: code_key(e["code"]))]
    _, error = scope_client.import_wbs(plan.depot_project_id, plan.project_name, plan.portfolio_name, elements, body.get("author"))
    if error:
        return jsonify({"error": error}), 502
    return jsonify(_payload(plan))
