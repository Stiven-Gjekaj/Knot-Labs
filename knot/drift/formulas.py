"""Ranking formulas for Drift."""
from __future__ import annotations

from datetime import datetime
from typing import Dict

from knot.common.time import now_iso, parse_iso

WEIGHTS = {"views": 1, "likes": 5, "comments": 8, "shares": 12, "gifts": 20}
HALF_LIFE_HOURS = 24


def raw_score(eng: Dict[str, int]) -> int:
    return sum(WEIGHTS[k] * eng.get(k, 0) for k in WEIGHTS)


def apply_decay(score: float, created_at: str) -> float:
    now = datetime.fromisoformat(now_iso())
    created = parse_iso(created_at)
    age_hours = (now - created).total_seconds() / 3600
    decay = 0.5 ** (age_hours / HALF_LIFE_HOURS)
    return score * decay
