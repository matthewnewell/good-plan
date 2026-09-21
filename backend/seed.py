"""
Demo seed — weekly labor plans for the demo projects in Conway's Depot's story (fixed ids from that
repo's demo_data.py, so a plan lines up with its project on a fresh clone). Three awarded projects
plus a large pursuit, priced from Reckon's rate table at read time (nothing here stores a rate).

Each plan is built the way a planner would: labor categories, each stepping up and down over the
schedule as FTE runs (a role rarely runs flat for a whole program). The pursuit plan starts in the
future; the awarded ones started a few weeks ago, so their charts show a past and a future.
Contract values are chosen so the labor share is realistic — material, subcontract and travel
(next slice) make up the rest of the cost.
"""

import math
from datetime import date, timedelta

from db import db
from models import CostLine, CostPhase, LaborLine, LaborWeek, Plan
from plan_math import monday_of

BRACKET = ("ff5bfe0b-7b18-4337-a464-6517c6f6c13b", "Bracket Assembly Program", "Industrial Programs")
NACELLE = ("35fe3413-20e9-4762-8828-029ecade70c2", "Nacelle Fairing Retrofit", "Industrial Programs")
RADAR = ("2a9c5e71-84d3-4f0b-b6a2-c13e7d9f5a08", "Radar Housing Production", "Defense Systems")
COASTAL = ("d4e7a1b9-5c28-4360-9f1a-e83b0c6d72f5", "Prospect: Coastal Patrol Recompete", "Defense Systems")

# project -> (contract value, fee %, weeks before this Monday the plan starts, window weeks,
#             [(category, wbs, [(fte, first week, last week)], note)])   weeks are 0-based offsets
_PLANS = {
    BRACKET: (1_200_000, 8.0, 4, 44, [
        ("Program Manager", "1.1", [(0.25, 0, 40)], None),
        ("Systems Engineer", "1.2", [(1.0, 0, 9)], "Requirements and architecture through PDR."),
        ("Mechanical Engineer", "1.3", [(1.5, 1, 14), (0.5, 15, 30)], "Design through CDR, then sustaining engineering."),
        ("Manufacturing Engineer", "1.4", [(1.0, 6, 30)], None),
        ("Machinist", "2.1", [(2.0, 10, 28)], None),
        ("Quality Inspector", "2.2", [(0.5, 14, 40)], None),
        ("Mission Assurance Engineer", "3.1", [(0.5, 8, 40)], "First-article inspection and KC-1 sampling."),
    ]),
    NACELLE: (850_000, 8.0, 4, 40, [
        ("Program Manager", "1.1", [(0.25, 0, 30)], None),
        ("Mechanical Engineer", "1.3", [(1.0, 0, 12)], None),
        ("Composite Technician", "2.1", [(2.5, 8, 30)], "Lay-up capacity is the constraint this quarter."),
        ("Quality Inspector", "2.2", [(1.0, 12, 34)], "NDT-heavy retrofit — higher inspection ratio than a new build."),
        ("Mission Assurance Engineer", "3.1", [(0.5, 6, 34)], None),
    ]),
    RADAR: (3_900_000, 8.0, 6, 48, [
        ("Program Manager", "1.1", [(0.5, 0, 46)], None),
        ("Systems Engineer", "1.2", [(1.0, 0, 8)], None),
        ("Mechanical Engineer", "1.3", [(2.0, 0, 14)], None),
        ("Manufacturing Engineer", "1.4", [(1.5, 4, 42)], None),
        ("Supply Chain Analyst", "1.5", [(0.5, 0, 30)], "Titanium forging expedite."),
        ("Machinist", "2.1", [(2.0, 10, 18), (4.0, 19, 40)], "Steps up once the forging lands."),
        ("Quality Inspector", "2.2", [(1.5, 12, 46)], None),
        ("Mission Assurance Engineer", "3.1", [(1.0, 10, 46)], "First-article gates after units 2 and 12."),
        ("Test Technician", "3.2", [(1.0, 28, 46)], None),
    ]),
    COASTAL: (6_400_000, 8.0, 0, 60, [
        ("Program Manager", "1.1", [(1.0, 0, 58)], None),
        ("Systems Engineer", "1.2", [(3.0, 4, 24)], None),
        ("Electrical Engineer", "1.3", [(3.0, 8, 30)], None),
        ("Software Engineer", "1.4", [(4.0, 10, 40)], "Sensor fusion and operator interface."),
        ("Mechanical Engineer", "1.5", [(2.0, 8, 30)], None),
        ("Mission Assurance Engineer", "3.1", [(1.0, 12, 58)], None),
        ("Test Technician", "3.2", [(2.0, 30, 56)], None),
    ]),
}


# Team-size multiplier per project, applied to every FTE below — the FTE figures are the *shape*
# (who ramps when); this sets how big the program is. A plan is built PER PERSON: a category that
# needs 2.5 FTE becomes three lines (1.0, 1.0, 0.5), because a line is one position a functional
# manager fills with one person, and no person should be planned above 1.0 FTE.
_TEAM_SCALE = {BRACKET: 1.0, NACELLE: 1.0, RADAR: 1.5, COASTAL: 1.5}

# contract type, fee % (fixed fee / base fee / target profit), award-fee pool % — most of ours are CPFF
_TERMS = {
    BRACKET: ("cpff", 8.0, 0.0),
    NACELLE: ("ffp", 10.0, 0.0),
    RADAR: ("cpaf", 6.0, 3.0),
    COASTAL: ("cpff", 8.0, 0.0),
}


