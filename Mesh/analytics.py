from __future__ import annotations

import os
import json
from collections import defaultdict
from typing import Dict
from .category import ensure_category


def category_stats(posts_dir: str) -> Dict[str, Dict[str, float]]:
    """Compute simple category aggregates across posts.

    Returns a mapping: macro-category -> { count, likes, comments, shares, gifts, score }
    """
    stats: Dict[str, Dict[str, float]] = {}
    def ensure(cat: str):
        if cat not in stats:
            stats[cat] = {"count": 0, "likes": 0, "comments": 0, "shares": 0, "gifts": 0, "score": 0.0}
        return stats[cat]

    if not os.path.isdir(posts_dir):
        return stats
    for name in os.listdir(posts_dir):
        if not name.endswith('.json'):
            continue
        p = os.path.join(posts_dir, name)
        try:
            post = json.load(open(p, 'r', encoding='utf-8'))
        except Exception:
            continue
        cat = ensure_category(post)
        macros = cat.get('macro')
        macro_list = macros if isinstance(macros, list) else [macros] if isinstance(macros, str) else []
        if not macro_list:
            macro_list = ['uncategorized']
        # Count towards each macro present (unique per post)
        for c in set(macro_list):
            s = ensure(c)
            s['count'] += 1
            s['likes'] += float(post.get('likesCount', 0))
            s['comments'] += float(post.get('commentsCount', 0))
            s['shares'] += float(post.get('shareCount', 0))
            s['gifts'] += float(post.get('giftsCount', 0))
            s['score'] += float(post.get('Score', 0.0))
    return stats
