# Good Plan

Define the labor a project needs, before anyone commits a person to it.

## The idea

A project's staffing story usually gets written down twice: once as a vague sentence in a
proposal, and once as a spreadsheet someone quietly maintains and nobody else can see. Good
Plan is the first one, made real: a project asserts its own labor demand — a role, how much of
it (FTE), and when — as a short list of lines, not a spreadsheet and not a guess dressed up as
a number.

This is deliberately half of a two-app split, not a full workforce planning suite:

1. **Demand, not commitment.** Good Plan only ever records what a project says it needs. It has
   no idea who's actually available, and doesn't pretend to — that knowledge, and the authority
   to commit a real person against it, belongs to a complementary organizational app (working
   name **Big Plan**) a functional/resource manager uses. Collapsing "what's needed" and "who's
   assigned" into one app is exactly the mistake an earlier tool in this ecosystem
   (BurnedValue) made trying to be the plan and the execution at once.
2. **One line per phase, not one number per role.** Demand for a role rarely holds flat for a
   whole program — a design-phase Mechanical Engineer ratio is not a build-phase ratio. Good
   Plan expects more than one line for the same role over different date ranges, not a single
   FTE value averaged across a project that doesn't move at one pace.
3. **No fake precision.** There's no computed "total FTE" rollup anywhere. Summing FTE across
   lines with different date ranges would imply a peak-concurrent-headcount number this app
   doesn't actually know — so it shows the real lines instead, sorted and filterable.

## Stack

Same as the rest of this ecosystem — Flask + SQLAlchemy + SQLite backend, React + TypeScript +
Vite frontend, tied in only by convention (plain-text `project`/`portfolio` labels), no shared
database.

## Running locally

```bash
# backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python app.py            # :8093, seeds demo data on first run

# frontend (separate terminal)
cd frontend
npm install
npm run dev                        # :5178, proxies /api to :8093
```

## Data model

- **DemandLine** — a project needs `fte` of `role` from `start_date` to `end_date`, with an
  optional note. That's the whole model. `project`/`portfolio` are plain-text labels, the same
  cross-app convention every sibling app here uses.

## Status

v1 — labor demand only. Budget, scope, material cost, subcontract cost, and travel cost were
all named as things a fuller "plan" might eventually carry; staffing is the actual driving use
case, so the rest isn't modeled yet.
