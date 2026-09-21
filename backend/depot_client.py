"""
A thin, read-only client for Conway's Depot's own API — same reasoning as every sibling app
that stays in sync with the Depot rather than keeping its own copy (see Task Master's own
depot_client.py). Every call here is server-to-server and tolerant of the Depot being
unreachable: every function returns `None` on any failure rather than raising, so a caller
always has one thing to check.
"""

import os

import httpx

DEPOT_API_URL = os.environ.get("DEPOT_API_URL", "http://localhost:8090").rstrip("/")


def fetch_projects() -> list[dict] | None:
    """Every project Conway's Depot knows about, full `to_dict()` shape — including
    `has_manufacturing`, the field MARTI's hybrid manufacturing-project trigger reads. MARTI
    never keeps its own copy of a project's core facts, same discipline Task Master already
    follows for people/projects."""
    try:
        r = httpx.get(f"{DEPOT_API_URL}/api/projects", timeout=3.0)
        if r.status_code != 200:
            return None
        return r.json()
    except httpx.HTTPError:
        return None


def fetch_project(project_id: str) -> dict | None:
    """One project's full detail — used when MARTI needs more than the list view carries
    (e.g. when a plan is created for a project)."""
    try:
        r = httpx.get(f"{DEPOT_API_URL}/api/projects/{project_id}", timeout=3.0)
        if r.status_code != 200:
            return None
        return r.json()
    except httpx.HTTPError:
        return None
