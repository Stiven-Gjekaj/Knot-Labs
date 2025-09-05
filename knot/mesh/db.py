"""Mesh database for storing users and posts in JSON."""
from __future__ import annotations

import random
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional

from knot.common.time import now_iso, parse_iso
from knot.common.id_gen import new_id
from . import storage
from .models import Post, User
from knot.drift.ranker import rank_post


ENG_TYPES = ["views", "likes", "comments", "shares", "gifts"]


class MeshDB:
    """Simple JSON storage backend."""

    def __init__(self, root: Path):
        self.root = root
        self.users_dir = root / "users"
        self.posts_dir = root / "posts"
        self.feeds_dir = root / "feeds"
        self.index_dir = root / "index"
        self.session_file = root / ".session.json"
        self.master_file = root / "mastercategories.txt"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.users_dir.mkdir(parents=True, exist_ok=True)
        self.posts_dir.mkdir(parents=True, exist_ok=True)
        self.feeds_dir.mkdir(parents=True, exist_ok=True)
        self.root.mkdir(parents=True, exist_ok=True)
        self._load_master_categories()

    # ------------------------------------------------------------------
    def _load_master_categories(self) -> None:
        text = storage.read_text(self.master_file, "")
        if not text.strip():
            # generate default 210 categories
            cats = [f"cat{i}" for i in range(210)]
            storage.write_text_atomic(self.master_file, "\n".join(cats))
            text = "\n".join(cats)
        cats = [c.strip().lower() for c in text.splitlines() if c.strip()]
        # dedupe
        seen = []
        for c in cats:
            if c not in seen:
                seen.append(c)
        self.master_categories = seen
        storage.write_text_atomic(self.master_file, "\n".join(seen))

    # ------------------------------------------------------------------
    def _index_path(self, name: str) -> Path:
        return self.index_dir / f"{name}.json"

    def _load_index(self, name: str) -> List[str]:
        return storage.read_json(self._index_path(name), [])

    def _save_index(self, name: str, items: List[str]) -> None:
        storage.write_json_atomic(self._index_path(name), items)

    # ------------------------------------------------------------------
    # Session management
    def get_active_user_id(self) -> Optional[str]:
        data = storage.read_json(self.session_file, {"active_user_id": None})
        return data.get("active_user_id")

    def set_active_user(self, user_id: Optional[str]) -> None:
        storage.write_json_atomic(self.session_file, {"active_user_id": user_id})

    # ------------------------------------------------------------------
    # User operations
    def create_user(self, user_id: str, handle: Optional[str] = None) -> User:
        path = self.users_dir / f"{user_id}.json"
        if path.exists():
            return self.get_user(user_id)
        handle = handle or user_id
        user = User(user_id=user_id, handle=handle, created_at=now_iso())
        storage.write_json_atomic(path, asdict(user))
        index = self._load_index("users")
        if user_id not in index:
            index.append(user_id)
            self._save_index("users", index)
        return user

    def get_user(self, user_id: str) -> User:
        path = self.users_dir / f"{user_id}.json"
        data = storage.read_json(path, None)
        if not data:
            raise KeyError(f"user {user_id} not found")
        return User(**data)

    def save_user(self, user: User) -> None:
        path = self.users_dir / f"{user.user_id}.json"
        storage.write_json_atomic(path, asdict(user))

    def list_users(self) -> List[str]:
        return self._load_index("users")

    # ------------------------------------------------------------------
    # Post operations
    def create_post(self, post_id: str, owner_id: str, media_path: str, categories: List[str]) -> Post:
        if len(categories) != 3:
            raise ValueError("exactly 3 categories required")
        path = self.posts_dir / f"{post_id}.json"
        post = Post(
            post_id=post_id,
            owner_id=owner_id,
            media_path=media_path,
            media_type="image" if media_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')) else "unknown",
            created_at=now_iso(),
            categories=categories,
            engagement={k: 0 for k in ENG_TYPES},
            rank_score=0.0,
            last_ranked_at=now_iso(),
        )
        storage.write_json_atomic(path, asdict(post))
        # update index
        idx = self._load_index("posts")
        if post_id not in idx:
            idx.append(post_id)
            self._save_index("posts", idx)
        # update user
        user = self.get_user(owner_id)
        user.posts.append(post_id)
        for c in categories:
            user.category_stats[c] = user.category_stats.get(c, 0) + 1
        user.top_categories = sorted(user.category_stats, key=user.category_stats.get, reverse=True)[:5]
        self.save_user(user)
        # rank and feed
        rank_post(post)
        storage.write_json_atomic(path, asdict(post))
        self.update_feed()
        return post

    def get_post(self, post_id: str) -> Post:
        path = self.posts_dir / f"{post_id}.json"
        data = storage.read_json(path, None)
        if not data:
            raise KeyError(f"post {post_id} not found")
        return Post(**data)

    def save_post(self, post: Post) -> None:
        path = self.posts_dir / f"{post.post_id}.json"
        storage.write_json_atomic(path, asdict(post))

    def list_posts(self) -> List[str]:
        return self._load_index("posts")

    # ------------------------------------------------------------------
    def record_engagement(self, post_id: str, kind: str, viewer_id: Optional[str] = None) -> Post:
        if kind not in ENG_TYPES:
            raise ValueError("invalid engagement type")
        post = self.get_post(post_id)
        post.engagement[kind] += 1
        # update viewer stats
        if viewer_id:
            viewer = self.get_user(viewer_id)
            stats = viewer.viewer_stats.setdefault(post.owner_id, {k: 0 for k in ENG_TYPES})
            stats[kind] += 1
            if post_id not in viewer.seen_posts:
                viewer.seen_posts.append(post_id)
            self.save_user(viewer)
        # creator score
        owner = self.get_user(post.owner_id)
        owner.creator_score += 1
        self.save_user(owner)
        # rerank
        rank_post(post)
        self.save_post(post)
        self.update_feed()
        return post

    # ------------------------------------------------------------------
    def update_feed(self) -> None:
        posts = [self.get_post(pid) for pid in self.list_posts()]
        posts.sort(key=lambda p: p.rank_score, reverse=True)
        feed_path = self.feeds_dir / "global.json"
        storage.write_json_atomic(feed_path, [p.post_id for p in posts])

    def get_feed(self, top_k: int = 20) -> List[Post]:
        feed_path = self.feeds_dir / "global.json"
        ids = storage.read_json(feed_path, [])[:top_k]
        return [self.get_post(pid) for pid in ids]

    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Remove all stored data."""
        for path in [self.users_dir, self.posts_dir, self.feeds_dir, self.index_dir]:
            if path.exists():
                for item in path.glob("*"):
                    if item.is_file():
                        item.unlink()
        self._save_index("users", [])
        self._save_index("posts", [])
        storage.write_json_atomic(self.session_file, {"active_user_id": None})
        self.update_feed()

    # ------------------------------------------------------------------
    def gen_samples(self, n: int) -> None:
        random.seed(0)
        for i in range(n):
            uid = f"sample{i}"
            self.create_user(uid, uid)
            categories = random.sample(self.master_categories, 3)
            if i == 0 and "basketball" in self.master_categories:
                categories[0] = "basketball"
            pid = f"post{uid}"
            self.create_post(pid, uid, f"/tmp/{pid}.png", categories)

