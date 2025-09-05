"""Mesh database API."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .storage import read_json, write_json, ensure_dir
from .models import user_default, post_default

# Weights for creator score mirroring Drift weights
CREATOR_WEIGHTS = {"view": 1, "like": 5, "comment": 8, "share": 12, "gift": 20}
PLURAL = {"view": "views", "like": "likes", "comment": "comments", "share": "shares", "gift": "gifts"}


class MeshDB:
    """JSON-backed storage."""

    def __init__(self, base: Path | str = Path("data")) -> None:
        self.base = Path(base)
        self.users_dir = self.base / "users"
        self.posts_dir = self.base / "posts"
        self.index_dir = self.base / "index"
        self.feeds_dir = self.base / "feeds"
        ensure_dir(self.users_dir)
        ensure_dir(self.posts_dir)
        ensure_dir(self.index_dir)
        ensure_dir(self.feeds_dir)
        self.session_path = self.base / ".session.json"
        self.migrate_legacy_if_any()

    # ---- master categories ----
    def _master_path(self) -> Path:
        return self.base / "mastercategories.txt"

    def get_master_categories(self) -> List[str]:
        path = self._master_path()
        if not path.exists():
            # try to import legacy
            legacy_paths = [
                Path("legacy/mastercategories.txt"),
                Path("veil/mastercategories.txt"),
                Path("Knot-Scribe/data/mastercategories.txt"),
                Path("Knot-Veil/examples/mastercategories.txt"),
            ]
            for lp in legacy_paths:
                if lp.exists():
                    ensure_dir(path.parent)
                    path.write_text(lp.read_text(), encoding="utf-8")
                    break
            else:
                # create default list
                default_cats = list(dict.fromkeys(DEFAULT_CATEGORIES))
                ensure_dir(path.parent)
                path.write_text("\n".join(default_cats), encoding="utf-8")
        cats = [c.strip() for c in path.read_text(encoding="utf-8").splitlines() if c.strip()]
        unique = list(dict.fromkeys(cats))
        if unique != cats:
            path.write_text("\n".join(unique), encoding="utf-8")
        return unique

    # ---- legacy migration ----
    def migrate_legacy_if_any(self) -> None:
        self.get_master_categories()  # ensure categories exist
        # migrate users from legacy drift if present
        legacy_files = [Path("legacy/drift_users.json"), Path("drift/user_info.json")]
        for lf in legacy_files:
            if lf.exists():
                data = read_json(lf, default={}) or {}
                for user_id, info in data.items():
                    if not (self.users_dir / f"{user_id}.json").exists():
                        user = user_default(user_id)
                        if isinstance(info, dict):
                            user.update({k: info.get(k, v) for k, v in user.items() if k in info})
                        self.save_user(user)

    # ---- user ops ----
    def _user_path(self, user_id: str) -> Path:
        return self.users_dir / f"{user_id}.json"

    def create_user(self, user_id: str) -> Dict:
        user = user_default(user_id)
        self.save_user(user)
        users = read_json(self.index_dir / "users.json", default=[])
        if user_id not in users:
            users.append(user_id)
            write_json(self.index_dir / "users.json", users)
        return user

    def get_user(self, user_id: str) -> Dict | None:
        return read_json(self._user_path(user_id))

    def save_user(self, user_obj: Dict) -> None:
        write_json(self._user_path(user_obj["user_id"]), user_obj)

    def list_users(self) -> List[str]:
        return read_json(self.index_dir / "users.json", default=[])

    # ---- post ops ----
    def _post_path(self, post_id: str) -> Path:
        return self.posts_dir / f"{post_id}.json"

    def create_post(self, post_id: str, owner_id: str, media_path: str) -> Dict:
        post = post_default(post_id, owner_id, media_path)
        self.save_post(post)
        posts = read_json(self.index_dir / "posts.json", default=[])
        if post_id not in posts:
            posts.append(post_id)
            write_json(self.index_dir / "posts.json", posts)
        # register post to user
        user = self.get_user(owner_id) or self.create_user(owner_id)
        if post_id not in user["posts"]:
            user["posts"].append(post_id)
            self.save_user(user)
        return post

    def get_post(self, post_id: str) -> Dict | None:
        return read_json(self._post_path(post_id))

    def save_post(self, post_obj: Dict) -> None:
        write_json(self._post_path(post_obj["post_id"]), post_obj)

    def list_posts(self) -> List[str]:
        return read_json(self.index_dir / "posts.json", default=[])

    def set_post_categories(self, post_id: str, cats: List[str]) -> None:
        post = self.get_post(post_id)
        if not post:
            raise KeyError(f"post {post_id} not found")
        post["categories"] = cats[:3]
        self.save_post(post)

    def increment_engagement(self, post_id: str, actor_user_id: str, kind: str) -> Dict:
        if kind not in PLURAL:
            raise ValueError("invalid engagement kind")
        post = self.get_post(post_id)
        if not post:
            raise KeyError(f"post {post_id} not found")
        plural = PLURAL[kind]
        post["engagement"][plural] += 1
        self.save_post(post)
        owner = self.get_user(post["owner_id"]) or self.create_user(post["owner_id"])
        if kind != "view":
            owner["creator_score"] += CREATOR_WEIGHTS[kind]
            self.save_user(owner)
        # update viewer stats
        viewer = self.get_user(actor_user_id) or self.create_user(actor_user_id)
        stats = viewer.setdefault("viewer_stats", {}).setdefault(
            owner["user_id"], {p: 0 for p in PLURAL.values()}
        )
        stats[plural] += 1
        seen = viewer.setdefault("seen_posts", [])
        if post_id not in seen:
            seen.append(post_id)
        self.save_user(viewer)
        return post

    # ---- feed ----
    def update_feed(self, sorted_post_ids: List[str]) -> None:
        write_json(self.feeds_dir / "global.json", sorted_post_ids)

    def get_feed(self, topK: int = 10) -> List[Dict]:
        ids = read_json(self.feeds_dir / "global.json", default=[])[:topK]
        out = []
        for pid in ids:
            p = self.get_post(pid)
            if p:
                out.append({
                    "post_id": p["post_id"],
                    "owner_id": p["owner_id"],
                    "rank_score": p["rank_score"],
                    "categories": p["categories"],
                })
        return out

    # ---- session ----
    def set_active_user(self, user_id: str) -> None:
        write_json(self.session_path, {"active_user_id": user_id})

    def get_active_user(self) -> str | None:
        data = read_json(self.session_path, default={})
        return data.get("active_user_id") if data else None


# Default categories (excerpt for commit) ~100 categories
DEFAULT_CATEGORIES = [
    "art", "animals", "architecture", "astronomy", "automotive", "baking", "basketball",
    "beauty", "biology", "business", "cars", "cats", "chemistry", "comedy", "cooking",
    "crafts", "dance", "design", "diy", "education", "fashion", "fitness", "food",
    "football", "gaming", "gardening", "geography", "history", "hiking", "home", "humor",
    "kids", "language", "law", "literature", "makeup", "marketing", "math", "meditation",
    "movies", "music", "news", "outdoors", "painting", "pets", "photography", "physics",
    "politics", "programming", "science", "shopping", "soccer", "space", "sports",
    "technology", "travel", "video", "writing", "yoga", "finance", "economics", "culture",
    "environment", "nature", "wildlife", "health", "recipes", "relationships", "religion",
    "science fiction", "tabletop games", "tennis", "theater", "urban", "virtual reality",
    "weather", "weddings", "wine", "workout", "world news", "photography", "anime",
    "manga", "board games", "entrepreneurship", "investing", "startups", "machine learning",
    "artificial intelligence", "robotics", "craft beer", "podcasts", "horror", "mystery",
    "drama", "adventure", "surfing", "skateboarding", "skiing", "snowboarding"
]

