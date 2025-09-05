"""Drift module: ranking algorithms for posts."""
from typing import Dict, List, Tuple
import time
import math


class Drift:
    """Ranks posts given engagement statistics."""

    def _age_factor(self, created_at: float) -> float:
        """Return a decay factor based on post age.

        Uses a logarithmic decay so that items reach zero score after
        three months (≈90 days). New posts have a factor near 1.
        """

        max_age_days = 90
        age_days = (time.time() - created_at) / 86400
        if age_days >= max_age_days:
            return 0.0
        return max(
            0.0,
            1 - math.log(age_days + 1) / math.log(max_age_days + 1),
        )

    def rank(
        self, posts: Dict[str, Dict], algorithm: str = "simple"
    ) -> List[Tuple[str, Dict, float]]:
        ranked: List[Tuple[str, Dict, float]] = []
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
            factor = self._age_factor(post.get("created_at", time.time()))
            score *= factor
            if score <= 0:
                continue
            ranked.append((pid, post, score))
        ranked.sort(key=lambda x: x[2], reverse=True)
        return ranked
