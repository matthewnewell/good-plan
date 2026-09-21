"""
Good Plan's Agent tab — an ongoing conversation about one project's plan, grounded in its labor
lines, weekly shape, pricing and contract terms. Same shape as MARTI's routes/ai.py: the frontend
owns conversation history, this route rebuilds the plan's context fresh on every call so an edit
made mid-conversation is reflected immediately. Read-only for now (it explains and analyses; it
doesn't edit the plan).
"""

from flask import Blueprint, jsonify, request

import ai_client
import reckon_client
from models import Plan
from plan_math import plan_view

bp = Blueprint("ai", __name__, url_prefix="/api/plans")

_TYPE_LABEL = {
    "cpff": "Cost Plus Fixed Fee",
    "cpaf": "Cost Plus Award Fee",
    "ffp": "Firm Fixed Price",
    "internal": "Internal / IRAD (no fee)",
}

_SYSTEM = (
    "You help a program manager or functional manager build and sanity-check a project's plan: "
    "labor hours by category by week, priced from historical rates, against the contract. Ground "
    "every answer in the plan data below — never give generic estimating advice unconnected to "
    "this plan. Undistributed budget is contract budget (excluding fee) not yet planned into "
    "work; it is normal while a plan is incomplete and a problem only when negative. If asked "
    "about something the data can't answer, say so plainly rather than guessing."
)


def _money(n):
    return "not set" if n is None else f"${n:,.0f}"


def _context_lines(plan: Plan) -> list[str]:
    rates, _ = reckon_client.fetch_rates()
    burden, _ = reckon_client.fetch_burden()
    v = plan_view(plan, rates, burden)
    t = v["totals"]
    lines = [
        f'Project: "{plan.project_name}"' + (f" ({plan.portfolio_name})" if plan.portfolio_name else ""),
        f"Contract type: {_TYPE_LABEL.get(plan.contract_type, plan.contract_type)}",
        f"Contract value: {_money(plan.contract_value)}; budget base (excl. fee): {_money(t['contract_budget_base'])}",
        f"Fee: {_money(t['fee'])} ({plan.fee_percent:g}%)"
        + (f"; award fee pool {_money(t['award_fee'])} ({plan.award_fee_percent:g}%)" if plan.contract_type == "cpaf" else ""),
        f"Planned cost (all types, {'burdened' if plan.include_burden else 'direct, no burden'}): {_money(t['cost'])} — "
        f"labor {_money(t['labor_cost'])} ({t['hours']:,.0f} h), materials {_money(t['material_cost'])}, "
        f"subcontracts {_money(t['subcontract_cost'])}, services {_money(t['services_cost'])}, travel {_money(t['travel_cost'])}, "
        f"other {_money(t['other_cost'])}; undistributed budget {_money(t['undistributed'])}"
        + (f" ({t['undistributed_pct']}% of budget base)" if t["undistributed_pct"] is not None else ""),
        f"Plan window: {v['weeks'][0]} for {plan.week_count} weeks; {plan.hours_per_fte_week:g} hours = 1 FTE-week.",
        "",
        "Labor lines (category, WBS, effective $/h, total hours, total cost):",
    ]
    for line in v["lines"]:
        active = sorted(w for w, h in line["hours"].items() if h > 0)
        span = f", weeks {active[0]} to {active[-1]}" if active else ", no hours yet"
        rate = f"${line['effective_rate']:.0f}/h" if line["effective_rate"] is not None else "unpriced"
        lines.append(
            f"  - {line['category']}" + (f" [WBS {line['wbs']}]" if line["wbs"] else "")
            + f": {rate}, {line['total_hours']:,.0f} h, {_money(line['total_cost'])}{span}"
        )
    if v["costs"]:
        lines.append("")
        lines.append("Materials and other direct costs (kind, description, qty x unit cost = total, when):")
        for c in v["costs"]:
            when = (
                ", ".join(f"{p['percent']:g}% on {p['date']}" for p in c["phases"])
                if c["phases"] else (c["need_date"] or "no date")
            )
            lines.append(
                f"  - {c['kind']}: {c['description'] or '(no description)'}"
                + (f" [{c['vendor']}]" if c["vendor"] else "")
                + f" — {c['qty']:g} x {_money(c['unit_cost'])} = {_money(c['total'])}, {when}"
            )
    if t["unpriced_hours"]:
        lines.append(f"NOTE: {t['unpriced_hours']:,.0f} hours have no rate.")
    return lines


@bp.post("/<plan_id>/chat")
def chat_about_plan(plan_id):
    if not ai_client.is_configured():
        return jsonify({"error": ai_client.NOT_CONFIGURED_MESSAGE}), 200
    body = request.get_json(force=True) or {}
    messages = body.get("messages")
    if not messages or not isinstance(messages, list):
        return jsonify({"error": "messages (a non-empty list) is required"}), 400
    plan = Plan.query.get_or_404(plan_id)
    system = _SYSTEM + "\n\n" + "\n".join(_context_lines(plan))
    return jsonify({"reply": ai_client.chat(messages=messages, system=system, max_tokens=1024)})
