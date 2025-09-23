#!/usr/bin/env python3
"""
Build a curated, general + inclusive 1000-category master label list.

Output file: Mesh/mastercategories.txt

Notes on Category System:
- Mesh posts store a Category object with fields: macro, meso, micro.
- The master file here provides micro-level labels. Code derives macro/meso
  from the first two micro labels used on a post (see Mesh/category.py).
- Veil expects the prompt format per line:
      a video about <category> | a photo of <category>

Rules implemented here:
- Construct >=1000 raw candidates across domains.
- Normalize: lowercase, no punctuation, replace '&' with 'and'.
- Deduplicate: fuzzy match with rapidfuzz.token_set_ratio > 93.
- Guarantee essentials across domains and minimum per-domain coverage (>=10).
- Deterministic (seed=42).
- Final 1000 sorted by domain then alphabetical.

This script is self-contained and uses rapidfuzz if available; otherwise it
falls back to a simple token-set similarity that approximates token_set_ratio.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import random
import time
from typing import Dict, List, Tuple, Iterable, Set, Optional, Callable

try:
    from rapidfuzz.fuzz import token_set_ratio  # type: ignore
except Exception:  # pragma: no cover - fallback when not installed
    def token_set_ratio(a: str, b: str) -> float:  # type: ignore
        at = set(a.split())
        bt = set(b.split())
        if not at or not bt:
            return 0.0
        inter = len(at & bt)
        score = 100.0 * (2 * inter) / (len(at) + len(bt))
        return float(score)


SEED = 42
random.seed(SEED)

TARGET_COUNT = 1000


class _Progress:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._last = -1

    def update(self, percent: int, prefix: str = "") -> None:
        if not self.enabled:
            return
        p = max(1, min(100, int(percent)))
        if p == self._last:
            return
        print(f"\r{prefix}Progress: {p}%", end="", flush=True)
        if p >= 100:
            print("")
        self._last = p


def normalize(text: str) -> str:
    """Lowercase, replace & with 'and', remove punctuation except spaces.

    Also squashes repeated whitespace.
    """
    t = text.lower().replace("&", " and ")
    t = re.sub(r"[^a-z0-9\s/\-\(\)]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def unique_dedup(cands: Iterable[Tuple[str, str]], threshold: float = 75.0) -> List[Tuple[str, str]]:
    """Deduplicate by fuzzy token-set ratio on normalized values.

    cands: iterable of (domain, normalized_category)
    Returns a filtered list preserving first occurrence per near-duplicate cluster.
    """
    keep: List[Tuple[str, str]] = []
    seen_norm: List[str] = []
    for dom, cat in cands:
        is_dup = False
        for prev in seen_norm:
            if token_set_ratio(cat, prev) > threshold:
                is_dup = True
                break
        if not is_dup:
            keep.append((dom, cat))
            seen_norm.append(cat)
    return keep

# ------------------------------
# Hierarchical tree builder (infused)
# ------------------------------

# Fixed macro list for hierarchical builder
MACROS: List[str] = [
    "Gaming","Music","Sports","Movies & TV","Anime & Comics","Technology & Gadgets",
    "Science & Education","Art & Design","Fashion & Beauty","Food & Cooking","Travel & Places",
    "Cars & Vehicles","Health & Fitness","Lifestyle & Routines","History & Culture",
    "Politics & News","Finance & Business","Nature & Animals","DIY & How-To","Comedy & Memes",
    "Motivation & Self-Help","Mystery & Horror","Podcasts & Talk","Relationships & Community",
    "Spirituality & Philosophy",
]

# Map friendly macro names to Wikipedia category topics to broaden coverage
MACRO_WIKI_TOPICS: Dict[str, List[str]] = {
    "Gaming": ["Gaming", "Video games", "Esports", "Game development", "Board games"],
    "Music": ["Music", "Music genres", "Musicians", "Concerts", "Music industry"],
    "Sports": ["Sports", "Sports by type", "Recreational sports", "Outdoor recreation"],
    "Movies & TV": ["Film", "Television", "Cinematography", "Screenwriting", "Animation"],
    "Anime & Comics": ["Anime", "Manga", "Comics", "Graphic novels", "Light novels"],
    "Technology & Gadgets": ["Technology", "Electronics", "Gadgets", "Computing", "Robotics"],
    "Science & Education": ["Science", "Education", "STEM", "Research", "Academic disciplines"],
    "Art & Design": ["Art", "Design", "Architecture", "Visual arts", "Applied arts"],
    "Fashion & Beauty": ["Fashion", "Beauty", "Cosmetics", "Hairstyles", "Clothing"],
    "Food & Cooking": ["Food", "Cooking", "Cuisines", "Beverages", "Baking"],
    "Travel & Places": ["Travel", "Geography", "Tourism", "Landforms", "Attractions"],
    "Cars & Vehicles": ["Vehicles", "Automobiles", "Transport", "Aviation", "Rail transport"],
    "Health & Fitness": ["Health", "Physical fitness", "Exercise", "Wellness", "Nutrition"],
    "Lifestyle & Routines": ["Lifestyle", "Hobbies", "Leisure", "Daily routines"],
    "History & Culture": ["History", "Culture", "Cultural history", "World history"],
    "Politics & News": ["Politics", "News media", "Public policy", "Elections"],
    "Finance & Business": ["Finance", "Business", "Economics", "Entrepreneurship", "Investing"],
    "Nature & Animals": ["Nature", "Animals", "Wildlife", "Natural environment"],
    "DIY & How-To": ["Do it yourself", "Handicrafts", "Home improvement"],
    "Comedy & Memes": ["Comedy", "Internet memes", "Humor"],
    "Motivation & Self-Help": ["Self-help", "Personal development", "Motivation"],
    "Mystery & Horror": ["Horror", "Mystery fiction", "Thriller"],
    "Podcasts & Talk": ["Podcasts", "Talk radio", "Interviews"],
    "Relationships & Community": ["Relationships", "Community", "Social groups"],
    "Spirituality & Philosophy": ["Spirituality", "Philosophy", "Religion"],
}


def _dedup_keep_order(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for it in items:
        k = normalize(it)
        if not k or k in seen:
            continue
        out.append(k)
        seen.add(k)
    return out


_SUBCAT_CACHE: Dict[Tuple[str, int, int], List[str]] = {}


def _fetch_wikipedia_subcats(topic: str, max_items: int = 10, depth: int = 0) -> List[str]:
    """Fetch Wikipedia subcategories for a topic with pagination and optional depth.

    - Follows `cmcontinue` to accumulate up to `max_items` entries.
    - If `depth > 0`, performs a BFS into subcategories up to that depth.
    - Results are memoized per (normalized(topic), max_items, depth).
    - Best-effort: network errors yield [].
    """
    key = (normalize(topic), int(max_items), int(depth))
    if key in _SUBCAT_CACHE:
        return list(_SUBCAT_CACHE[key])

    try:
        import urllib.parse as up
        import urllib.request as ur
    except Exception:
        return []

    def _paged_fetch(cat_title: str, cap: int) -> List[str]:
        results: List[str] = []
        cont: Optional[str] = None
        # Wikipedia requires a descriptive User-Agent per policy
        headers = {
            "User-Agent": "Knot-Labs Category Builder/1.1 (+https://github.com/knotlabs; tools@knotlabs.local)",
        }
        while len(results) < cap:
            try:
                title = f"Category:{cat_title.replace(' ', '_')}"
                url = (
                    "https://en.wikipedia.org/w/api.php?action=query&list=categorymembers&cmtitle="
                    + up.quote(title)
                    + "&cmtype=subcat&cmlimit=50&format=json"
                )
                if cont:
                    url += "&cmcontinue=" + up.quote(cont)
                req = ur.Request(url, headers=headers)
                with ur.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                items = [m.get('title','') for m in (data.get('query',{}).get('categorymembers') or [])]
                for it in items:
                    it = re.sub(r"^Category:\s*", "", it)
                    if it:
                        results.append(it)
                        if len(results) >= cap:
                            break
                cont = None
                try:
                    cont = (data.get('continue', {}) or {}).get('cmcontinue')
                except Exception:
                    cont = None
                if not cont:
                    break
            except Exception:
                break
        return _dedup_keep_order(results)[:cap]

    # BFS over subcategories up to `depth`
    collected: List[str] = []
    collected_norm: Set[str] = set()
    seen_nodes: Set[str] = set()
    queue: List[Tuple[str, int]] = [(topic, 0)]
    while queue and len(collected) < max_items:
        node, d = queue.pop(0)
        node_key = normalize(node)
        if node_key in seen_nodes:
            continue
        seen_nodes.add(node_key)

        subs = _paged_fetch(node, cap=max(1, max_items - len(collected)))
        for s in subs:
            ns = normalize(s)
            if ns not in collected_norm:
                collected.append(s)
                collected_norm.add(ns)
                if len(collected) >= max_items:
                    break
        if d < depth:
            for s in subs:
                queue.append((s, d + 1))

    out = _dedup_keep_order(collected)[:max_items]
    _SUBCAT_CACHE[key] = list(out)
    return out


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

# Build a normalized-key view for robust lookups
_FALLBACK_MICRO_N: Dict[str, List[str]] = {normalize(k): v for k, v in FALLBACK_MICRO.items()}


def build_tree(per_macro_mesos: int = 3, per_meso_micros: int = 3, mesos_depth: int = 0, micros_depth: int = 0) -> Dict[str, Dict[str, List[str]]]:
    """Build a hierarchical category tree using Wikipedia subcategories with offline fallbacks.

    Returns a dict: {macro: {meso: [micro, ...], ...}, ...}
    """
    tree: Dict[str, Dict[str, List[str]]] = {}
    taken: set[str] = set()
    for macro in MACROS:
        # Broaden mesos by querying multiple related topics with optional depth
        meso_srcs: List[str] = []
        for t in MACRO_WIKI_TOPICS.get(macro, [macro]):
            meso_srcs.extend(_fetch_wikipedia_subcats(t, max_items=50, depth=mesos_depth))
        mesos = meso_srcs or _fetch_wikipedia_subcats(macro, max_items=10, depth=mesos_depth)
        if not mesos:
            mesos = FALLBACK_MESO.get(macro, [])
        mesos = [m for m in mesos if m]
        mesos = _dedup_keep_order(mesos)[: max(1, per_macro_mesos)]
        tree[macro] = {}
        for meso in mesos:
            micros = _fetch_wikipedia_subcats(meso, max_items=50, depth=micros_depth)
            if not micros:
                # robust fallback lookup using normalized keys
                micros = _FALLBACK_MICRO_N.get(normalize(meso), [])
            micros = [mi for mi in micros if mi]
            micros = [
                mi for mi in micros
                if normalize(mi) not in taken and normalize(mi) != normalize(meso) and normalize(mi) != normalize(macro)
            ]
            micros = _dedup_keep_order(micros)[: max(1, per_meso_micros)]
            for mi in micros:
                taken.add(normalize(mi))
            tree[macro][meso] = micros
        # Avoid empty macros by seeding from fallbacks
        if not tree[macro]:
            fm = FALLBACK_MESO.get(macro, [])[: max(1, per_macro_mesos)]
            for meso in fm:
                mi = FALLBACK_MICRO.get(meso, [])[: max(1, per_meso_micros)]
                tree[macro][meso] = mi
    return tree


def build_tree_by_count(target_micros: int, mesos_depth: int = 0, micros_depth: int = 0) -> Dict[str, Dict[str, List[str]]]:
    """Build a hierarchical tree sourced from Wikipedia, selecting up to target micro categories.

    Strategy:
    - Fetch mesos per macro via Wikipedia (fallback to known values).
    - Fetch micros per meso via Wikipedia (fallback where needed).
    - Round-robin across (macro, meso) buckets to pick unique micros until target is reached.
    - Return only the selected portions as a tree.
    """
    # Gather mesos per macro
    macro_to_mesos: Dict[str, List[str]] = {}
    for macro in MACROS:
        topics = MACRO_WIKI_TOPICS.get(macro, [macro])
        meso_accum: List[str] = []
        for t in topics:
            meso_accum.extend(_fetch_wikipedia_subcats(t, max_items=200, depth=mesos_depth))
        if not meso_accum:
            meso_accum = FALLBACK_MESO.get(macro, [])
        mesos = _dedup_keep_order(meso_accum)
        macro_to_mesos[macro] = mesos

    # Gather micros per (macro, meso)
    pool: Dict[Tuple[str, str], List[str]] = {}
    for macro, mesos in macro_to_mesos.items():
        for meso in mesos:
            micros = _dedup_keep_order(_fetch_wikipedia_subcats(meso, max_items=500, depth=micros_depth) or _FALLBACK_MICRO_N.get(normalize(meso), []))
            # Filter out obvious self/parent duplicates
            micros = [mi for mi in micros if normalize(mi) not in {normalize(meso), normalize(macro)}]
            pool[(macro, meso)] = micros

    # Round-robin selection
    selected_tree: Dict[str, Dict[str, List[str]]] = {m: {} for m in MACROS}
    used: Set[str] = set()
    buckets: List[Tuple[str, str]] = [k for k, v in pool.items() if v]
    idx: Dict[Tuple[str, str], int] = {k: 0 for k in buckets}

    while len(used) < target_micros and buckets:
        progressed = False
        new_buckets: List[Tuple[str, str]] = []
        for k in buckets:
            macro, meso = k
            arr = pool[k]
            i = idx[k]
            # advance to next unused micro
            while i < len(arr) and normalize(arr[i]) in used:
                i += 1
            if i < len(arr):
                mi = normalize(arr[i])
                used.add(mi)
                idx[k] = i + 1
                if meso not in selected_tree[macro]:
                    selected_tree[macro][meso] = []
                selected_tree[macro][meso].append(mi)
                progressed = True
                if len(used) >= target_micros:
                    break
                # keep this bucket for future rounds
                new_buckets.append(k)
            else:
                # bucket exhausted; drop it
                pass
        if not progressed:
            break
        buckets = new_buckets or buckets  # if all buckets appended, continue
    # Prune empty macros
    selected_tree = {ma: me for ma, me in selected_tree.items() if me}
    # If still empty, fall back to minimal tree
    if not selected_tree:
        return build_tree()
    return selected_tree


def write_master_from_tree(tree: Dict[str, Dict[str, List[str]]], out_path: str) -> int:
    """Write mastercategories.txt lines from a tree. Returns number of lines written.

    Supports both legacy trees where micros are a list[str] and extended trees where
    micros are a mapping {micro: [nanos...]}. Only micro labels are written to master.
    """
    lines: List[str] = []
    for macro, mesos in tree.items():
        for meso, micros in mesos.items():
            if isinstance(micros, dict):
                micro_iter = list(micros.keys())
            else:
                micro_iter = list(micros or [])
            for mi in micro_iter:
                lab = normalize(mi)
                if not lab:
                    continue
                lines.append(f"a video about {lab} | a photo of {lab}")
    # de-duplicate across full list, preserving order
    final: List[str] = []
    seen = set()
    for ln in lines:
        base = normalize(ln)
        if base in seen:
            continue
        final.append(ln)
        seen.add(base)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(final) + "\n")
    return len(final)


def _build_nanos_for_tree(
    tree: Dict[str, Dict[str, List[str]]],
    nanos_per_micro: int = 3,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> Dict[str, List[str]]:
    """Build nano categories for each micro by querying Wikipedia subcategories.

    Returns a mapping: {micro_label: [nano, ...]}.
    """
    micros: List[str] = []
    for _macro, mesos in tree.items():
        for _meso, micro_list in (mesos or {}).items():
            for mi in (micro_list or []):
                if mi:
                    micros.append(normalize(mi))
    total = len(micros) if micros else 1
    out: Dict[str, List[str]] = {}
    for i, mi in enumerate(micros, 1):
        nanos = _dedup_keep_order(_fetch_wikipedia_subcats(mi, max_items=20))[: max(0, int(nanos_per_micro))]
        out[mi] = nanos
        if progress_cb is not None:
            # nanos building accounts for 25% of the overall meter; scale here 0..100 for the sub-phase
            subp = int((i / total) * 100)
            progress_cb(subp)
    return out


def _embed_nanos_into_tree(tree: Dict[str, Dict[str, List[str]]], nanos_map: Dict[str, List[str]]) -> Dict[str, Dict[str, Dict[str, List[str]]]]:
    """Return a new tree where each meso maps to {micro: [nanos...]}."""
    new_tree: Dict[str, Dict[str, Dict[str, List[str]]]] = {}
    for macro, mesos in (tree or {}).items():
        new_tree[macro] = {}
        for meso, micro_list in (mesos or {}).items():
            micro_map: Dict[str, List[str]] = {}
            for mi in (micro_list or []):
                key = normalize(mi)
                micro_map[mi] = list(nanos_map.get(key, nanos_map.get(mi, [])) or [])
            new_tree[macro][meso] = micro_map
    return new_tree


def build_tree_and_write(
    out_path: Optional[str] = None,
    tree_out: Optional[str] = None,
    mesos: int = 3,
    micros: int = 3,
    total: Optional[int] = None,
    nanos: Optional[int] = None,
    mesos_depth: int = 0,
    micros_depth: int = 0,
    progress: bool = False,
) -> Dict[str, int]:
    """Programmatic entry to build the hierarchical tree and write outputs.

    - If total is provided (>0), selects up to that many micro categories via
      Wikipedia-driven round-robin across macros/mesos.
    - Otherwise, uses fixed counts per macro/meso as provided.
    - Writes mastercategories.txt (micro prompts) and master_tree.json (hierarchy)
    - Returns stats dict
    """
    # Default resolve under Mesh/ if not provided
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    if not out_path:
        os.makedirs(root_dir, exist_ok=True)
        out_path = os.path.join(root_dir, "mastercategories.txt")
    if not tree_out:
        os.makedirs(root_dir, exist_ok=True)
        tree_out = os.path.join(root_dir, "master_tree.json")

    t0 = time.time()
    prog = _Progress(enabled=progress)

    # Phase 1: build tree (micros)
    def _phase1(pct: int) -> None:
        # map sub-phase [0..100] -> overall [1..70]
        prog.update(1 + int(0.69 * max(0, min(100, pct))), prefix="(tree) ")

    if total is not None and int(total) > 0:
        # build by count, report progress during selection
        tree = build_tree_by_count(int(total), mesos_depth=mesos_depth, micros_depth=micros_depth)
        _phase1(100)
    else:
        # estimate progress across expected micros
        approx_total = max(1, int(mesos) * int(micros) * max(1, len(MACROS)))
        built = 0
        tree: Dict[str, Dict[str, List[str]]] = {}
        taken: set[str] = set()
        for macro in MACROS:
            # broaden mesos by using related topics and depth
            meso_srcs: List[str] = []
            for t in MACRO_WIKI_TOPICS.get(macro, [macro]):
                meso_srcs.extend(_fetch_wikipedia_subcats(t, max_items=50, depth=mesos_depth))
            meso_list = meso_srcs or _fetch_wikipedia_subcats(macro, max_items=10, depth=mesos_depth) or FALLBACK_MESO.get(macro, [])
            meso_list = _dedup_keep_order([m for m in meso_list if m])[: max(1, int(mesos))]
            tree[macro] = {}
            for meso in meso_list:
                micro_list = _fetch_wikipedia_subcats(meso, max_items=50, depth=micros_depth) or _FALLBACK_MICRO_N.get(normalize(meso), [])
                micro_list = [mi for mi in micro_list if mi]
                micro_list = [
                    mi for mi in micro_list
                    if normalize(mi) not in taken and normalize(mi) != normalize(meso) and normalize(mi) != normalize(macro)
                ]
                micro_list = _dedup_keep_order(micro_list)[: max(1, int(micros))]
                for mi in micro_list:
                    taken.add(normalize(mi))
                tree[macro][meso] = micro_list
                built += len(micro_list)
                _phase1(int(min(100, (built / approx_total) * 100)))
            if not tree[macro]:
                fm = FALLBACK_MESO.get(macro, [])[: max(1, int(mesos))]
                for m in fm:
                    mi = FALLBACK_MICRO.get(m, [])[: max(1, int(micros))]
                    tree[macro][m] = mi
                    built += len(mi)
                    _phase1(int(min(100, (built / approx_total) * 100)))

    # Phase 2: write master from tree
    n = write_master_from_tree(tree, out_path)
    prog.update(85, prefix="(write) ")

    # Phase 3: optionally build nanos and embed into the tree structure
    nanos_per_micro = 12 if nanos is None else int(nanos)
    if nanos_per_micro > 0:
        def _phase2_sub(pct: int) -> None:
            # map sub-phase [0..100] -> overall [70..95]
            prog.update(70 + int(0.25 * max(0, min(100, pct))), prefix="(nanos) ")
        nanos_map = _build_nanos_for_tree(tree, nanos_per_micro=nanos_per_micro, progress_cb=_phase2_sub)
        # Replace micros list with mapping micro -> nanos
        tree = _embed_nanos_into_tree(tree, nanos_map)  # type: ignore[assignment]
        prog.update(95, prefix="(nanos) ")

    # Write the (possibly extended) tree JSON
    with open(tree_out, 'w', encoding='utf-8') as f:
        json.dump(tree, f, indent=2, ensure_ascii=False)

    prog.update(100, prefix="(done) ")
    dt = time.time() - t0
    # Count nanos if embedded
    nanos_total = 0
    try:
        for _macro, mesos_d in (tree or {}).items():
            for _meso, micro_val in (mesos_d or {}).items():
                if isinstance(micro_val, dict):
                    for _mi, nanos_list in micro_val.items():
                        nanos_total += len(nanos_list or [])
    except Exception:
        nanos_total = 0
    return {"final": int(n), "macros": len(tree), "elapsed_s": int(dt), "nanos": int(nanos_total)}


def build_candidates() -> Dict[str, List[str]]:
    """Return raw candidate categories per domain (>=1000 total across domains).

    The lists intentionally include some overlaps and near-duplicates; the
    dedup step will consolidate them.
    """
    # For geographic and culture coverage, mix global terms; avoid brand names.
    people = [
        "children", "teenagers", "adults", "seniors", "parents", "families",
        "students", "teachers", "scientists", "engineers", "nurses", "doctors",
        "farmers", "artists", "musicians", "actors", "athletes", "coaches",
        "activists", "volunteers", "leaders", "entrepreneurs", "refugees",
        "immigrants", "indigenous peoples", "people with disabilities",
        "community workers", "craftspeople", "photographers", "chefs",
        "journalists", "programmers", "gamers", "streamers", "health workers",
        "researchers", "writers", "poets", "dancers", "pilots", "drivers",
        "construction workers", "mechanics", "electricians", "plumbers",
        "tailors", "designers", "barbers", "bakers", "cooks", "caregivers",
        "firefighters", "paramedics", "police officers", "postal workers",
        "market vendors", "street performers", "tour guides", "monastics",
        "clergy", "sailors", "fisherfolk", "miners", "foresters",
    ]

    activities = [
        "cooking", "baking", "grilling", "barbecue", "reading", "writing",
        "painting", "drawing", "sewing", "knitting", "weaving", "gardening",
        "farming", "meditation", "yoga", "pilates", "cycling", "running",
        "walking", "hiking", "camping", "fishing", "swimming", "diving",
        "photography", "videography", "blogging", "vlogging", "podcasting",
        "coding", "robotics", "woodworking", "metalworking", "ceramics",
        "calligraphy", "origami", "birdwatching", "stargazing", "volunteering",
        "recycling", "upcycling", "thrifting", "shopping", "travel planning",
        "language learning", "chess", "board gaming", "card playing",
        "tabletop roleplaying", "speedrunning",
    ]

    sports = [
        "football (soccer)", "american football", "basketball", "baseball",
        "cricket", "rugby", "tennis", "table tennis", "badminton", "volleyball",
        "golf", "swimming", "track and field", "boxing", "kickboxing",
        "judo", "karate", "taekwondo", "mma", "wrestling", "gymnastics",
        "ice hockey", "field hockey", "handball", "water polo", "surfing",
        "skateboarding", "snowboarding", "skiing", "cross country skiing",
        "biathlon", "cycling road", "mountain biking", "bmx", "climbing",
        "bouldering", "equestrian", "sailing", "rowing", "canoe sprint",
        "kayaking", "dragon boat", "fencing", "archery", "snooker", "darts",
        "pickleball", "padel", "ultimate frisbee", "disc golf",
        "figure skating", "speed skating", "triathlon", "duathlon",
    ]

    arts = [
        "painting", "sculpture", "photography", "film", "theater", "ballet",
        "opera", "street art", "graffiti", "calligraphy", "ceramics",
        "printmaking", "illustration", "design", "architecture",
        "fashion design", "interior design", "industrial design", "poetry",
        "novels", "short stories", "comics", "animation", "3d modeling",
        "digital art", "tattoo art", "installation art", "performance art",
    ]

    music = [
        "classical music", "jazz", "blues", "rock", "pop", "hip hop", "rap",
        "r and b", "soul", "reggae", "ska", "punk", "metal", "country",
        "folk", "electronic", "edm", "house", "techno", "trance",
        "drum and bass", "dubstep", "ambient", "soundtracks", "world music",
        "latin music", "k pop", "afrobeats", "gospel", "choir", "orchestra",
        "band", "dj", "singing", "songwriting", "music production",
        "live concert", "music festival",
    ]

    gaming = [
        "action games", "adventure games", "role playing games", "mmorpgs",
        "moba", "first person shooters", "third person shooters",
        "strategy games", "real time strategy", "turn based strategy",
        "simulation games", "sports games", "racing games", "fighting games",
        "platformers", "puzzle games", "indie games", "retro gaming",
        "speedrunning", "esports", "game streaming", "vr gaming",
        "mobile gaming", "board games", "card games", "tabletop rpgs",
        "dungeons and dragons",
    ]

    tech = [
        "smartphones", "computers", "laptops", "tablets", "wearables",
        "smart home", "internet of things", "robotics", "artificial intelligence",
        "machine learning", "data science", "programming", "cybersecurity",
        "cloud computing", "devops", "blockchain", "cryptocurrency",
        "augmented reality", "virtual reality", "3d printing", "drones",
        "space technology", "biotechnology", "medical technology", "green tech",
        "electric vehicles", "autonomous vehicles", "renewable energy",
        "edge computing", "computer vision", "natural language processing",
    ]

    science = [
        "astronomy", "astrophysics", "physics", "chemistry", "biology",
        "ecology", "geology", "meteorology", "oceanography", "paleontology",
        "psychology", "neuroscience", "genetics", "microbiology", "botany",
        "zoology", "anthropology", "archaeology", "sociology", "mathematics",
        "statistics", "climate science", "environmental science",
        "space exploration", "quantum science",
    ]

    health = [
        "nutrition", "healthy eating", "mental health", "wellness", "fitness",
        "workouts", "strength training", "cardio", "yoga", "meditation",
        "mindfulness", "sleep health", "public health", "epidemiology",
        "medicine", "disease prevention", "first aid", "pharmacy", "nursing",
        "pregnancy", "parenting health", "elder care", "disability support",
        "therapy", "addiction recovery", "physiotherapy", "dental care",
    ]

    food = [
        "breakfast", "lunch", "dinner", "desserts", "baking", "grilling",
        "barbecue", "vegan cooking", "vegetarian cooking",
        "gluten free cooking", "seafood", "poultry", "beef dishes",
        "pork dishes", "soups", "stews", "salads", "sandwiches", "pasta",
        "pizza", "sushi", "noodles", "rice dishes", "curries", "street food",
        "snacks", "beverages", "coffee", "tea", "juices", "smoothies",
        "cocktails", "wine", "beer", "fermented foods", "spices", "herbs",
        "bread baking", "cakes", "cookies", "chocolate", "ice cream",
    ]

    fashion = [
        "streetwear", "couture", "vintage fashion", "sustainable fashion",
        "handmade fashion", "ethical fashion", "men fashion", "women fashion",
        "kids fashion", "plus size fashion", "modest fashion", "accessories",
        "shoes", "sneakers", "jewelry", "watches", "fashion shows", "runway",
        "makeup", "hairstyles", "skincare", "nail art",
    ]

    lifestyle = [
        "home decor", "minimalism", "organization", "productivity", "self care",
        "mindfulness", "travel", "budgeting", "personal finance", "parenting",
        "relationships", "pet care", "sustainability", "diy projects",
        "crafts", "hobbies", "photography", "videography", "vlogging",
        "podcasting", "motivation", "inspiration", "wellbeing",
    ]

    nature = [
        "forests", "mountains", "deserts", "beaches", "oceans", "rivers",
        "lakes", "waterfalls", "glaciers", "volcanoes", "caves", "savannas",
        "tundra", "wetlands", "rainforests", "coral reefs", "meadows",
        "prairies", "islands", "reefs",
    ]

    animals = [
        "dogs", "cats", "horses", "cattle", "sheep", "goats", "pigs",
        "chickens", "ducks", "geese", "turkeys", "rabbits", "hamsters",
        "guinea pigs", "parrots", "songbirds", "eagles", "owls", "hawks",
        "falcons", "penguins", "seals", "whales", "dolphins", "sharks",
        "rays", "turtles", "snakes", "lizards", "frogs", "toads",
        "butterflies", "bees", "ants", "spiders", "beetles", "wolves",
        "foxes", "bears", "lions", "tigers", "leopards", "cheetahs",
        "hyenas", "giraffes", "zebras", "hippos", "rhinos", "elephants",
        "kangaroos", "koalas", "pandas", "monkeys", "gorillas",
        "chimpanzees", "orangutans", "camels", "llamas", "alpacas",
        "crocodiles", "alligators",
    ]

    vehicles = [
        "cars", "trucks", "buses", "motorcycles", "bicycles", "scooters",
        "skateboards", "trains", "subways", "trams", "airplanes",
        "helicopters", "drones", "ships", "boats", "sailboats", "yachts",
        "submarines", "rockets", "spacecraft", "electric cars", "hybrid cars",
        "autonomous cars", "off road vehicles", "construction vehicles",
        "farm machinery",
    ]

    places_core = [
        "cities", "villages", "towns", "parks", "museums", "libraries",
        "schools", "universities", "hospitals", "temples", "churches",
        "mosques", "synagogues", "markets", "restaurants", "cafes",
        "theaters", "stadiums", "airports", "train stations", "castles",
        "palaces", "monuments", "landmarks", "national parks",
    ]

    # Cities removed by request; we avoid city lists to reduce proper-noun bias.

    events = [
        "weddings", "birthdays", "funerals", "festivals", "concerts",
        "parades", "protests", "ceremonies", "conferences", "workshops",
        "competitions", "tournaments", "fairs", "exhibitions", "graduations",
        "awards", "holidays", "new year", "carnival", "marathons",
        "hackathons", "lan parties", "cultural celebrations", "religious holidays",
    ]

    objects = [
        "smartphone", "laptop", "tablet", "camera", "drone", "television",
        "monitor", "keyboard", "mouse", "printer", "bottle", "cup", "glass",
        "mug", "plate", "bowl", "spoon", "fork", "knife", "chair", "table",
        "sofa", "bed", "lamp", "clock", "watch", "wallet", "bag",
        "backpack", "umbrella", "book", "notebook", "pen", "pencil",
        "marker", "paintbrush", "scissors", "toolbox", "hammer", "screwdriver",
        "wrench", "saw", "drill", "helmet", "goggles", "mask",
    ]

    weather = [
        "sunny", "cloudy", "rainy", "stormy", "snowy", "windy", "foggy",
        "hazy", "thunderstorms", "lightning", "rainbow", "hail", "blizzard",
        "heatwave", "cold snap", "drought", "flooding", "tornado", "hurricane",
        "typhoon",
    ]

    emotions = [
        "happiness", "joy", "sadness", "anger", "fear", "surprise",
        "disgust", "love", "affection", "pride", "shame", "guilt",
        "anxiety", "calm", "relief", "excitement", "boredom", "curiosity",
        "nostalgia", "hope", "frustration", "confidence", "embarrassment",
        "loneliness", "friendliness", "kindness", "empathy",
    ]

    culture = [
        "literature", "philosophy", "religion", "spirituality", "mythology",
        "folklore", "languages", "linguistics", "dance", "cuisine",
        "traditions", "rituals", "festivals", "film culture", "pop culture",
        "counterculture", "heritage", "museums", "fine arts", "crafts",
        "calligraphy", "traditional dress", "kimono", "sari", "hanbok",
    ]

    content_formats = [
        "tutorials", "reviews", "unboxings", "walkthroughs", "documentaries",
        "vlogs", "news reports", "interviews", "podcasts", "live streams",
        "shorts", "trailers", "behind the scenes", "timelapses", "asmr",
        "memes", "parodies", "challenges", "pranks", "how to", "explainers",
        "listicles", "top ten", "highlights", "montages", "comparisons",
        "debates", "roundtables", "panel discussions", "lectures", "lessons",
    ]

    # SEED EXPANSIONS
    EXTRA_PEOPLE = [
        "influencers", "content creators", "data analysts", "product managers", "project managers",
        "ux designers", "ui designers", "graphic designers", "3d artists", "sound engineers",
        "mixing engineers", "video editors", "cinematographers", "screenwriters", "voice actors",
        "animators", "illustrators", "photoreporters", "biochemists", "bioinformaticians",
        "statisticians", "economists", "lawyers", "judges", "paramedics", "therapists",
        "psychologists", "veterinarians", "zookeepers", "librarians", "archivists",
        "curators", "park rangers", "meteorologists", "cartographers", "urban planners",
        "electric vehicle technicians", "drone pilots", "esports athletes", "game developers",
        "stream moderators", "community managers", "social media managers", "marketers",
        "copywriters", "salespeople", "hr specialists", "recruiters", "translators",
        "interpreters", "tour operators", "flight attendants", "ship captains", "baristas",
        "bartenders", "cheesemakers", "brewers", "distillers", "butchers", "fishmongers",
        "tailors and seamstresses", "cobblers", "watchmakers", "goldsmiths", "blacksmiths",
    ]

    EXTRA_ACTIVITIES = [
        "bouldering outdoors", "ice climbing", "trail running", "ultramarathons",
        "orienteering", "geocaching", "slacklining", "paragliding", "hang gliding",
        "windsurfing", "kitesurfing", "freediving", "spearfishing", "cave diving",
        "wild camping", "foraging", "beekeeping", "soap making", "candle making",
        "leatherworking", "glassblowing", "lockpicking (legal)", "juggling", "magic tricks",
        "speedcubing", "home lab science", "pcb soldering", "retro computing",
        "home automation", "mechanical keyboards", "drone racing", "fpv flying",
        "lego building", "miniature painting", "warhammer painting", "3d printing minis",
        "photobook making", "zine making", "calligraphy brush lettering",
    ]

    EXTRA_SPORTS = [
        "australian rules football", "gaelic football", "canadian football", "arena football",
        "lacrosse", "floorball", "netball", "softball", "hurling", "sepaktakraw",
        "kabaddi", "paddle tennis", "beach tennis", "indoor rowing", "coastal rowing",
        "skiff racing", "freestyle bmx", "downhill mountain biking", "cyclocross",
        "bikepacking", "parkour", "freerunning", "orienteering sport", "trail orienteering",
        "ultra trail running", "skyrunning", "snowshoeing", "telemark skiing", "nordic combined",
        "ski jumping", "snow kiting", "ice climbing competition", "sport climbing lead",
        "speed climbing", "ice cross downhill", "speedway", "motocross", "kart racing",
        "drifting", "rally", "rallycross", "enduro", "sailing dinghy", "windsurf racing",
        "kitesurf racing", "underwater hockey", "underwater rugby", "polo", "padel pro",
        "pickleball doubles", "cheerleading", "strongman", "powerlifting", "weightlifting",
        "arm wrestling", "futsal", "beach volleyball", "ultimate beach", "disc dog",
    ]

    EXTRA_ARTS = [
        "concept art", "matte painting", "storyboarding", "character design", "pixel art",
        "low poly art", "paper quilling", "encaustic painting", "airbrushing", "silkscreen",
        "risograph printing", "linocut", "woodcut", "marbling", "origami tessellations",
        "stained glass", "mosaic art", "ceramic glazing", "raku pottery", "weaving tapestries",
        "bookbinding", "letterpress", "fashion illustration", "costume design", "prop making",
    ]

    EXTRA_MUSIC = [
        "indie rock", "indie pop", "dream pop", "shoegaze", "grunge", "garage rock",
        "post rock", "math rock", "funk", "disco", "soul jazz", "bebop", "swing",
        "bluegrass", "americana", "progressive rock", "symphonic metal", "black metal",
        "death metal", "power metal", "kawaii metal", "synthwave", "retrowave",
        "vaporwave", "chiptune", "breakbeat", "two step", "garage", "jungle",
        "hard trance", "hardstyle", "psytrance", "tech house", "uk drill", "afro house",
        "baile funk", "reggaeton", "corridos tumbados", "cumbia", "soca", "dancehall",
        "bossa nova", "samba", "fado", "flamenco", "tango", "bolero", "klezmer",
    ]

    EXTRA_GAMING = [
        "roguelike games", "roguelite games", "extraction shooters", "battle royale games",
        "auto battlers", "deck builders", "idle clicker games", "tycoon games",
        "colony simulators", "city builders", "life sims", "dating sims", "visual novels",
        "otome games", "metroidvania games", "soulslike games", "puzzle platformers",
        "physics puzzle games", "party games", "local co op games", "competitive couch games",
        "educational games", "brain training games", "rhythm games", "dance games",
        "karaoke games", "music production games", "gacha games", "monster collecting games",
        "trading card games digital", "tabletop skirmish games",
    ]

    EXTRA_TECH = [
        "single board computers", "raspberry pi", "arduino projects", "microcontrollers",
        "embedded systems", "firmware engineering", "real time operating systems",
        "systems programming", "compilers", "program analysis", "static analysis",
        "distributed systems", "stream processing", "data engineering", "lakehouses",
        "vector databases", "retrieval augmented generation", "prompt engineering",
        "mlops", "feature stores", "auto ml", "federated learning", "on device ai",
        "edge ai", "robot operating system", "ros2", "slam", "drone autonomy",
        "digital signal processing", "audio dsp", "computer graphics", "ray tracing",
        "procedural generation", "webassembly", "wasm edge", "serverless",
        "observability", "telemetry", "sre", "site reliability engineering",
        "homelab", "self hosting", "nas builds", "reverse engineering",
        "malware analysis", "threat hunting", "privacy engineering",
    ]

    EXTRA_SCIENCE = [
        "astronautics", "planetary science", "exoplanets", "cosmology", "gravitational waves",
        "quantum computing", "condensed matter physics", "materials science",
        "photonic crystals", "nanotechnology", "supramolecular chemistry",
        "electrochemistry", "synthetic biology", "metagenomics", "proteomics",
        "epigenetics", "developmental biology", "systems neuroscience",
        "computational neuroscience", "cognitive science", "linguistics science",
        "behavioral economics", "game theory", "network science", "complex systems",
        "climate modeling", "glaciology", "hydrology", "geophysics", "petrology",
    ]

    EXTRA_HEALTH = [
        "functional fitness", "calisthenics", "hypertrophy training", "crossfit",
        "mobility training", "breathwork", "cold exposure", "sauna therapy",
        "sports nutrition", "macro tracking", "intuitive eating",
        "mental skills training", "sports psychology", "sleep optimization",
        "injury prevention", "physical therapy", "occupational therapy",
        "speech therapy", "dental hygiene", "dermatology", "endocrinology",
        "cardiology", "orthopedics", "sports medicine", "public health campaigns",
    ]

    EXTRA_FOOD = [
        "street tacos", "birria", "arepas", "pupusas", "ceviche", "pão de queijo",
        "feijoada", "chimichurri dishes", "empanadas", "mate drinks", "shawarma",
        "falafel", "hummus plates", "tabbouleh", "baklava", "kebabs", "mezze",
        "biryani", "butter chicken", "tandoori", "naan breads", "dosa", "idli",
        "pho", "banh mi", "bun cha", "pad thai", "som tam", "massaman curry",
        "bibimbap", "kimchi dishes", "ramen", "udon", "soba", "okonomiyaki",
        "takoyaki", "yakitori", "sukiyaki", "hot pot", "mapo tofu", "xiao long bao",
        "sourdough", "artisan cheese", "charcuterie", "kombucha", "kimchi fermenting",
    ]

    EXTRA_FASHION = [
        "avant garde fashion", "techwear", "gorpcore", "cottagecore", "normcore",
        "y2k fashion", "retro futurism", "minimalist wardrobe", "capsule wardrobe",
        "workwear style", "heritage menswear", "tailoring", "street goth",
        "athleisure", "performance wear", "denim culture", "sneaker culture",
        "custom sneakers", "japanese selvedge denim", "sustainable textiles",
        "natural dyes", "upcycled fashion", "3d printed fashion", "digital fashion",
        "runway styling", "editorial styling", "nail extensions", "barber fades",
    ]

    EXTRA_LIFESTYLE = [
        "bullet journaling", "second brain systems", "zettelkasten",
        "notion workflows", "markdown workflows", "life os systems",
        "time blocking", "pomodoro technique", "deep work routines",
        "habit stacking", "minimalist living", "vanlife", "tiny house living",
        "homesteading", "urban gardening", "zero waste", "thrifting flips",
        "houseplant care", "aquascaping", "reef tank keeping", "pet enrichment",
    ]

    EXTRA_NATURE = [
        "alpine meadows", "karst landscapes", "slot canyons", "sand dunes",
        "mangroves", "kelp forests", "peat bogs", "fen wetlands", "salt marshes",
        "badlands", "buttes and mesas", "lava fields", "moraines", "drumlins",
        "geyser basins", "hot springs", "tide pools", "barrier reefs",
    ]

    EXTRA_ANIMALS = [
        "marmots", "pikas", "wombats", "quokkas", "tasmanian devils",
        "tapirs", "okapis", "civets", "genets", "wildebeest", "antelope",
        "gazelles", "springboks", "ibex", "markhor", "snow leopards",
        "red pandas", "lynxes", "caracals", "shoebills", "albatrosses",
        "petrels", "boobies (birds)", "gannets", "cassowaries", "kiwis (birds)",
        "echidnas", "platypuses", "axolotls", "caecilians", "poison dart frogs",
        "mantis shrimps", "horseshoe crabs", "giant isopods", "tarantulas",
    ]

    EXTRA_VEHICLES = [
        "hot hatches", "muscle cars", "restomods", "kit cars", "track cars",
        "drift cars", "rally cars", "hypercars", "kei cars", "microcars",
        "luxury suvs", "overlanding rigs", "electric motorcycles",
        "classic motorcycles", "adventure bikes", "enduro bikes", "cafe racers",
        "scramblers", "cargo bikes", "gravel bikes", "recumbent bikes",
        "electric unicycles", "personal watercraft", "autogyros",
        "ultralight aircraft", "gliders", "sailplanes", "high speed trains",
    ]

    EXTRA_PLACES = [
        "botanical gardens", "arboretums", "zoos", "aquariums", "planetariums",
        "observatories", "science museums", "art galleries", "craft markets",
        "night markets", "food halls", "street food alleys", "co working spaces",
        "maker spaces", "innovation hubs", "community centers", "youth centers",
        "skate parks", "bmx parks", "climbing gyms", "indoor arenas",
        "concert halls", "opera houses", "music conservatories",
    ]

    EXTRA_EVENTS = [
        "comic conventions", "anime conventions", "makers fairs", "science fairs",
        "book fairs", "zine fests", "tattoo conventions", "lan parties",
        "speedrunning marathons", "game jams", "hack days", "startup demo days",
        "pitch competitions", "e sports tournaments", "robotics competitions",
        "cosplay contests", "film festivals", "photo walks", "photo marathons",
        "craft fairs", "farmers markets", "food truck rallies",
    ]

    EXTRA_OBJECTS = [
        "mechanical keyboard", "custom keycaps", "gaming mouse", "mousepad",
        "vr headset", "action camera", "gimbal", "tripod", "studio light",
        "softbox", "led panel", "lapel microphone", "shotgun microphone",
        "field recorder", "sampler", "synthesizer", "drum machine", "groovebox",
        "smartwatch", "fitness tracker", "e ink reader", "3d printer",
        "soldering station", "multimeter", "oscilloscope",
    ]

    EXTRA_WEATHER = [
        "stratocumulus clouds", "lenticular clouds", "mammatus clouds",
        "roll clouds", "cloud inversions", "sea fog", "freezing fog",
        "graupel", "sleet", "rime ice", "black ice", "dust storms", "haboobs",
        "polar stratospheric clouds", "aurora", "sun halos", "moon halos",
    ]

    EXTRA_EMOTIONS = [
        "awe", "melancholy", "serenity", "euphoria", "anticipation",
        "yearning", "schadenfreude", "sonder", "embarrassment humor",
        "flow state", "runner s high", "stage fright", "imposter syndrome",
    ]

    EXTRA_CULTURE = [
        "artisan crafts", "folk embroidery", "lace making", "tatreez",
        "ikat weaving", "batik", "block printing textiles", "indigo dyeing",
        "henna art", "kintsugi", "tea ceremony culture", "coffee ceremony culture",
        "call and response songs", "work songs", "sea shanties", "lullabies",
        "oral history projects", "story circles", "slam poetry",
    ]

    EXTRA_FORMATS = [
        "longform essays", "photo essays", "before and afters",
        "comparison shots", "side by sides", "explainer threads",
        "case studies", "teardowns", "build logs", "behind the build",
        "dev diaries", "patch notes", "release notes", "bug bounties",
        "live coding", "live music sessions", "studio sessions",
        "sound design breakdowns", "speedpaints", "process videos",
    ]

    # Actually extend the base lists
    people += EXTRA_PEOPLE
    activities += EXTRA_ACTIVITIES
    sports += EXTRA_SPORTS
    arts += EXTRA_ARTS
    music += EXTRA_MUSIC
    gaming += EXTRA_GAMING
    tech += EXTRA_TECH
    science += EXTRA_SCIENCE
    health += EXTRA_HEALTH
    food += EXTRA_FOOD
    fashion += EXTRA_FASHION
    lifestyle += EXTRA_LIFESTYLE
    nature += EXTRA_NATURE
    animals += EXTRA_ANIMALS
    vehicles += EXTRA_VEHICLES
    places_core += EXTRA_PLACES
    events += EXTRA_EVENTS
    objects += EXTRA_OBJECTS
    weather += EXTRA_WEATHER
    emotions += EXTRA_EMOTIONS
    culture += EXTRA_CULTURE
    content_formats += EXTRA_FORMATS

    # Expand places by appending the word 'city' to city names to avoid conflict
    # with other contexts and to increase candidates.
    places = places_core

    # Ensure each list is reasonably sized; total across domains should exceed 1000
    domain_map: Dict[str, List[str]] = {
        "PEOPLE": people,
        "ACTIVITIES": activities,
        "SPORTS": sports,
        "ARTS": arts,
        "MUSIC": music,
        "GAMING": gaming,
        "TECH": tech,
        "SCIENCE": science,
        "HEALTH": health,
        "FOOD": food,
        "FASHION": fashion,
        "LIFESTYLE": lifestyle,
        "NATURE": nature,
        "ANIMALS": animals,
        "VEHICLES": vehicles,
        "PLACES": places,
        "EVENTS": events,
        "OBJECTS": objects,
        "WEATHER": weather,
        "EMOTIONS": emotions,
        "CULTURE": culture,
        "FORMATS": content_formats,
    }
    return domain_map


def guarantee_essentials(domains: Dict[str, List[str]]) -> Set[Tuple[str, str]]:
    """Return a set of (domain, normalized_category) for must-have items."""
    essentials: List[Tuple[str, str]] = [
        ("SPORTS", "football (soccer)"),
        ("SPORTS", "american football"),
        ("ANIMALS", "cats"),
        ("ANIMALS", "dogs"),
        # Removed city essentials per request
        ("FOOD", "pizza"),
        ("FOOD", "sushi"),
        ("FORMATS", "tutorials"),
        ("FORMATS", "news reports"),
        ("EMOTIONS", "happiness"),
        ("EMOTIONS", "sadness"),
    ]
    out: Set[Tuple[str, str]] = set()
    for dom, cat in essentials:
        out.add((dom, normalize(cat)))
    return out


def build_final(target_count: int = TARGET_COUNT) -> List[Tuple[str, str]]:
    domains = build_candidates()

    # Normalize and tag by domain
    tagged: List[Tuple[str, str]] = []
    for dom, items in domains.items():
        for it in items:
            tagged.append((dom, normalize(it)))

    # Deduplicate across all using fuzzy token-set ratio
    deduped = unique_dedup(tagged, threshold=75.0)

    # Partition by domain after dedup
    by_dom: Dict[str, List[str]] = {}
    for dom, cat in deduped:
        by_dom.setdefault(dom, []).append(cat)

    # Shuffle deterministically within domains to avoid bias
    rng = random.Random(SEED)
    for cats in by_dom.values():
        rng.shuffle(cats)

    # Ensure minimum coverage per domain (>=10). Then fill remaining slots.
    final: List[Tuple[str, str]] = []
    required_min = 10
    must_have = guarantee_essentials(domains)
    included: Set[str] = set()

    # Add essentials first
    for dom, cat in must_have:
        if cat in by_dom.get(dom, []) and cat not in included:
            final.append((dom, cat))
            included.add(cat)

    # Ensure per-domain minimums
    for dom, cats in by_dom.items():
        count = 0
        for c in cats:
            if c in included:
                continue
            final.append((dom, c))
            included.add(c)
            count += 1
            if count >= required_min:
                break

    # Fill remaining up to target_count by round-robin across domains
    domain_keys = list(by_dom.keys())
    idx_map = {d: 0 for d in domain_keys}
    # Move indices past already used items
    for d in domain_keys:
        used = set(c for (dd, c) in final if dd == d)
        base = by_dom[d]
        i = 0
        while i < len(base) and base[i] in used:
            i += 1
        idx_map[d] = i

    while (target_count is None or target_count <= 0) or (len(final) < target_count):
        progressed = False
        for d in domain_keys:
            cats = by_dom[d]
            i = idx_map[d]
            while i < len(cats) and cats[i] in included:
                i += 1
            if i < len(cats):
                final.append((d, cats[i]))
                included.add(cats[i])
                idx_map[d] = i + 1
                progressed = True
                if len(final) >= target_count:
                    break
        if not progressed:
            break  # no more candidates

    # If we somehow exceed (should not), truncate deterministically
    if target_count is not None and target_count > 0:
        final = final[:target_count]

    # Sort by domain, then alphabetical within domain
    final.sort(key=lambda x: (x[0], x[1]))
    return final


def write_master(lines: List[Tuple[str, str]], out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        for dom, cat in lines:
            f.write(f"a video about {cat} | a photo of {cat}\n")


def build_and_write(out_path: str | None = None, target_count: int = TARGET_COUNT, progress: bool = False) -> Dict[str, int]:
    """Programmatic entry point used by the GUI.

    Returns a dict of basic stats.
    """
    prog = _Progress(enabled=progress)
    prog.update(1, prefix="(flat) ")
    domains = build_candidates()
    raw_count = sum(len(v) for v in domains.values())

    prog.update(20, prefix="(flat) ")
    # Normalize + dedup once for stats
    tagged: List[Tuple[str, str]] = []
    for dom, items in domains.items():
        for it in items:
            tagged.append((dom, normalize(it)))
    deduped = unique_dedup(tagged)

    prog.update(50, prefix="(flat) ")
    final = build_final(target_count)

    # Default path: Mesh/mastercategories.txt (parent of this tools/ dir)
    if not out_path:
        out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "mastercategories.txt")
    out_path = os.path.abspath(out_path)
    prog.update(90, prefix="(flat) ")
    write_master(final, out_path)
    prog.update(100, prefix="(flat) ")

    return {
        "candidates": raw_count,
        "unique": len(deduped),
        "final": len(final),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Build Mesh/mastercategories.txt (1000 micro labels) or hierarchical tree")
    p.add_argument("--output", default=None, help="Output path for mastercategories.txt (default Mesh/mastercategories.txt)")
    p.add_argument("--count", type=int, default=TARGET_COUNT, help="Target count (flat mode) or total micro labels in tree mode")
    # Hierarchical options
    p.add_argument("--use-tree", action="store_true", help="Build using hierarchical macro/meso/micro(+nano) tree and also write master_tree.json")
    p.add_argument("--tree-out", default=None, help="Path for master_tree.json (default Mesh/master_tree.json)")
    p.add_argument("--mesos", type=int, default=3, help="meso per macro (tree mode)")
    p.add_argument("--micros", type=int, default=3, help="micro per meso (tree mode)")
    p.add_argument("--nanos", type=int, default=None, help="nano per micro (tree mode; default 12; pass 0 to skip)")
    p.add_argument("--depth-mesos", type=int, default=0, help="subcategory depth for mesos discovery (0=no recursion)")
    p.add_argument("--depth-micros", type=int, default=0, help="subcategory depth for micros discovery (0=no recursion)")
    p.add_argument("--progress", action="store_true", default=True, help="show a 1%-100% progress meter")
    args = p.parse_args()

    if args.use_tree:
        stats = build_tree_and_write(
            out_path=args.output,
            tree_out=args.tree_out,
            mesos=args.mesos,
            micros=args.micros,
            total=args.count,
            nanos=args.nanos,
            mesos_depth=args.depth_mesos,
            micros_depth=args.depth_micros,
            progress=args.progress,
        )
        out_path = args.output or os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)), "mastercategories.txt")
        tree_out = args.tree_out or os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)), "master_tree.json")
        print(f"Final (tree micros): {stats['final']}")
        print(f"Wrote: {os.path.abspath(out_path)}")
        print(f"Tree: {os.path.abspath(tree_out)}")
    else:
        stats = build_and_write(out_path=args.output, target_count=args.count, progress=args.progress)
        # Resolve path for print
        out_path = args.output or os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)), "mastercategories.txt")
        print(f"Candidates: {stats['candidates']}")
        print(f"Unique (post-normalize+dedup): {stats['unique']}")
        print(f"Final: {stats['final']} (expected {args.count})")
        print(f"Wrote: {os.path.abspath(out_path)}")


if __name__ == "__main__":
    main()

