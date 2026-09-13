"""
Demo seed — labor demand for the same two demo projects Value Stream, Conway's Depot, and the
other sibling apps already share ("Demo: Bracket Assembly Program", "Demo: Nacelle Fairing
Retrofit"), portfolio "Industrial Programs" to match Conway's Depot's own seeded Portfolio.

Deliberately includes more than one line for the same role on the same project (Mechanical
Engineer on the Bracket program, in two different date ranges) — demand for a role that steps
up or down over time is normal, and the seed should show that rather than pretend every role is
one flat line for the whole program.
"""

from datetime import timedelta

from db import db
from models import DemandLine, _now

DAY = timedelta(days=1)
_PORTFOLIO = "Industrial Programs"
_BKT = "Demo: Bracket Assembly Program"
_NAC = "Demo: Nacelle Fairing Retrofit"

# project, role, fte, start_offset_days, end_offset_days, note
_LINES = [
    (_BKT, "Program Manager", 0.25, -30, 60, None),
    (_BKT, "Systems Engineer", 1.0, -30, 10,
     "Requirements and architecture through PDR."),
    (_BKT, "Mechanical Engineer", 1.5, -20, 15,
     "Design Definition through CDR."),
    (_BKT, "Mechanical Engineer", 0.5, 15, 45,
     "Design support during build — sustaining engineering, not full-time."),
    (_BKT, "Machinist", 2.0, 10, 45, None),
    (_BKT, "Quality Inspector", 0.5, 20, 60, None),
    (_NAC, "Program Manager", 0.25, -10, 90, None),
    (_NAC, "Mechanical Engineer", 1.0, -10, 20, None),
    (_NAC, "Machinist", 1.0, 15, 60, None),
    (_NAC, "Quality Inspector", 1.0, 20, 90,
     "NDT-heavy retrofit — higher inspection ratio than a new-build program."),
]


def seed_if_empty():
    if DemandLine.query.count() > 0:
        return

    today = _now()
    for project, role, fte, start_offset, end_offset, note in _LINES:
        db.session.add(DemandLine(
            project=project,
            portfolio=_PORTFOLIO,
            role=role,
            fte=fte,
            start_date=(today + start_offset * DAY).date(),
            end_date=(today + end_offset * DAY).date(),
            note=note,
            created_at=today,
        ))

    db.session.commit()
