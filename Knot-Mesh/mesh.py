"""Mesh module: persistent JSON datastore with CRUD operations."""
import json
import os
import uuid
import time
from typing import Dict, List, Tuple, Optional

from veil import Veil


class Mesh:
    """Simple JSON-backed storage for users and posts."""

    def __init__(self, path: str = "mesh_data.json") -> None:
        self.path = path
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"users": {}, "posts": {}}, f)

    # internal helpers
    def _load(self) -> Dict[str, Dict]:
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: Dict[str, Dict]) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # user operations
    def add_user(self, name: str, uid: Optional[str] = None) -> str:
        """Add a user and return its ID.

        A custom ``uid`` can be supplied which is helpful for demos where the
        caller wants control over the identifier (e.g., to map to a per-user
        data file). If not provided, a random UUID is generated.
        """

        data = self._load()
        uid = uid or str(uuid.uuid4())
        data["users"][uid] = {"name": name}
        self._save(data)
        return uid

    # post operations
    def create_post(
        self, content_path: str, tags: Optional[List[str]] = None, veil: Optional[Veil] = None
    ) -> str:
        data = self._load()
        pid = str(uuid.uuid4())
        if tags is None:
            if veil is None:
                raise ValueError("Either tags or a Veil instance must be provided")
            tags = veil.classify(content_path)
        if len(tags) < 3:
            raise ValueError("Post requires three categories")
        data["posts"][pid] = {
            "path": content_path,
            "tags": tags[:3],
            "likes": 0,
            "comments": 0,
            "gifts": 0,
            "shares": 0,
            "created_at": time.time(),
        }
        self._save(data)
        return pid

    def get_post(self, pid: str) -> Optional[Dict]:
        return self._load()["posts"].get(pid)

    def update_post(self, pid: str, **updates) -> bool:
        data = self._load()
        if pid in data["posts"]:
            data["posts"][pid].update(updates)
            self._save(data)
            return True
        return False

    def delete_post(self, pid: str) -> bool:
        data = self._load()
        if pid in data["posts"]:
            del data["posts"][pid]
            self._save(data)
            return True
        return False

    def all_posts(self) -> Dict[str, Dict]:
        return self._load()["posts"]

    def increment(self, pid: str, field: str) -> None:
        data = self._load()
        if pid in data["posts"]:
            data["posts"][pid][field] += 1
            self._save(data)

    # searching
    def search(self, text: Optional[str] = None, tag: Optional[str] = None) -> List[Tuple[str, Dict]]:
        posts = self.all_posts()
        results: List[Tuple[str, Dict]] = []
        for pid, post in posts.items():
            if text and text.lower() in post["path"].lower():
                results.append((pid, post))
            elif tag and tag in post["tags"]:
                results.append((pid, post))
        return results
