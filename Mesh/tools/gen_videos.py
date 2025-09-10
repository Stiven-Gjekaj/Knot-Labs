#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import time
import uuid
from typing import Dict, List

from Mesh.category import make_category_from_micro


COUNTRIES = [
    "US", "CA", "GB", "DE", "FR", "BR", "IN", "JP", "KR", "AU",
    "MX", "ID", "NG", "ZA", "EG", "IT", "ES", "NL", "SE", "NO",
]


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def load_users(users_dir: str) -> List[Dict]:
    if not os.path.isdir(users_dir):
        return []
    users: List[Dict] = []
    for name in os.listdir(users_dir):
        if not name.endswith(".json"):
            continue
        p = os.path.join(users_dir, name)
        try:
            with open(p, "r", encoding="utf-8") as f:
                users.append(json.load(f))
        except Exception:
            continue
    return users


def load_master_categories(path: str) -> List[str]:
    cats: List[str] = []
    if not os.path.isfile(path):
        return cats
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw or raw.startswith("#"):
                continue
            if "|" not in raw:
                continue
            left = raw.split("|", 1)[0].strip()
            if not left.startswith("a video about "):
                continue
            cat = left[len("a video about "):].strip()
            if cat:
                cats.append(cat)
    return cats


def make_post(creator_id: str, categories: List[str], country: str | None = None) -> Dict:
    post_id = uuid.uuid4().hex
    # pick up to 14 unique categories (2 macro + 4 meso + 8 micro)
    if categories:
        picks = random.sample(categories, k=min(14, len(categories)))
    else:
        picks = []
    if country is None or country not in COUNTRIES:
        country = random.choice(COUNTRIES)
    category_obj = make_category_from_micro(picks)
    return {
        "postID": post_id,
        "creator": creator_id,
        "description": "Description Here",
        "Score": 0.0,
        "Category": category_obj,
        "country": country,
        "created_at": time.time(),
        "isPayPerView": False,
        "PostType": "Video",
        "isPromotion": False,
        "isFlagged": False,
        "isActive": True,
        "isDeleted": False,
        "payPerViewCount": 0,
        "likesCount": 0,
        "commentsCount": 0,
        "giftsCount": 0,
        "isSuggested": False,
        "shareCount": 0,
        "star": 0,
    }


def save_post(post: Dict, posts_dir: str) -> str:
    ensure_dir(posts_dir)
    path = os.path.join(posts_dir, f"{post['postID']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(post, f, indent=2, ensure_ascii=False)
    return path

# Backwards-compatible aliases
def make_video(creator_id: str, categories: List[str]) -> Dict:  # type: ignore[override]
    return make_post(creator_id, categories)

def save_video(post: Dict, videos_dir: str) -> str:  # type: ignore[override]
    return save_post(post, videos_dir)


def main() -> None:
    p = argparse.ArgumentParser(description="Generate N posts under Mesh/Posts/")
    p.add_argument("N", type=int, help="number of videos to create")
    p.add_argument("--users-dir", default=os.path.join("Mesh", "Users"))
    # Backward-compatible flag name, default points to Posts
    p.add_argument("--videos-dir", default=os.path.join("Mesh", "Posts"))
    # Preferred new flag name (alias)
    p.add_argument("--posts-dir", default=None)
    p.add_argument("--master", default=os.path.join("Mesh", "mastercategories.txt"))
    p.add_argument("--creator", help="optional creator userID; if omitted, pick a random user from Users/")
    p.add_argument("--country", choices=COUNTRIES, help="optional country to assign (applies to all created)")
    args = p.parse_args()

    users = load_users(args.users_dir)
    if not users and not args.creator:
        raise SystemExit("No users found in Users/ and no --creator provided")
    cats = load_master_categories(args.master)
    posts_dir = args.posts_dir or args.videos_dir
    created = []
    for _ in range(args.N):
        creator_id = args.creator or random.choice(users)["userID"]
        post = make_post(creator_id, cats, country=args.country)
        path = save_post(post, posts_dir)
        created.append((post["postID"], path))
    for vid, path in created:
        print(f"Created post {vid} at {path}")


if __name__ == "__main__":
    main()
