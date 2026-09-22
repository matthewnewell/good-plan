"""One-off: rename existing 'Program Manager' labor lines (a per-project, start/end role) to
'Project Engineer', matching the split between Program Management (owns the program, several
projects) and Project Engineer (owns one project) — see Org Charts' FUNCTION_CATEGORIES. Safe to
re-run; only touches rows still saying the old name."""

from app import create_app
from db import db
from models import LaborLine

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        rows = LaborLine.query.filter_by(category="Program Manager").all()
        for line in rows:
            line.category = "Project Engineer"
        db.session.commit()
        print(f"renamed {len(rows)} labor line(s)")
