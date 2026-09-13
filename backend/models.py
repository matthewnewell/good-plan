"""
Models: DemandLine.

Good Plan is the demand side of a two-app split, on purpose. A project records what labor it
needs — a role, how much of it (FTE), and when — as its own plan, before anyone has committed a
real person to it. That commitment is a different job, done by a different persona (a
functional/resource manager who actually owns people, not a project team), and belongs to a
complementary organizational app — working name "Big Plan" — not built here. Collapsing "what a
project needs" and "who's actually being given to it" into one app is exactly the shape of
mistake this ecosystem has already learned from once (BurnedValue tried to be the plan and the
execution and the everything-else in one place); Good Plan stays the plan.

`project`/`portfolio` are plain-text labels — the same cross-app-by-convention pattern as every
other sibling app here, not a foreign key into some shared database.

v1 is deliberately staffing-only. Budget, scope, material cost, subcontract cost, and travel
cost were all named as things a fuller "plan" might eventually carry, but labor demand is the
actual driving use case — the other categories are not modeled here yet.
"""

from datetime import datetime, timezone

from db import _uuid, db


def _now():
    return datetime.now(timezone.utc)


class DemandLine(db.Model):
    """One line of labor demand: a project needs `fte` of `role` from `start_date` to
    `end_date`. Deliberately just a fact a project is asserting about its own plan — not a
    commitment, not an assignment of a real person, and not validated against anyone's actual
    availability (Good Plan has no idea who's available; that knowledge, and the authority to
    commit it, belongs to Big Plan). Multiple lines for the same role are normal — demand for a
    role that steps up or down over time is just two (or more) lines, not one line with a
    curve."""

    __tablename__ = "demand_line"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    project = db.Column(db.String(200), nullable=False, index=True)
    portfolio = db.Column(db.String(200), nullable=True, index=True)
    role = db.Column(db.String(200), nullable=False, index=True)
    fte = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=_now, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project": self.project,
            "portfolio": self.portfolio,
            "role": self.role,
            "fte": self.fte,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "note": self.note,
            "created_at": self.created_at.isoformat(),
        }