def seed_if_empty():
    if Plan.query.count() > 0:
        return

    this_monday = monday_of(date.today())
    for (project_id, name, portfolio), (tcv, fee, weeks_back, window, lines) in _PLANS.items():
        scale = _TEAM_SCALE[project_id, name, portfolio]
        start = this_monday - timedelta(weeks=weeks_back)
        plan = Plan(
            depot_project_id=project_id, project_name=name, portfolio_name=portfolio,
            contract_value=tcv, include_burden=True,
            contract_type=_TERMS[project_id, name, portfolio][0], fee_percent=_TERMS[project_id, name, portfolio][1],
            award_fee_percent=_TERMS[project_id, name, portfolio][2],
            start_week=start, week_count=window,
        )
        db.session.add(plan)
        db.session.flush()
        position = 0
        for category, wbs, runs, note in lines:
            people = max(1, math.ceil(max(fte * scale for fte, _, _ in runs) - 1e-9))
            for k in range(people):
                weeks_hours = {}
                for fte, first, last in runs:
                    share = min(1.0, max(0.0, fte * scale - k))
                    if share <= 0:
                        continue
                    for w in range(first, min(last, window - 1) + 1):
                        weeks_hours[w] = round(share * 40.0, 2)
                if not weeks_hours:
                    continue
                line = LaborLine(plan_id=plan.id, category=category, wbs=wbs, note=note if k == 0 else None, position=position)
                position += 1
                db.session.add(line)
                db.session.flush()
                for w, hours in weeks_hours.items():
                    db.session.add(LaborWeek(line_id=line.id, week_start=start + timedelta(weeks=w), hours=hours))
    db.session.commit()


# project -> [(kind, description, vendor, wbs, qty, unit cost, need week offset, [(week offset, percent)] or None)]
# Offsets are weeks from the plan's start. Materials are estimates (free-typed on purpose); the
# amounts are chosen so each plan lands with a different amount of budget still undistributed.
_COSTS = {
    BRACKET: [
        ("material", "Long-lead casting, bracket body", "Ridgeline Foundry", "2.1", 24, 6800, 10, None),
        ("material", "Raw bar stock", "Alcoa distributor", "2.1", 1, 54000, 6, None),
        ("material", "Fastener kit", "Fastenal", "2.1", 240, 41, 16, None),
        ("subcontract", "Heat treat and NDT", "Precision Thermal", "2.3", 1, 92000, 12, [(12, 50), (22, 50)]),
        ("services", "Fixture design consulting", "Tooling Partners", "1.4", 1, 28000, 4, None),
        ("travel", "Customer PDR / CDR trips (4 travelers, 2 trips)", None, "1.1", 8, 1621, 8, None),
    ],
    NACELLE: [
        ("material", "Carbon prepreg", "Hexcel", "2.1", 18, 3900, 4, None),
        ("material", "Honeycomb core", "Hexcel", "2.1", 60, 620, 6, None),
        ("material", "Bagging consumables", None, "2.1", 1, 22000, 8, None),
        ("subcontract", "NDI inspection", "Sonic NDT Labs", "2.2", 1, 64000, 14, [(14, 40), (28, 60)]),
        ("services", "Autoclave overflow cure time", "Aero Cure Services", "2.1", 1, 35000, 10, None),
        ("travel", "Fleet site visits (2 travelers, 3 trips)", None, "1.1", 6, 1500, 12, None),
    ],
    RADAR: [
        ("material", "Titanium forging blanks", "Tri-State Forge", "2.1", 52, 9800, 12, None),
        ("material", "Connector kits", "Amphenol", "2.1", 52, 640, 20, None),
        ("material", "Hardware and seals lot", None, "2.1", 1, 61000, 18, None),
        ("subcontract", "Anodize and chem film", "Meridian Finishing", "2.4", 1, 180000, 16, [(16, 25), (24, 25), (32, 25), (40, 25)]),
        ("services", "CMM programming", "Metrology Works", "3.1", 1, 46000, 6, None),
        ("travel", "Customer reviews (3 travelers, 6 trips)", None, "1.1", 18, 1900, 14, None),
    ],
    COASTAL: [
        ("material", "Prototype sensor units", None, "2.1", 4, 118000, 30, None),
        ("material", "Racks and cabling lot", None, "2.1", 1, 96000, 26, None),
        ("subcontract", "Sensor vendor development", "Aurora Sensors", "2.2", 1, 1350000, 12, [(12, 20), (28, 30), (44, 30), (56, 20)]),
        ("services", "Test range time", "Coastal Test Range", "3.2", 1, 210000, 40, [(40, 50), (48, 50)]),
        ("travel", "Customer and test-range trips (4 travelers, 10 trips)", None, "1.1", 40, 2300, 20, None),
    ],
}


def seed_costs_if_missing():
    """Materials and other direct costs for the demo plans. Idempotent: a plan that already has any
    cost line is left alone, so it also fills in a live database without touching what's there."""
    for (project_id, _name, _portfolio), rows in _COSTS.items():
        plan = Plan.query.filter_by(depot_project_id=project_id).first()
        if plan is None or plan.cost_lines:
            continue
        for position, (kind, description, vendor, wbs, qty, unit, offset, phases) in enumerate(rows):
            line = CostLine(
                plan_id=plan.id, kind=kind, description=description, vendor=vendor, wbs=wbs,
                qty=qty, unit_cost=unit, need_date=plan.start_week + timedelta(weeks=offset), position=position,
            )
            db.session.add(line)
            db.session.flush()
            for w, pct in phases or []:
                db.session.add(CostPhase(line_id=line.id, date=plan.start_week + timedelta(weeks=w), percent=pct))
    db.session.commit()
