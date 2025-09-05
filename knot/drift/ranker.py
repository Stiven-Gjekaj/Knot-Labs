"""Drift ranking operations."""
from __future__ import annotations

from dataclasses import asdict

from knot.common.time import now_iso
from .formulas import raw_score, apply_decay


def rank_post(post) -> float:
    """Update a post's rank score."""
    score = raw_score(post.engagement)
    score = apply_decay(score, post.created_at)
    post.rank_score = score
    post.last_ranked_at = now_iso()
    return score
