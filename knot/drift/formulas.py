"""Ranking formulas."""
from __future__ import annotations

from typing import Dict

from ..common.time import now_iso, parse_iso, hours_between

W_VIEW = 1
W_LIKE = 5
W_COMMENT = 8
W_SHARE = 12
W_GIFT = 20
HALF_LIFE_HOURS = 24


def decay(now: str, created_at: str) -> float:
    """Return time decay factor between 0 and 1."""
    age = hours_between(created_at, now)
    return 0.5 ** (age / HALF_LIFE_HOURS)


def score_raw(eng: Dict[str, int]) -> float:
    return (
        eng.get("views", 0) * W_VIEW
        + eng.get("likes", 0) * W_LIKE
        + eng.get("comments", 0) * W_COMMENT
        + eng.get("shares", 0) * W_SHARE
        + eng.get("gifts", 0) * W_GIFT
    )


def score(now: str, post: Dict) -> float:
    return score_raw(post.get("engagement", {})) * decay(now, post.get("created_at"))

