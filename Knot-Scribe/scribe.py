"""Scribe module: text and tag search interface."""
from __future__ import annotations
from typing import List, Tuple, Dict

from mesh import Mesh

try:  # pragma: no cover - optional dependency
    from sentence_transformers import SentenceTransformer, util
except Exception:  # pragma: no cover - dependency missing
    SentenceTransformer = None  # type: ignore
    util = None  # type: ignore


class Scribe:
    """Searches posts stored in Mesh."""

    def __init__(self, mesh: Mesh) -> None:
        self.mesh = mesh
        self._model = None
        if SentenceTransformer is not None:
            try:  # pragma: no cover - heavy model load
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception:
                self._model = None

    def search(self, query: str) -> List[Tuple[str, Dict]]:
        """Search by text or tag (#tag)."""
        query = query.strip().lower()
        if query.startswith("#"):
            return self.mesh.search(tag=query[1:])

        posts = self.mesh.all_posts()
        if not posts:
            return []

        if self._model is None:
            return self.mesh.search(text=query)

        corpus: List[str] = []
        ids: List[str] = []
        for pid, post in posts.items():
            text = f"{post.get('path', '')} {' '.join(post.get('tags', []))}".lower()
            corpus.append(text)
            ids.append(pid)

        q_emb = self._model.encode(query, convert_to_tensor=True)
        p_emb = self._model.encode(corpus, convert_to_tensor=True)
        scores = util.cos_sim(q_emb, p_emb)[0].cpu().tolist()
        ranked = []
        for pid, post, score in zip(ids, posts.values(), scores):
            if query in post.get('path', '').lower() or any(
                query in t.lower() for t in post.get('tags', [])
            ):
                score += 1.0  # boost exact matches
            ranked.append((pid, post, score))
        ranked.sort(key=lambda x: x[2], reverse=True)
        return [(pid, post) for pid, post, _ in ranked]
