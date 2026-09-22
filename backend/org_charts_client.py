"""
Read-only client for Org Charts' functional taxonomy (GET /api/functions) — Org Charts owns it
because it also owns the roster each function's categories are staffed from. Used to build the
"pick a role" picker on a labor line: choose the Function, then the category inside it, instead
of free-typing a category name. Same tolerant-probe posture as reckon_client: a cold call with
Org Charts down gets an empty list plus a flag, not a crash.
"""

import os

import httpx

ORG_CHARTS_API_URL = os.environ.get("ORG_CHARTS_API_URL", "http://localhost:8095").rstrip("/")

_last_good: list[dict] = []


def fetch_functions() -> tuple[list[dict], bool]:
    """Returns ([{name, categories, manager_name}], reachable)."""
    global _last_good
    try:
        r = httpx.get(f"{ORG_CHARTS_API_URL}/api/functions", timeout=2.0)
        r.raise_for_status()
        _last_good = [
            {"name": f["name"], "categories": f["categories"], "manager_name": f.get("manager_name")}
            for f in r.json()
        ]
        return _last_good, True
    except (httpx.HTTPError, ValueError, KeyError):
        return _last_good, False
