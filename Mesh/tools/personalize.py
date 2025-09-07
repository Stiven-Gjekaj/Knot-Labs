#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from typing import Dict, List

from Mesh.category import ensure_category


def _iter_json(dir_path: str) -> List[Dict]:
    out: List[Dict] = []
    if not os.path.isdir(dir_path):
        return out
    for name in os.listdir(dir_path):
        if name.endswith('.json'):
            p = os.path.join(dir_path, name)
            try:
                out.append(json.load(open(p, 'r', encoding='utf-8')))
            except Exception:
                pass
    return out


def compute_user_category_scores(users_dir: str, posts_dir: str) -> int:
    """Offline job: recompute CategoryScores per user from SeenPosts and recent interactions.

    Very simple heuristic: for each SeenPost, add +1 to all micro labels on that post. Normalize to [0,1].
    """
    posts_by_id: Dict[str, Dict] = {}
    for p in _iter_json(posts_dir):
        posts_by_id[p.get('postID')] = p

    updated = 0
    for u in _iter_json(users_dir):
        scores: Dict[str, float] = defaultdict(float)
        seen = u.get('SeenPosts') or []
        for pid in seen:
            p = posts_by_id.get(pid)
            if not p:
                continue
            cat = ensure_category(p)
            micro = cat.get('micro') or []
            for m in micro:
                if not isinstance(m, str):
                    continue
                scores[m] += 1.0
        if scores:
            # normalize
            vals = list(scores.values())
            mn, mx = min(vals), max(vals)
            if mx - mn < 1e-8:
                norm = {k: 0.0 for k in scores.keys()}
            else:
                norm = {k: (v - mn) / (mx - mn) for k, v in scores.items()}
            u['CategoryScores'] = norm
            # write back
            path = os.path.join(users_dir, f"{u.get('userID')}.json")
            try:
                json.dump(u, open(path, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
                updated += 1
            except Exception:
                pass
    return updated


def main() -> None:
    p = argparse.ArgumentParser(description='Recompute user category scores offline.')
    p.add_argument('--users', default=os.path.join('Mesh','Users'))
    p.add_argument('--posts', default=os.path.join('Mesh','Posts'))
    args = p.parse_args()
    n = compute_user_category_scores(args.users, args.posts)
    print(f"Updated {n} users")


if __name__ == '__main__':
    main()

