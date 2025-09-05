"""Time utilities."""
from __future__ import annotations

from datetime import datetime, timezone

ISO_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def now_iso() -> str:
    """Return current time in ISO8601 format with Zulu timezone."""
    return datetime.now(timezone.utc).strftime(ISO_FMT)


def parse_iso(s: str) -> datetime:
    """Parse ISO string produced by :func:`now_iso`."""
    try:
        return datetime.strptime(s, ISO_FMT).replace(tzinfo=timezone.utc)
    except ValueError:
        # Fallback for strings without microseconds
        return datetime.fromisoformat(s.replace("Z", "+00:00"))


def hours_between(t1: str | datetime, t2: str | datetime) -> float:
    """Return hours from t1 to t2 (t2 - t1)."""
    if isinstance(t1, str):
        t1 = parse_iso(t1)
    if isinstance(t2, str):
        t2 = parse_iso(t2)
    delta = t2 - t1
    return delta.total_seconds() / 3600.0

