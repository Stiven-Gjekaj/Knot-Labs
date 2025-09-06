from __future__ import annotations

import os
import json
from typing import Dict, List, Optional

from Drift.models import User as DriftUser, VideoCandidate as DriftVideo  # type: ignore
from Drift.drift_ranker import rank_videos as drift_rank_videos  # type: ignore


def mesh_user_to_drift_user(mesh_user: Dict) -> DriftUser:
    preferred = sorted(mesh_user.get("CategoryScores", {}).items(), key=lambda kv: kv[1], reverse=True)
    preferred_categories = [k for k, _ in preferred[:10]]
    seen_creators = list({*mesh_user.get("RecentCreators", []), *list(mesh_user.get("ViewerScore", {}).keys())})
    drift_user_dict = {
        "id": mesh_user.get("userID"),
        "preferred_categories": preferred_categories,
        "seen_creators": seen_creators,
        "recent_creators": mesh_user.get("RecentCreators", []),
        "watched_videos": mesh_user.get("SeenPosts", []),
        "creator_engagement": mesh_user.get("ViewerScore", {}),
    }
    return DriftUser(**drift_user_dict)


def mesh_post_to_drift_video(post: Dict) -> Optional[DriftVideo]:
    if not (post.get("isActive", True) and not post.get("isDeleted", False) and not post.get("isFlagged", False)):
        return None
    cats = post.get("Categories", [])
    cat = cats[0] if cats else "uncategorized"
    drift_video_dict = {
        "id": post.get("postID"),
        "creatorId": post.get("creator"),
        "description": post.get("description"),
        "category": cat,
        "isPayPerView": post.get("isPayPerView", False),
        "ContentType": post.get("PostType", "Video"),
        "isPromotion": post.get("isPromotion", False),
        "isFlagged": post.get("isFlagged", False),
        "ContentStatus": ("Active" if post.get("isActive", True) else "Unavailable"),
        "payPerViewCount": post.get("payPerViewCount", 0),
        "likesCount": post.get("likesCount", 0),
        "commentsCount": post.get("commentsCount", 0),
        "shareCount": post.get("shareCount", 0),
        "giftsCount": post.get("giftsCount", 0),
        "star": post.get("star", 0),
    }
    try:
        return DriftVideo(**drift_video_dict)
    except Exception:
        return None


def load_mesh_posts(posts_dir: str) -> List[Dict]:
    posts: List[Dict] = []
    if not os.path.isdir(posts_dir):
        return posts
    for name in os.listdir(posts_dir):
        if not name.endswith(".json"):
            continue
        p = os.path.join(posts_dir, name)
        try:
            posts.append(json.load(open(p, "r", encoding="utf-8")))
        except Exception:
            pass
    return posts


def mesh_posts_to_drift_candidates(posts_dir: str) -> List[DriftVideo]:
    cands: List[DriftVideo] = []
    for post in load_mesh_posts(posts_dir):
        dv = mesh_post_to_drift_video(post)
        if dv is not None:
            cands.append(dv)
    return cands


def rank_for_mesh_user_identifier(identifier: str, users_dir: str, posts_dir: str):
    # Load mesh user by userID or username
    mesh_user: Optional[Dict] = None
    for name in os.listdir(users_dir) if os.path.isdir(users_dir) else []:
        if not name.endswith(".json"):
            continue
        p = os.path.join(users_dir, name)
        try:
            u = json.load(open(p, "r", encoding="utf-8"))
        except Exception:
            continue
        if u.get("userID") == identifier or u.get("username") == identifier:
            mesh_user = u
            break
    if mesh_user is None:
        return []
    duser = mesh_user_to_drift_user(mesh_user)
    cands = mesh_posts_to_drift_candidates(posts_dir)
    return drift_rank_videos(duser, cands)

