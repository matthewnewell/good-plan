"""Smoke test against a throwaway DB (own DATA_DIR), never the real dev data."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os  # noqa: E402

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="goodplan-test-")

from app import create_app  # noqa: E402


def test_create_list_update_delete_demand_line():
    app = create_app()
    client = app.test_client()

    r = client.post("/api/demand", json={
        "project": "Test Program", "portfolio": "Test Portfolio", "role": "Machinist",
        "fte": 2.0, "start_date": "2026-01-01", "end_date": "2026-03-01",
    })
    assert r.status_code == 201, r.data
    line = r.get_json()
    assert line["fte"] == 2.0

    r = client.get("/api/demand?project=Test Program")
    assert r.status_code == 200
    assert len(r.get_json()) == 1

    r = client.put(f"/api/demand/{line['id']}", json={"fte": 3.0})
    assert r.status_code == 200
    assert r.get_json()["fte"] == 3.0

    r = client.delete(f"/api/demand/{line['id']}")
    assert r.status_code == 204

    r = client.get("/api/demand?project=Test Program")
    assert r.get_json() == []


def test_end_date_before_start_date_is_rejected():
    app = create_app()
    client = app.test_client()
    r = client.post("/api/demand", json={
        "project": "Test Program", "role": "Machinist", "fte": 1.0,
        "start_date": "2026-03-01", "end_date": "2026-01-01",
    })
    assert r.status_code == 400


def test_zero_or_negative_fte_is_rejected():
    app = create_app()
    client = app.test_client()
    r = client.post("/api/demand", json={
        "project": "Test Program", "role": "Machinist", "fte": 0,
        "start_date": "2026-01-01", "end_date": "2026-03-01",
    })
    assert r.status_code == 400
