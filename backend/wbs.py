"""
Which WBS a plan budgets against, and whether a code is a work package in it. Scope Manager's WBS
when the project has one there; otherwise the plan's own draft (a pursuit's). The rule for every
line, labor, material or ODC: it sits on a LEAF (a work package), never on a grouping element.
"""

import scope_client
from models import CostLine, LaborLine, Plan, WbsElement


def code_key(code: str | None) -> tuple:
    if not code:
        return (1, ())
    return (0, tuple(int(p) if p.isdigit() else p for p in code.split(".")))


def parent_code(code: str) -> str | None:
    return code.rsplit(".", 1)[0] if "." in code else None


def draft_elements(plan: Plan) -> list[dict]:
    rows = WbsElement.query.filter_by(plan_id=plan.id).all()
    codes = {r.code for r in rows}
    parents = {parent_code(c) for c in codes}
    return [
        {
            "id": r.id, "code": r.code, "title": r.title, "parent_code": parent_code(r.code),
            "leaf": r.code not in parents, "charge_number": None, "percent_complete": None, "status": None,
        }
        for r in sorted(rows, key=lambda r: code_key(r.code))
    ]


def active_wbs(plan: Plan) -> dict:
    """{source, elements, reachable}. source: "scope_manager" (the project's real WBS), "draft"
    (the plan's own), or "none" (no WBS anywhere yet)."""
    sm = scope_client.fetch_wbs(plan.depot_project_id)
    if sm:
        by_id = {e["id"]: e["code"] for e in sm}
        elements = [
            {
                "id": e["id"], "code": e["code"], "title": e["title"],
                "parent_code": by_id.get(e.get("parent_id")), "leaf": e["leaf"],
                "charge_number": e.get("charge_number"), "percent_complete": e.get("percent_complete"),
                "status": e.get("status"),
            }
            for e in sm if e.get("code")
        ]
        return {"source": "scope_manager", "elements": elements, "reachable": True}
    draft = draft_elements(plan)
    return {"source": "draft" if draft else "none", "elements": draft, "reachable": sm is not None}


def check_code(plan: Plan, code: str | None) -> str | None:
    """None if `code` may go on a line, else the reason it can't. Clearing a code is always fine.
    If Scope Manager can't be reached and the plan has no draft, the code is let through rather
    than blocking the plan on another app being down."""
    if not code:
        return None
    wbs = active_wbs(plan)
    if wbs["source"] == "none":
        if not wbs["reachable"]:
            return None
        return "This project has no WBS yet. Set one up on the WBS tab first."
    match = next((e for e in wbs["elements"] if e["code"] == code), None)
    if match is None:
        return f"WBS {code} isn't in this project's WBS."
    if not match["leaf"]:
        return f"WBS {code} ({match['title']}) is a grouping element. Put the line on one of its work packages."
    return None


def lines_on(plan: Plan, code: str) -> int:
    """How many labor and cost lines sit on `code`."""
    return (
        LaborLine.query.filter_by(plan_id=plan.id, wbs=code).count()
        + CostLine.query.filter_by(plan_id=plan.id, wbs=code).count()
    )
