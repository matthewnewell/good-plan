"""
The plan's arithmetic, kept out of the routes so it is easy to test: week windows, pricing a line,
and rolling a plan up into weekly hours/cost and the budget-vs-contract picture.
"""

from datetime import date, timedelta

from models import CostLine, LaborLine, Plan

DEFAULT_BURDEN = {"material": 1.13, "subcontract": 1.08, "services": 1.08, "travel": 1.08, "other": 1.08}


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def window_weeks(plan: Plan) -> list[date]:
    return [plan.start_week + timedelta(weeks=i) for i in range(plan.week_count)]


def line_rates(plan: Plan, line: LaborLine, rates: dict[str, dict]) -> dict:
    """Direct rate, burden factor and the effective (loaded if burden is on) rate for a line.
    `effective` is None when there's neither an override nor a rate for the category."""
    known = rates.get(line.category)
    direct = line.rate_override if line.rate_override is not None else (known["avg_rate"] if known else None)
    factor = (known["burden_factor"] if known else 1.0) if plan.include_burden else 1.0
    effective = round(direct * factor, 4) if direct is not None else None
    return {"direct_rate": direct, "burden_factor": factor, "effective_rate": effective}


def cost_line_total(line: CostLine) -> float:
    return (line.qty or 0.0) * (line.unit_cost or 0.0)


def cost_factor(plan: Plan, kind: str, burden: dict[str, float]) -> float:
    """The burden multiplier for a cost line's kind (1.0 when burden is off)."""
    return burden.get(kind, DEFAULT_BURDEN.get(kind, 1.0)) if plan.include_burden else 1.0


def cost_events(line: CostLine) -> list[tuple[date, float]]:
    """When a cost line's money lands: its milestones, else its single need date, else nowhere
    (unscheduled — counted in the totals but not on any week)."""
    total = cost_line_total(line)
    if line.phases:
        return [(p.date, total * p.percent / 100.0) for p in line.phases]
    return [(line.need_date, total)] if line.need_date else []


def plan_view(plan: Plan, rates: dict[str, dict], burden: dict[str, float] | None = None) -> dict:
    burden = burden or DEFAULT_BURDEN
    weeks = window_weeks(plan)
    iso = [w.isoformat() for w in weeks]

    hours_by_week = {w: 0.0 for w in iso}
    cost_by_week = {w: 0.0 for w in iso}
    total_hours = 0.0
    total_cost = 0.0
    unpriced_hours = 0.0
    lines_out = []

    for line in plan.lines:
        r = line_rates(plan, line, rates)
        hours = {w.week_start.isoformat(): w.hours for w in line.weeks}
        line_hours = sum(hours.values())
        cost = line_hours * r["effective_rate"] if r["effective_rate"] is not None else None
        for wk, h in hours.items():
            if wk in hours_by_week:
                hours_by_week[wk] += h
                if r["effective_rate"] is not None:
                    cost_by_week[wk] += h * r["effective_rate"]
        total_hours += line_hours
        if cost is None:
            unpriced_hours += line_hours
        else:
            total_cost += cost
        lines_out.append({
            "id": line.id,
            "category": line.category,
            "wbs": line.wbs,
            "rate_override": line.rate_override,
            "note": line.note,
            **r,
            "hours": hours,
            "total_hours": round(line_hours, 2),
            "total_cost": round(cost, 2) if cost is not None else None,
        })

    # ── everything that isn't labor: materials + other direct costs ──
    labor_cost = total_cost
    kind_cost = {k: 0.0 for k in ("material", "subcontract", "services", "travel", "other")}
    week_by_group = {
        "labor": dict(cost_by_week),
        "material": {w: 0.0 for w in iso},
        "odc": {w: 0.0 for w in iso},
    }
    outside_window = 0.0
    unscheduled = 0.0
    costs_out = []
    for c in plan.cost_lines:
        total = cost_line_total(c)
        factor = cost_factor(plan, c.kind, burden)
        loaded = total * factor
        kind_cost[c.kind] = kind_cost.get(c.kind, 0.0) + loaded
        events = cost_events(c)
        if not events:
            unscheduled += loaded
        group = "material" if c.kind == "material" else "odc"
        for when, amount in events:
            wk = monday_of(when).isoformat()
            if wk in cost_by_week:
                cost_by_week[wk] += amount * factor
                week_by_group[group][wk] += amount * factor
            else:
                outside_window += amount * factor
        costs_out.append({
            "id": c.id, "kind": c.kind, "description": c.description, "vendor": c.vendor, "wbs": c.wbs,
            "qty": c.qty, "unit_cost": c.unit_cost, "total": round(total, 2),
            "factor": factor, "loaded_total": round(loaded, 2),
            "need_date": c.need_date.isoformat() if c.need_date else None,
            "phases": [{"id": p.id, "date": p.date.isoformat(), "percent": p.percent} for p in c.phases],
            "detail": c.detail, "note": c.note,
        })
    odc_cost = kind_cost["subcontract"] + kind_cost["services"] + kind_cost["travel"] + kind_cost["other"]
    total_cost = labor_cost + kind_cost["material"] + odc_cost

    tcv = plan.contract_value
    base_pct = 0.0 if plan.contract_type == "internal" else (plan.fee_percent or 0.0)
    award_pct = (plan.award_fee_percent or 0.0) if plan.contract_type == "cpaf" else 0.0
    # Contract budget base: what the contract funds in cost, i.e. the value with fee taken out.
    cbb = tcv / (1 + (base_pct + award_pct) / 100.0) if tcv is not None else None
    fee = cbb * base_pct / 100.0 if cbb is not None else None
    award_fee = cbb * award_pct / 100.0 if cbb is not None else None
    undistributed = (cbb - total_cost) if cbb is not None else None
    margin = (tcv - total_cost) if tcv is not None else None
    return {
        "id": plan.id,
        "depot_project_id": plan.depot_project_id,
        "project_name": plan.project_name,
        "portfolio_name": plan.portfolio_name,
        "contract_value": tcv,
        "contract_type": plan.contract_type,
        "include_burden": plan.include_burden,
        "fee_percent": plan.fee_percent,
        "award_fee_percent": plan.award_fee_percent,
        "hours_per_fte_week": plan.hours_per_fte_week,
        "start_week": plan.start_week.isoformat(),
        "week_count": plan.week_count,
        "weeks": iso,
        "lines": lines_out,
        "costs": costs_out,
        "totals": {
            "hours": round(total_hours, 2),
            "cost": round(total_cost, 2),
            "labor_cost": round(labor_cost, 2),
            "material_cost": round(kind_cost["material"], 2),
            "subcontract_cost": round(kind_cost["subcontract"], 2),
            "services_cost": round(kind_cost["services"], 2),
            "travel_cost": round(kind_cost["travel"], 2),
            "other_cost": round(kind_cost["other"], 2),
            "odc_cost": round(odc_cost, 2),
            "cost_outside_window": round(outside_window, 2),
            "cost_unscheduled": round(unscheduled, 2),
            "cost_by_week_kind": {g: {k: round(v, 2) for k, v in d.items()} for g, d in week_by_group.items()},
            "contract_budget_base": round(cbb, 2) if cbb is not None else None,
            "fee": round(fee, 2) if fee is not None else None,
            "award_fee": round(award_fee, 2) if award_fee is not None else None,
            "undistributed": round(undistributed, 2) if undistributed is not None else None,
            "undistributed_pct": round(undistributed / cbb * 100, 1) if undistributed is not None and cbb else None,
            "margin": round(margin, 2) if margin is not None else None,
            "margin_pct": round(margin / tcv * 100, 1) if margin is not None and tcv else None,
            "unpriced_hours": round(unpriced_hours, 2),
            "hours_by_week": {k: round(v, 2) for k, v in hours_by_week.items()},
            "cost_by_week": {k: round(v, 2) for k, v in cost_by_week.items()},
        },
    }


