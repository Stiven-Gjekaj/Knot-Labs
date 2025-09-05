"""Data models for Mesh."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class User:
    user_id: str
    handle: str
    created_at: str
    gender: Optional[str] = None
    posts: List[str] = field(default_factory=list)
    creator_score: int = 0
    viewer_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    seen_posts: List[str] = field(default_factory=list)
    top_categories: List[str] = field(default_factory=list)
    category_stats: Dict[str, int] = field(default_factory=dict)


@dataclass
class Post:
    post_id: str
    owner_id: str
    media_path: str
    media_type: str
    created_at: str
    categories: List[str]
    engagement: Dict[str, int]
    rank_score: float
    last_ranked_at: str
