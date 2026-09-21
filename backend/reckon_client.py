"""
Read-only client for Reckon's labor-rate table (GET /api/rates) — Reckon owns rates because the
history they're averaged from is actuals, which live there. Server-to-server, tolerant of Reckon
being down: the last table that loaded successfully is kept in memory and reused (flagged stale),
so a plan can still be priced during a Reckon restart; only a cold start with Reckon down has no
rates at all, and callers get `reachable=False` to say so plainly.
"""

import os

import httpx

RECKON_API_URL = os.environ.get("RECKON_API_URL", "http://localhost:8103").rstrip("/")

_last_good: dict[str, dict] = {}


def fetch_rates() -> tuple[dict[str, dict], bool]:
    """Returns ({category name: {avg_rate, burden_factor, basis_hours}}, reachable)."""
    global _last_good
    try:
        r = httpx.get(f"{RECKON_API_URL}/api/rates", timeout=2.0)
        r.raise_for_status()
        _last_good = {
            row["name"]: {
                "avg_rate": row["avg_rate"],
                "burden_factor": row.get("burden_factor", 1.0),
                "basis_hours": row.get("basis_hours", 0),
            }
            for row in r.json()
        }
        return _last_good, True
    except (httpx.HTTPError, ValueError, KeyError):
        return _last_good, False


# Used until Reckon has answered at least once, so a cold start with Reckon down still prices.
DEFAULT_BURDEN = {"material": 1.13, "subcontract": 1.08, "services": 1.08, "travel": 1.08, "other": 1.08}
_last_burden: dict[str, float] = {}


def fetch_burden() -> tuple[dict[str, float], bool]:
    """Returns ({cost kind: burden multiplier}, reachable) for the non-labor cost types."""
    global _last_burden
    try:
        r = httpx.get(f"{RECKON_API_URL}/api/burden", timeout=2.0)
        r.raise_for_status()
        _last_burden = {row["kind"]: row["burden_factor"] for row in r.json()}
        return _last_burden, True
    except (httpx.HTTPError, ValueError, KeyError):
        return (_last_burden or dict(DEFAULT_BURDEN)), False
