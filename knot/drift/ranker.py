"""Drift ranking functions."""
from __future__ import annotations

from typing import List, Tuple

from .formulas import score
from ..common.time import now_iso


def rank_post(mesh, post_id: str) -> float:
    post = mesh.get_post(post_id)
    if not post:
        raise KeyError(f"post {post_id} not found")
    now = now_iso()
    s = score(now, post)
    post["rank_score"] = s
    post["last_ranked_at"] = now
    mesh.save_post(post)
    return s


def rank_all(mesh) -> List[Tuple[str, float]]:
    out = []
    for pid in mesh.list_posts():
        s = rank_post(mesh, pid)
        out.append((pid, s))
    out.sort(key=lambda t: t[1], reverse=True)
    return out


def update_global_feed(mesh) -> None:
    ranked = rank_all(mesh)
    mesh.update_feed([pid for pid, _ in ranked])

