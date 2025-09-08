#!/usr/bin/env python3
from __future__ import annotations

"""
Build a hierarchical mastercategories file from a fixed macro list, pulling
meso/micro candidates from the web when available with offline fallbacks.

Output:
- Mesh/mastercategories.txt (micro prompts: "a video about X | a photo of X")
- Mesh/master_tree.json (hierarchy: {macro:[{meso:[micro,...]}, ...]})

Requirements: none (uses stdlib); optional network via urllib.
"""

import argparse
import json
import os
import re
import time
from typing import Dict, List, Tuple, Iterable

MACROS: List[str] = [
    "Gaming","Music","Sports","Movies & TV","Anime & Comics","Technology & Gadgets",
    "Science & Education","Art & Design","Fashion & Beauty","Food & Cooking","Travel & Places",
    "Cars & Vehicles","Health & Fitness","Lifestyle & Routines","History & Culture",
    "Politics & News","Finance & Business","Nature & Animals","DIY & How-To","Comedy & Memes",
    "Motivation & Self-Help","Mystery & Horror","Podcasts & Talk","Relationships & Community",
    "Spirituality & Philosophy",
]


def norm_label(s: str) -> str:
    t = s.lower()
    t = t.replace('&', ' and ')
    t = re.sub(r"\(.*?\)", " ", t)  # drop parentheses
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    # collapse bland adjectives
    t = re.sub(r"\b(best|top|new|latest|cool|awesome|funny|random)\b", "", t).strip()
    return t


def dedup_keep_order(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for it in items:
        k = norm_label(it)
        if not k or k in seen:
            continue
        out.append(k)
        seen.add(k)
    return out


def fetch_wikipedia_subcats(topic: str, max_items: int = 10) -> List[str]:
    # Best-effort extraction; ignores failures gracefully
    try:
        import urllib.parse as up
        import urllib.request as ur
        title = f"Category:{topic.replace(' ', '_')}"
        url = (
            "https://en.wikipedia.org/w/api.php?action=query&list=categorymembers&cmtitle="
            + up.quote(title)
            + "&cmtype=subcat&cmlimit=50&format=json"
        )
        with ur.urlopen(url, timeout=6) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        items = [m.get('title','') for m in (data.get('query',{}).get('categorymembers') or [])]
        cleaned = []
        for it in items:
            it = re.sub(r"^Category:\s*", "", it)
            cleaned.append(it)
        return dedup_keep_order(cleaned)[:max_items]
    except Exception:
        return []


FALLBACK_MESO: Dict[str, List[str]] = {
    "Gaming": ["PC gaming", "Console gaming", "Mobile gaming"],
    "Music": ["Pop music", "Hip hop", "Classical music"],
    "Sports": ["Ball sports", "Combat sports"],
    "Movies & TV": ["Movie reviews", "TV series"],
    "Anime & Comics": ["Shonen", "Seinen"],
    "Technology & Gadgets": ["Smartphones", "PC hardware"],
}

FALLBACK_MICRO: Dict[str, List[str]] = {
    "PC gaming": ["strategy games", "simulation games", "indie games"],
    "Console gaming": ["action-adventure", "platformers"],
    "Mobile gaming": ["casual games", "gacha games"],
    "Pop music": ["dance pop", "synth pop"],
    "Hip hop": ["trap", "boom bap"],
    "Classical music": ["baroque", "romantic era"],
    "Ball sports": ["football (soccer)", "basketball"],
    "Combat sports": ["boxing", "mma"],
    "Movie reviews": ["film analysis", "movie trailers"],
    "TV series": ["sitcoms", "dramas"],
    "Shonen": ["action shonen", "sports shonen"],
    "Seinen": ["psychological seinen", "slice of life"],
    "Smartphones": ["android phones", "iphone"],
    "PC hardware": ["graphics cards", "cpus"],
}


def build_tree(per_macro_mesos: int = 3, per_meso_micros: int = 3) -> Dict[str, Dict[str, List[str]]]:
    tree: Dict[str, Dict[str, List[str]]] = {}
    taken: set[str] = set()
    for macro in MACROS:
        mesos = fetch_wikipedia_subcats(macro, max_items=10)
        if not mesos:
            mesos = FALLBACK_MESO.get(macro, [])
        mesos = [m for m in mesos if m]
        mesos = dedup_keep_order(mesos)[: max(1, per_macro_mesos)]
        tree[macro] = {}
        for meso in mesos:
            micros = fetch_wikipedia_subcats(meso, max_items=12)
            if not micros:
                micros = FALLBACK_MICRO.get(meso, [])
            micros = [mi for mi in micros if mi]
            micros = [mi for mi in micros if norm_label(mi) not in taken and norm_label(mi) != norm_label(meso) and norm_label(mi) != norm_label(macro)]
            micros = dedup_keep_order(micros)[: max(1, per_meso_micros)]
            for mi in micros:
                taken.add(norm_label(mi))
            tree[macro][meso] = micros
        # Avoid empty macros by seeding from fallbacks
        if not tree[macro]:
            fm = FALLBACK_MESO.get(macro, [])[: max(1, per_macro_mesos)]
            for meso in fm:
                mi = FALLBACK_MICRO.get(meso, [])[: max(1, per_meso_micros)]
                tree[macro][meso] = mi
    return tree


def write_master_from_tree(tree: Dict[str, Dict[str, List[str]]], out_path: str) -> int:
    lines: List[str] = []
    for macro, mesos in tree.items():
        for meso, micros in mesos.items():
            for mi in micros:
                lab = norm_label(mi)
                if not lab:
                    continue
                lines.append(f"a video about {lab} | a photo of {lab}")
    # de-duplicate across full list, preserving order
    final: List[str] = []
    seen = set()
    for ln in lines:
        base = norm_label(ln)
        if base in seen:
            continue
        final.append(ln)
        seen.add(base)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(final) + "\n")
    return len(final)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build hierarchical mastercategories from a fixed macro tree")
    ap.add_argument('--out', default='Mesh/mastercategories.txt')
    ap.add_argument('--tree_out', default='Mesh/master_tree.json')
    ap.add_argument('--mesos', type=int, default=3, help='meso per macro')
    ap.add_argument('--micros', type=int, default=3, help='micro per meso')
    args = ap.parse_args()

    t0 = time.time()
    tree = build_tree(per_macro_mesos=args.mesos, per_meso_micros=args.micros)
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    n = write_master_from_tree(tree, args.out)
    with open(args.tree_out, 'w', encoding='utf-8') as f:
        json.dump(tree, f, indent=2, ensure_ascii=False)
    dt = (time.time() - t0)
    print(f"Wrote {n} labels to {args.out} and tree to {args.tree_out} in {dt:.2f}s")


if __name__ == '__main__':
    main()

