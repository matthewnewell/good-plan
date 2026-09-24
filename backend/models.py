"""
Models: Plan, LaborLine, LaborWeek.

Good Plan is the *plan* side of a deliberate split. A project records what it needs and what that
costs — before anyone has committed a person to it, and before any actual dollar is spent. Who is
actually assigned is Labor Supply & Demand's job; what was actually spent, and how that compares
to this plan, is Reckon's. Good Plan never stores an actual, and reads exactly two things from
outside: the project itself (Conway's Depot) and the labor-rate table (Reckon).

A Plan belongs to one Conway's Depot project, by its id — any phase, pursuit included (in pursuit
the plan is the bid estimate). Slice 1 models labor: a Plan has LaborLines (a labor category, an
optional WBS element / charge code, an optional direct-rate override), and each line has weekly
hours (LaborWeek, one row per Monday). Hours are the source of truth; FTE is derived from them
(hours / `hours_per_fte_week`).

Pricing: a line's rate is its override, else Reckon's historical average for the category (both
DIRECT rates). If `include_burden` is on (the default), the category's burden multiplier — fringe,
overhead and G&A spread on top of labor — is applied.

Contract type (`contract_type`) says how the contract value divides up:
  - cpff  Cost Plus Fixed Fee — value = estimated cost + a FIXED fee. Most of our work.
  - cpaf  Cost Plus Award Fee — value = estimated cost + a fixed base fee + an award-fee pool that
          is earned (at risk), not guaranteed.
  - ffp   Firm Fixed Price — value is the price; `fee_percent` is the planned (target) profit.
  - internal  Internal / IRAD — no fee; the contract value is simply the budget.
`fee_percent` and `award_fee_percent` are percentages of the ESTIMATED COST, so the contract budget
base (CBB) — the cost the contract funds, excluding fee — is contract_value / (1 + fee% + award%).
The fee is therefore fixed by the contract; it does not move when the plan's cost does. What moves
is the UNDISTRIBUTED BUDGET: CBB minus the cost planned so far — budget that is authorized but not
yet planned into work. It shrinks as the plan fills in (materials, subcontracts, travel) and goes
negative if the plan costs more than the contract funds.

Everything that isn't labor is a CostLine: materials, and the "other direct costs" — subcontracts,
services, travel and other. A line is a description, a quantity and a unit cost (its total is the
product), and WHEN it lands: a single need date, or milestones (CostPhase: date + percent, summing
to 100) that override it — a subcontract paid 30/30/40 on three dates. Free-typed for now (a material
is an estimate at planning time; linking to MARTI's material numbers can come later). Each kind has
its own burden multiplier, held in Reckon: materials carry handling + G&A, the rest G&A only.

WBS: every line (labor, material, ODC) sits on one work package, a LEAF of the project's WBS, by
its code (`wbs`, e.g. "1.3"). Scope Manager owns the WBS (scope and progress); Good Plan budgets
against it and never edits it. A pursuit has no WBS there yet, so Good Plan holds a DRAFT
(`WbsElement`) to estimate against. The estimate is what forward-looking staffing reads. At award
the draft is sent to Scope Manager, which owns it from then on. Pursuit capture and proposal effort
itself charges to the pursuit's B&P (bid and proposal) charge number from S4, not to this WBS.
"""

from datetime import datetime, timezone

from db import _uuid, db


def _now():
    return datetime.now(timezone.utc)


CONTRACT_TYPES = ("cpff", "cpaf", "ffp", "internal")
COST_KINDS = ("material", "subcontract", "services", "travel", "other")


