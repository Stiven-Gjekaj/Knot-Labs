"""Time helpers for Knot."""
from __future__ import annotations

from datetime import datetime, timezone


def now_iso() -> str:
    """Return current time in ISO 8601 (UTC)."""
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: str) -> datetime:
    """Parse ISO 8601 string to datetime."""
    return datetime.fromisoformat(value)
