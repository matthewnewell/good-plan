"""
Client for Scope Manager, which owns each project's WBS. Good Plan reads it to know the work
packages its lines may sit on, and writes to it exactly once per project: sending a pursuit's
draft WBS over at award. Tolerant: a read returns None when Scope Manager can't be reached.
"""

import os

import httpx

SCOPE_MANAGER_URL = os.environ.get("SCOPE_MANAGER_URL", "http://localhost:8097").rstrip("/")
SCOPE_MANAGER_WEB_URL = os.environ.get("SCOPE_MANAGER_WEB_URL", "http://localhost:5183").rstrip("/")


def fetch_wbs(project_id: str) -> list[dict] | None:
    """The project's WBS elements (code, title, parent_id, leaf, charge_number, percent_complete),
    [] when it has none, None when Scope Manager is unreachable."""
    try:
        r = httpx.get(f"{SCOPE_MANAGER_URL}/api/wbs", params={"project_id": project_id}, timeout=3.0)
        r.raise_for_status()
        return r.json().get("elements", [])
    except httpx.HTTPError:
        return None


def import_wbs(project_id: str, project: str, portfolio: str | None, elements: list[dict], author: str | None):
    """(elements, error). Creates the project's WBS in Scope Manager from `[{code, title}]`."""
    try:
        r = httpx.post(
            f"{SCOPE_MANAGER_URL}/api/wbs/import",
            json={"project_id": project_id, "project": project, "portfolio": portfolio, "elements": elements, "author": author},
            timeout=5.0,
        )
    except httpx.HTTPError:
        return None, f"Scope Manager isn't reachable at {SCOPE_MANAGER_URL} right now."
    if r.status_code >= 400:
        try:
            return None, r.json().get("error") or f"Scope Manager returned {r.status_code}"
        except ValueError:
            return None, f"Scope Manager returned {r.status_code}"
    return r.json().get("elements", []), None


def tree_url(project_id: str) -> str:
    return f"{SCOPE_MANAGER_WEB_URL}/?project={project_id}"
