"""Drift module: ranking algorithms for posts."""
from typing import Dict, List, Tuple


class Drift:
    """Ranks posts given engagement statistics."""

    def rank(self, posts: Dict[str, Dict], algorithm: str = "simple") -> List[Tuple[str, Dict, int]]:
        ranked: List[Tuple[str, Dict, int]] = []
        for pid, post in posts.items():
            if algorithm == "feedback":
                score = (
                    post["likes"]
                    + post["comments"] * 2
                    + post["shares"] * 3
                    + post["gifts"] * 4
                )
            else:  # simple
                score = (
                    post["likes"]
                    + post["comments"] * 2
                    + post["shares"] * 2
                    + post["gifts"] * 3
                )
            ranked.append((pid, post, score))
        ranked.sort(key=lambda x: x[2], reverse=True)
        return ranked
