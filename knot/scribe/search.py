"""Scribe: query interpretation and search."""
from __future__ import annotations

import re
from typing import Dict, List

try:  # optional rapidfuzz
    from rapidfuzz import fuzz
except Exception:  # pragma: no cover - fallback
    fuzz = None
from difflib import get_close_matches


class Scribe:
    def __init__(self, mesh):
        self.mesh = mesh

    # ------------------------------------------------------------------
    def interpret_query(self, query: str) -> Dict[str, List[str]]:
        tokens = re.findall(r"\w+", query.lower())
        categories: List[str] = []
        users: List[str] = []
        terms: List[str] = []
        for tok in tokens:
            cat = self._match_category(tok)
            if cat:
                categories.append(cat)
                continue
            if tok in self.mesh.list_users():
                users.append(tok)
                continue
            terms.append(tok)
        return {
            "categories": list(dict.fromkeys(categories)),
            "users": list(dict.fromkeys(users)),
            "terms": list(dict.fromkeys(terms)),
        }

    def _match_category(self, token: str) -> str | None:
        cats = self.mesh.master_categories
        if token in cats:
            return token
        if fuzz:
            best = max(((c, fuzz.ratio(token, c)) for c in cats), key=lambda x: x[1])
            if best[1] >= 80:
                return best[0]
        else:
            matches = get_close_matches(token, cats, n=1, cutoff=0.8)
            if matches:
                return matches[0]
        return None

    # ------------------------------------------------------------------
    def search_posts(self, interp: Dict[str, List[str]], top_k: int = 20):
        cats = set(interp["categories"])
        users = set(interp["users"])
        terms = set(interp["terms"])
        posts = [self.mesh.get_post(pid) for pid in self.mesh.list_posts()]
        results = []
        for p in posts:
            cat_match = len(cats & set(p.categories))
            user_match = 1 if p.owner_id in users else 0
            term_match = sum(1 for t in terms if t in p.media_path.lower() or any(t in c for c in p.categories))
            total_matches = cat_match + user_match + term_match
            if total_matches == 0:
                continue
            engagement_total = sum(p.engagement.values())
            score = total_matches * (1 + engagement_total)
            results.append((score, p))
        results.sort(key=lambda x: (x[0], x[1].created_at), reverse=True)
        return [p for _, p in results[:top_k]]