class Plan(db.Model):
    __tablename__ = "plan"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    depot_project_id = db.Column(db.String(36), nullable=False, unique=True, index=True)
    # Frozen display copies from the Depot at creation — same "denormalize the name so a renamed
    # or deleted project's plan still reads sensibly" pattern the other sibling apps use. The
    # derived /api/demand feed keys Labor Supply & Demand by project *name*, so it needs these.
    project_name = db.Column(db.String(200), nullable=False)
    portfolio_name = db.Column(db.String(200), nullable=True)

    contract_value = db.Column(db.Float, nullable=True)
    contract_type = db.Column(db.String(10), nullable=False, default="cpff")  # see CONTRACT_TYPES
    include_burden = db.Column(db.Boolean, nullable=False, default=True)
    fee_percent = db.Column(db.Float, nullable=False, default=8.0)  # fixed fee / base fee / target profit
    award_fee_percent = db.Column(db.Float, nullable=False, default=0.0)  # CPAF award pool only
    hours_per_fte_week = db.Column(db.Float, nullable=False, default=40.0)

    # The grid's window: `week_count` Mondays starting at `start_week`.
    start_week = db.Column(db.Date, nullable=False)
    week_count = db.Column(db.Integer, nullable=False, default=26)

    created_at = db.Column(db.DateTime, default=_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now, nullable=False)

    lines = db.relationship(
        "LaborLine", back_populates="plan", cascade="all, delete-orphan",
        order_by="LaborLine.position", lazy="selectin",
    )
    cost_lines = db.relationship(
        "CostLine", back_populates="plan", cascade="all, delete-orphan",
        order_by="CostLine.position", lazy="selectin",
    )


class LaborLine(db.Model):
    __tablename__ = "labor_line"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    plan_id = db.Column(db.String(36), db.ForeignKey("plan.id"), nullable=False, index=True)
    category = db.Column(db.String(120), nullable=False)
    # A WBS element / charge code — optional in the UI, but it's what lets Reckon compare plan to
    # actuals line for line instead of guessing a mapping. Mocked S4 for now.
    wbs = db.Column(db.String(60), nullable=True)
    rate_override = db.Column(db.Float, nullable=True)  # a DIRECT $/hour, before burden
    note = db.Column(db.Text, nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0)

    plan = db.relationship("Plan", back_populates="lines")
    weeks = db.relationship("LaborWeek", back_populates="line", cascade="all, delete-orphan", lazy="selectin")


class LaborWeek(db.Model):
    __tablename__ = "labor_week"
    __table_args__ = (db.UniqueConstraint("line_id", "week_start", name="uq_labor_week"),)

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    line_id = db.Column(db.String(36), db.ForeignKey("labor_line.id"), nullable=False, index=True)
    week_start = db.Column(db.Date, nullable=False)  # always a Monday
    hours = db.Column(db.Float, nullable=False)

    line = db.relationship("LaborLine", back_populates="weeks")


class CostLine(db.Model):
    __tablename__ = "cost_line"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    plan_id = db.Column(db.String(36), db.ForeignKey("plan.id"), nullable=False, index=True)
    kind = db.Column(db.String(12), nullable=False)  # see COST_KINDS
    description = db.Column(db.String(200), nullable=False, default="")
    vendor = db.Column(db.String(120), nullable=True)
    wbs = db.Column(db.String(60), nullable=True)
    qty = db.Column(db.Float, nullable=False, default=1.0)
    unit_cost = db.Column(db.Float, nullable=False, default=0.0)
    need_date = db.Column(db.Date, nullable=True)
    # Travel's calculator inputs (trips, travelers, airfare, lodging, nights, per diem, car) as JSON,
    # so the line can be re-opened and edited; qty and unit_cost hold the resulting person-trips
    # and per-person-trip cost.
    detail = db.Column(db.Text, nullable=True)
    note = db.Column(db.Text, nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0)

    plan = db.relationship("Plan", back_populates="cost_lines")
    phases = db.relationship(
        "CostPhase", back_populates="line", cascade="all, delete-orphan",
        order_by="CostPhase.date", lazy="selectin",
    )


class CostPhase(db.Model):
    __tablename__ = "cost_phase"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    line_id = db.Column(db.String(36), db.ForeignKey("cost_line.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False)
    percent = db.Column(db.Float, nullable=False)

    line = db.relationship("CostLine", back_populates="phases")


class WbsElement(db.Model):
    """One element of a pursuit's draft WBS. Codes carry the tree ("1.2" sits under "1"); a leaf is
    an element no other code extends. Only used while Scope Manager has no WBS for the project."""

    __tablename__ = "wbs_element"
    __table_args__ = (db.UniqueConstraint("plan_id", "code", name="uq_wbs_element_code"),)

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    plan_id = db.Column(db.String(36), db.ForeignKey("plan.id"), nullable=False, index=True)
    code = db.Column(db.String(30), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=_now, nullable=False)