def time_phased_budget(plan: Plan, rates: dict[str, dict], burden: dict[str, float] | None = None) -> dict:
    """The plan's budget spread over time, per WBS element: what Reckon reads as planned value.
    {code: {week: amount}}, loaded exactly as plan_view prices it (labor at each line's effective
    rate, costs at their kind's burden, landing on their need date or milestones). Anything with no
    WBS code lands under None; costs with no date are left out of the weeks but kept in `undated`."""
    burden = burden or DEFAULT_BURDEN
    by_wbs: dict[str | None, dict[str, float]] = {}
    undated: dict[str | None, float] = {}

    def add(code, week: str, amount: float):
        row = by_wbs.setdefault(code, {})
        row[week] = row.get(week, 0.0) + amount

    for line in plan.lines:
        rate = line_rates(plan, line, rates)["effective_rate"]
        if rate is None:
            continue
        for w in line.weeks:
            if w.hours:
                add(line.wbs, w.week_start.isoformat(), w.hours * rate)
    for c in plan.cost_lines:
        factor = cost_factor(plan, c.kind, burden)
        events = cost_events(c)
        if not events:
            undated[c.wbs] = undated.get(c.wbs, 0.0) + cost_line_total(c) * factor
        for when, amount in events:
            add(c.wbs, monday_of(when).isoformat(), amount * factor)
    return {
        "by_wbs": {code: {w: round(v, 2) for w, v in sorted(row.items())} for code, row in by_wbs.items()},
        "undated": {code: round(v, 2) for code, v in undated.items()},
    }


def demand_runs(plan: Plan) -> list[dict]:
    """The legacy `/api/demand` shape Labor Supply & Demand reads: one row per run of consecutive
    weeks at the same FTE, per labor line — so a plan that steps a role up and down over time
    comes out as several rows, exactly as the old hand-entered lines did."""
    out = []
    hpw = plan.hours_per_fte_week or 40.0
    for line in plan.lines:
        weeks = sorted((w.week_start, w.hours) for w in line.weeks if w.hours > 0)
        run_start = prev = None
        run_hours = None
        for start, hours in weeks + [(None, None)]:
            continues = (
                start is not None and prev is not None and start == prev + timedelta(weeks=1) and hours == run_hours
            )
            if continues:
                prev = start
                continue
            if run_start is not None:
                out.append({
                    "id": f"{line.id}:{run_start.isoformat()}",
                    "project": plan.project_name,
                    "portfolio": plan.portfolio_name,
                    "role": line.category,
                    "fte": round(run_hours / hpw, 2),
                    "start_date": run_start.isoformat(),
                    "end_date": (prev + timedelta(days=6)).isoformat(),
                    "note": line.note,
                    "created_at": plan.created_at.isoformat(),
                })
            run_start, prev, run_hours = start, start, hours
    return out
