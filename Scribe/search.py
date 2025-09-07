from __future__ import annotations

import os
import json
import math
import re
from typing import Dict, List, Tuple, Optional
from Mesh.category import ensure_category, category_texts


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class BowEmbedder:
    def __init__(self) -> None:
        self.vocab: Dict[str, int] = {}
        self.idf: List[float] = []

    def fit_transform(self, texts: List[str]):
        # Build vocab and document frequencies
        dfs: Dict[str, int] = {}
        for t in texts:
            seen = set()
            for tok in _tokenize(t):
                if tok not in self.vocab:
                    self.vocab[tok] = len(self.vocab)
                if tok not in seen:
                    dfs[tok] = dfs.get(tok, 0) + 1
                    seen.add(tok)
        n = max(1, len(texts))
        # idf = log(N/df) + 1
        self.idf = [1.0] * len(self.vocab)
        for tok, idx in self.vocab.items():
            df = max(1, dfs.get(tok, 1))
            self.idf[idx] = math.log(n / df) + 1.0
        return [self.transform_one(t) for t in texts]

    def transform_one(self, text: str):
        vec = [0.0] * len(self.vocab)
        toks = _tokenize(text)
        for tok in toks:
            idx = self.vocab.get(tok)
            if idx is not None:
                vec[idx] += self.idf[idx]
        # Normalize to unit length
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer  # type: ignore

        self.model = SentenceTransformer(model_name)

    def fit_transform(self, texts: List[str]):
        return self.model.encode(texts, normalize_embeddings=True).tolist()

    def transform_one(self, text: str):
        return self.model.encode([text], normalize_embeddings=True)[0].tolist()


def load_posts(posts_dir: str) -> List[Dict]:
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


class Index:
    def __init__(self, embedder, ids: List[str], texts: List[str], vecs: List[List[float]]):
        self.embedder = embedder
        self.ids = ids
        self.texts = texts
        self.vecs = vecs

    def search(self, query: str, k: int = 10) -> List[Tuple[str, float]]:
        qv = self.embedder.transform_one(query)
        scores: List[Tuple[str, float]] = []
        for pid, pv in zip(self.ids, self.vecs):
            # Cosine similarity because vectors are normalized
            score = sum(a * b for a, b in zip(qv, pv))
            scores.append((pid, float(score)))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:k]


def build_index(
    posts_dir: str,
    *,
    backend: str = "bow",
    model_name: Optional[str] = None,
    fields: Tuple[str, ...] = ("description",),
) -> Index:
    posts = load_posts(posts_dir)
    ids: List[str] = []
    texts: List[str] = []
    for p in posts:
        pid = p.get("postID")
        if not pid:
            continue
        chunks: List[str] = []
        for f in fields:
            v = p.get(f)
            if isinstance(v, str):
                chunks.append(v)
            elif isinstance(v, list):
                chunks.extend([str(it) for it in v])
        # Add category tokens (macro, meso, micro)
        cat = ensure_category(p)
        chunks.extend(category_texts(cat))
        if not chunks:
            continue
        ids.append(pid)
        texts.append(" \n ".join(chunks))

    if backend == "bow":
        emb = BowEmbedder()
    else:
        try:
            emb = SentenceTransformerEmbedder(model_name or "sentence-transformers/all-MiniLM-L6-v2")
        except Exception:
            # Fallback to bow if ST model fails
            emb = BowEmbedder()

    vecs = emb.fit_transform(texts)
    return Index(emb, ids, texts, vecs)


def search_posts(query: str, posts_dir: str, *, k: int = 10, backend: str = "bow") -> List[Tuple[str, float]]:
    idx = build_index(posts_dir, backend=backend)
    return idx.search(query, k=k)
