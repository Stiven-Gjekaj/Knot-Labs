"""Search interpreter and query execution."""
from __future__ import annotations

import re
from typing import Dict, List

from rapidfuzz import fuzz


def interpret_query(q: str, master_categories: List[str]) -> Dict:
    """Return interpreted query tokens."""
    q = q.lower()
    tokens = re.split(r"\W+", q)
    categories: List[str] = []
    users: List[str] = []
    terms: List[str] = []
    for t in tokens:
        if not t:
            continue
        if t.startswith("user_"):
            users.append(t)
            continue
        # fuzzy match categories
        best = max(((fuzz.ratio(t, c), c) for c in master_categories), default=(0, None))
        if best[0] >= 80 and best[1]:
            categories.append(best[1])
        else:
            terms.append(t)
    return {"categories": categories, "users": users, "terms": terms}


def search_posts(mesh, interp: Dict, topK: int = 20) -> List[Dict]:
    """Return list of post objects matching interpreted query."""
    ids = mesh.list_posts()
    results: List[Dict] = []
    cats = set(interp.get("categories", []))
    users = set(interp.get("users", []))
    terms = interp.get("terms", [])
    for pid in ids:
        post = mesh.get_post(pid)
        if not post:
            continue
        if cats and not cats.intersection(post.get("categories", [])):
            continue
        if users and post.get("owner_id") not in users:
            continue
        if terms:
            haystack = " ".join([post.get("media_path", ""), " ".join(post.get("categories", []))]).lower()
            if not any(term in haystack for term in terms):
                continue
        results.append(post)
    results.sort(key=lambda p: p.get("rank_score", 0), reverse=True)
    return results[:topK]

