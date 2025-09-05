"""Data model helpers for Mesh."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from ..common.time import now_iso


# --- User ---

def user_default(user_id: str) -> Dict:
    """Return default user object."""
    return {
        "user_id": user_id,
        "handle": user_id,
        "created_at": now_iso(),
        "gender": None,
        "posts": [],
        "creator_score": 0,
        "viewer_stats": {},
        "seen_posts": [],
        "top_categories": [],
    }


# --- Post ---

def infer_media_type(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        return "image"
    if ext in {".mp4", ".mov", ".avi", ".mkv"}:
        return "video"
    return "unknown"


def post_default(post_id: str, owner_id: str, media_path: str) -> Dict:
    return {
        "post_id": post_id,
        "owner_id": owner_id,
        "media_path": media_path,
        "media_type": infer_media_type(media_path),
        "created_at": now_iso(),
        "categories": [],
        "engagement": {"views": 0, "likes": 0, "comments": 0, "shares": 0, "gifts": 0},
        "rank_score": 0.0,
        "last_ranked_at": now_iso(),
    }

