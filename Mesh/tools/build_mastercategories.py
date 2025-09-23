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
        "Farmer","Hunter","Gatherer","Fisherman","Shepherd","Nomad","Villager","City Dweller","Merchant","Trader",
        "Soldier","Knight","Samurai","Ninja","Viking","Pirate","Gladiator","Spartan","Legionnaire","Musketeer",
        "Monk","Priest","Nun","Shaman","Druid","Mystic","Oracle","Prophet","Sage","Hermit",
        "King","Queen","Prince","Princess","Duke","Duchess","Emperor","Empress","Pharaoh","Chief",
        "President","Prime Minister","Governor","Mayor","Senator","Ambassador","Diplomat","Councilor","Chancellor","Ruler",
        "Lawyer","Judge","Jury Member","Police Officer","Detective","Sheriff","Marshal","Warden","Prisoner","Criminal",
        "Doctor","Nurse","Surgeon","Dentist","Pharmacist","Veterinarian","Therapist","Psychologist","Psychiatrist","Paramedic",
        "Scientist","Physicist","Chemist","Biologist","Astronomer","Mathematician","Engineer","Architect","Inventor","Researcher",
        "Teacher","Professor","Student","Librarian","Historian","Archaeologist","Anthropologist","Geographer","Scribe","Scholar",
        "Writer","Poet","Novelist","Playwright","Journalist","Editor","Publisher","Blogger","Vlogger","Podcaster",
        "Musician","Singer","Composer","Conductor","DJ","Rapper","Producer","Drummer","Guitarist","Pianist",
        "Actor","Actress","Comedian","Performer","Dancer","Mime","Magician","Circus Performer","Acrobat","Clown",
        "Athlete","Runner","Swimmer","Cyclist","Boxer","Wrestler","Gymnast","Weightlifter","Skater","Skier",
        "Football Player","Basketball Player","Baseball Player","Cricketer","Rugby Player","Tennis Player","Golfer","Hockey Player","Volleyball Player","Esports Player",
        "Artist","Painter","Sculptor","Illustrator","Designer","Photographer","Animator","Cartoonist","Calligrapher","Graffiti Artist",
        "Craftsman","Carpenter","Blacksmith","Potter","Glassblower","Jeweler","Tailor","Seamstress","Shoemaker","Weaver",
        "Chef","Cook","Baker","Butcher","Brewer","Winemaker","Barista","Bartender","Sommelier","Caterer",
        "Pilot","Astronaut","Sailor","Captain","Navigator","Explorer","Adventurer","Pioneer","Colonist","Mountaineer",
        "Worker","Laborer","Miner","Factory Worker","Construction Worker","Mechanic","Technician","Electrician","Plumber","Welder",
        "Driver","Truck Driver","Taxi Driver","Bus Driver","Train Conductor","Subway Operator","Chauffeur","Racer","Delivery Worker","Courier",
        "Shopkeeper","Cashier","Waiter","Waitress","Host","Hostess","Salesperson","Marketer","Advertiser","Promoter",
        "Entrepreneur","Businessman","Businesswoman","Investor","CEO","Manager","Clerk","Accountant","Auditor","Banker",
        "Far-Right Politician","Far-Left Politician","Activist","Revolutionary","Protester","Rebel","Freedom Fighter","Pacifist","Philanthropist","Volunteer",
        "Citizen","Immigrant","Refugee","Exile","Tourist","Traveler","Nomadic Tribe Member","Urban Resident","Rural Resident","Suburban Resident",
        "Friend","Parent","Mother","Father","Son","Daughter","Brother","Sister","Child","Infant",
        "Teenager","Young Adult","Adult","Elder","Grandparent","Ancestor","Descendant","Mentor","Apprentice","Student Activist",
        "Hero","Villain","Antihero","Sidekick","Leader","Follower","Legend","Mythical Figure","Martyr","Saint",
        "God","Goddess","Demi-God","Angel","Demon","Spirit","Ghost","Vampire","Werewolf","Zombie",
        "Wizard","Witch","Sorcerer","Alchemist","Necromancer","Enchanter","Warlock","Healer","Seer","Illusionist",
        "Cyberpunk Hacker","AI Researcher","Programmer","Gamer","Streamer","Influencer","Model","Athleisure Influencer","Content Creator","Digital Nomad",
        "Farmer’s Market Vendor","Street Performer","Graffiti Writer","Tattoo Artist","Piercer","Fashion Designer","Hairstylist","Makeup Artist","Nail Technician","Bodybuilder",
        "Survivalist","Prepper","Minimalist","Maximalist","Collector","Hobbyist","Tinkerer","DIYer","Inventor-Entrepreneur","Maker",
        "Environmental Activist","Climate Scientist","Conservationist","Park Ranger","Wildlife Biologist","Zookeeper","Animal Rights Activist","Pet Owner","Trainer","Breeder",
        "Politician","Philosopher","Thinker","Strategist","General","Commander","Spy","Agent","Diplomat","Envoy"
    ]


    activities = [
        "Reading","Writing","Drawing","Painting","Sculpting","Photography","Filmmaking","Acting","Singing","Dancing",
        "Playing Guitar","Playing Piano","Playing Violin","Playing Drums","Playing Flute","DJing","Composing Music","Songwriting","Karaoke","Beatboxing",
        "Cooking","Baking","Grilling","Brewing Coffee","Tea Making","Wine Tasting","Beer Brewing","Bartending","Mixology","Cake Decorating",
        "Gardening","Farming","Composting","Beekeeping","Fishing","Hunting","Foraging","Birdwatching","Mushroom Picking","Flower Arranging",
        "Hiking","Camping","Backpacking","Trekking","Mountaineering","Rock Climbing","Bouldering","Caving","Canyoning","Trail Running",
        "Cycling","Mountain Biking","Road Biking","BMX","Skateboarding","Rollerblading","Scootering","Surfing","Snowboarding","Skiing",
        "Swimming","Diving","Snorkeling","Kayaking","Canoeing","Rowing","Sailing","Stand-Up Paddleboarding","Jet Skiing","Water Skiing",
        "Running","Jogging","Walking","Racewalking","Parkour","Freerunning","Obstacle Course Racing","CrossFit","Yoga","Pilates",
        "Meditation","Mindfulness","Tai Chi","Qigong","Martial Arts","Boxing Training","Kickboxing Training","Wrestling Practice","Self-Defense","Fencing Practice",
        "Weightlifting","Bodybuilding","Powerlifting","Strongman Training","Calisthenics","Stretching","Aerobics","Spinning","Jump Rope","Hula Hooping",
        "Chess","Checkers","Backgammon","Card Games","Poker","Bridge","Dominoes","Mahjong","Sudoku","Crosswords",
        "Board Games","Tabletop RPGs","Dungeons and Dragons","Warhammer","Miniature Painting","Trading Card Games","Magic: The Gathering","Yu-Gi-Oh!","Pokémon TCG","Deckbuilding Games",
        "Video Gaming","PC Gaming","Console Gaming","Mobile Gaming","VR Gaming","Esports","Speedrunning","Game Streaming","Game Collecting","Game Modding",
        "Knitting","Crocheting","Sewing","Embroidery","Quilting","Weaving","Macrame","Calligraphy","Origami","Papercraft",
        "Woodworking","Carpentry","Metalworking","Blacksmithing","Leathercraft","Pottery","Ceramics","Glassblowing","Jewelry Making","Stone Carving",
        "Cooking Classes","Art Classes","Dance Classes","Music Lessons","Language Learning","Math Tutoring","Science Experiments","Robotics","Electronics Hacking","3D Printing",
        "Coding","Web Development","App Development","Game Development","AI Programming","Ethical Hacking","Data Science","Machine Learning","Blogging","Podcasting",
        "Social Media Posting","Photography Blogging","Vlogging","Livestreaming","Video Editing","Graphic Design","Animation","3D Modeling","Illustration","Digital Painting",
        "Shopping","Window Shopping","Thrifting","Collecting Stamps","Collecting Coins","Collecting Comics","Collecting Action Figures","Collecting Sneakers","Collecting Vinyl Records","Antique Hunting",
        "Traveling","Backpacking Abroad","Road Trips","Couchsurfing","Volunteering","Cultural Exchange","Visiting Museums","Visiting Art Galleries","Visiting Zoos","Visiting Aquariums",
        "Attending Concerts","Going to Festivals","Watching Movies","Watching TV","Watching Anime","Listening to Podcasts","Listening to Audiobooks","Live Theater","Musical Theater","Opera Attendance",
        "Photography Tours","Food Tours","Pub Crawls","Cooking Competitions","Dance Competitions","Karaoke Nights","Trivia Nights","Escape Rooms","Board Game Cafés","Arcades",
        "Meditation Retreats","Yoga Retreats","Silent Retreats","Camping Retreats","Survival Training","Bushcraft","Fire Starting","Shelter Building","Navigation Practice","Stargazing",
        "Astrophotography","Meteor Watching","Solar Observation","Amateur Astronomy","Geocaching","Treasure Hunting","Metal Detecting","Drone Flying","Kite Flying","RC Cars",
        "RC Planes","RC Boats","Model Building","LEGO Building","Puzzle Solving","Jigsaw Puzzles","Rubik’s Cube","Logic Puzzles","Brain Teasers","Escape Puzzle Boxes",
        "Wine Making","Cheese Making","Charcuterie Crafting","Pickling","Fermenting","Jam Making","Chocolatiering","Candy Making","Ice Cream Making","Bread Making",
        "Community Service","Fundraising","Public Speaking","Debating","Storytelling","Poetry Reading","Creative Writing","Journal Writing","Diary Keeping","Scrapbooking",
        "Pet Training","Dog Walking","Cat Care","Horseback Riding","Falconry","Animal Rescue Volunteering","Pet Grooming","Pet Sitting","Aquarium Keeping","Terrarium Building",
        "Collecting Crystals","Collecting Fossils","Collecting Shells","Rock Tumbling","Mineral Hunting","Archaeology Hobby","Historical Reenactments","Cosplay","Costume Making","Prop Building",
        "Fashion Design","Makeup Artistry","Nail Art","Hair Styling","Tattooing","Piercing","Henna Art","Face Painting","Body Painting","Performance Art",
        "DJ Nights","Silent Discos","Club Dancing","Line Dancing","Square Dancing","Swing Dancing","Belly Dancing","Pole Dancing","Salsa Dancing","Flamenco Dancing"
    ]


    sports = [
        "Soccer","American Football","Basketball","Baseball","Softball","Ice Hockey","Field Hockey","Lacrosse","Rugby Union","Rugby League",
        "Cricket","Tennis","Table Tennis","Badminton","Squash","Pickleball","Volleyball","Beach Volleyball","Handball","Water Polo",
        "Boxing","Kickboxing","Muay Thai","Karate","Taekwondo","Kung Fu","Judo","Aikido","Brazilian Jiu-Jitsu","Sambo",
        "Wrestling","Greco-Roman Wrestling","Freestyle Wrestling","Sumo","MMA","Capoeira","Savate","Krav Maga","Pencak Silat","Hapkido",
        "Fencing","Archery","Shooting","Biathlon","Modern Pentathlon","Triathlon","Decathlon","Heptathlon","Pentathlon","CrossFit",
        "Gymnastics","Artistic Gymnastics","Rhythmic Gymnastics","Trampoline","Parkour","Cheerleading","Acrobatics","Pole Sports","Calisthenics","Aerobics",
        "Track and Field","Sprinting","Marathon","Relay Race","Hurdles","Pole Vault","High Jump","Long Jump","Triple Jump","Shot Put",
        "Discus Throw","Hammer Throw","Javelin Throw","Racewalking","Steeplechase","Trail Running","Ultramarathon","Mountain Running","Orienteering","Cross Country",
        "Cycling","Road Cycling","Track Cycling","BMX","Mountain Biking","Cyclocross","Freestyle BMX","Indoor Cycling","Bike Polo","Unicycle Sports",
        "Swimming","Synchronized Swimming","Diving","Open Water Swimming","Water Aerobics","Surfing","Bodyboarding","Windsurfing","Kitesurfing","Sailing",
        "Rowing","Canoeing","Kayaking","Dragon Boat Racing","Rafting","Stand-Up Paddleboarding","Fishing Sport","Spearfishing","Freediving","Scuba Diving",
        "Skiing","Alpine Skiing","Nordic Skiing","Cross-Country Skiing","Ski Jumping","Freestyle Skiing","Mogul Skiing","Backcountry Skiing","Telemark Skiing","Snowboarding",
        "Halfpipe","Slopestyle","Big Air","Snowshoeing","Ice Climbing","Speed Skating","Figure Skating","Pairs Skating","Synchronized Skating","Curling",
        "Skeleton","Luge","Bobsleigh","Ice Sailing","Snowmobiling","Dog Sledding","Skijoring","Snow Kiting","Ice Fishing","Winter Triathlon",
        "Golf","Mini Golf","Disc Golf","FootGolf","Cricket Bowling","Cricket Batting","Gaelic Football","Hurling","Camogie","Shinty",
        "Australian Rules Football","Canadian Football","Arena Football","Flag Football","Touch Rugby","Wheelchair Rugby","Paralympic Football","Blind Soccer","Powerchair Football","Amputee Football",
        "Esports","Chess","Go","Shogi","Xiangqi","Draughts","Checkers","Dominoes","Backgammon","Bridge",
        "Poker","Mahjong","Carrom","Billiards","Pool","Snooker","Croquet","Bocce","Petanque","Lawn Bowls",
        "Equestrian","Dressage","Show Jumping","Eventing","Horse Racing","Polo","Polocrosse","Vaulting","Endurance Riding","Harness Racing",
        "Rodeo","Bull Riding","Bronc Riding","Calf Roping","Steer Wrestling","Barrel Racing","Cutting","Reining","Team Penning","Campdrafting",
        "Motorsport","Formula 1","NASCAR","IndyCar","Rallying","Kart Racing","Drag Racing","Motorcycle Racing","MotoGP","Superbike",
        "Motocross","Enduro","Trials","Freestyle Motocross","Sidecar Racing","Truck Racing","Monster Trucks","Boat Racing","Jet Ski Racing","Air Racing",
        "Climbing","Bouldering","Sport Climbing","Lead Climbing","Speed Climbing","Mountaineering","Alpinism","Caving","Canyoning","Via Ferrata",
        "Strength Sports","Weightlifting","Powerlifting","Strongman","Highland Games","Stone Lifting","Armlifting","Grip Sport","Tug of War","Stone Put",
        "Combat Archery","Laser Tag","Paintball","Airsoft","Dodgeball","Kickball","Capture the Flag","Quidditch","Ultimate Frisbee","Frisbee Freestyle",
        "DanceSport","Ballet","Ballroom Dancing","Latin Dancing","Breakdancing","Hip-Hop Dance","Jazz Dance","Contemporary Dance","Tap Dance","Salsa Dance",
        "Martial Arts Trickings","Stunt Performance","Stage Combat","Medieval Combat","Historical Fencing","LARP Combat","Battle Reenactment","Armored Combat League","HEMA","Glima",
        "Adventure Racing","Obstacle Course Racing","Mud Run","Tough Mudder","Spartan Race","Endurocross","Eco-Challenge","Ultra Trail","Bikepacking","Adventure Triathlon",
        "Traditional Games","Kabaddi","Kho-Kho","Sepak Takraw","Wushu","Dragon Dance Sport","Tai Chi Competition","Yoga Asana Sport","Mallakhamb","Stick Fighting",
        "Exotic Sports","Cheese Rolling","Zorbing","Bossaball","Bubble Soccer","Underwater Hockey","Underwater Rugby","Underwater Target Shooting","Sandboarding","Volcano Boarding",
        "Paragliding","Hang Gliding","Skydiving","BASE Jumping","Wingsuit Flying","Parasailing","Gliding","Microlight Flying","Paramotoring","Bungee Jumping",
        "Arm Wrestling","Slap Fighting","Highland Tug-of-War","Egg-and-Spoon Race","Sack Race","Wheelbarrow Race","Log Rolling","Stone Skipping","Gurning Contest","Shin Kicking"
    ]

    arts = [
        "Prehistoric Art","Cave Painting","Petroglyphs","Ancient Egyptian Art","Greek Classical Art","Roman Art","Byzantine Art","Medieval Art","Romanesque","Gothic",
        "Renaissance","High Renaissance","Early Renaissance","Mannerism","Baroque","Rococo","Neoclassicism","Romanticism","Realism","Academic Art",
        "Impressionism","Post-Impressionism","Expressionism","Fauvism","Symbolism","Art Nouveau","Arts and Crafts","Jugendstil","Secession","Cubism",
        "Analytical Cubism","Synthetic Cubism","Orphism","Constructivism","Futurism","Vorticism","Dada","Surrealism","Metaphysical Art","Magic Realism",
        "Abstract Art","Abstract Expressionism","Action Painting","Color Field Painting","Tachisme","Lyrical Abstraction","Minimalism","Hard-Edge Painting","Geometric Abstraction","Op Art",
        "Pop Art","Neo-Dada","Fluxus","Performance Art","Conceptual Art","Happenings","Body Art","Land Art","Earth Art","Installation Art",
        "Environmental Art","Kinetic Art","Light Art","Sound Art","New Media Art","Digital Art","Generative Art","Algorithmic Art","AI Art","Glitch Art",
        "Pixel Art","NFT Art","Crypto Art","Interactive Art","Virtual Reality Art","Augmented Reality Art","Video Art","Projection Mapping","Internet Art","Web Art",
        "Photography","Pictorialism","Straight Photography","Documentary Photography","Street Photography","Portrait Photography","Fashion Photography","Fine Art Photography","Photojournalism","Surreal Photography",
        "Collage","Photomontage","Assemblage","Mixed Media","Found Object Art","Ready-Mades","Recycled Art","Junk Art","Graffiti","Street Art",
        "Stencil Art","Muralism","Political Art","Protest Art","Social Practice Art","Community Art","Outsider Art","Naïve Art","Visionary Art","Art Brut",
        "Folk Art","Indigenous Art","Tribal Art","Aboriginal Art","Oceanic Art","African Art","Native American Art","Pre-Columbian Art","Islamic Art","Persian Miniature",
        "Indian Miniature","Chinese Painting","Japanese Ink Painting","Ukiyo-e","Nihonga","Korean Painting","Tibetan Thangka","Mongolian Art","Himalayan Art","Southeast Asian Art",
        "Calligraphy","Illuminated Manuscripts","Heraldic Art","Cartographic Art","Scientific Illustration","Medical Illustration","Botanical Illustration","Zoological Illustration","Technical Drawing","Architectural Drawing",
        "Landscape Painting","Seascape","Cityscape","Still Life","Portrait","Self-Portrait","Genre Painting","History Painting","Mythological Painting","Religious Painting",
        "Allegorical Painting","Narrative Art","Symbolic Art","Decorative Art","Pattern Art","Tapestry","Textile Art","Fiber Art","Embroidery","Quilting",
        "Weaving","Macrame","Fashion Illustration","Costume Design","Stage Design","Set Design","Poster Art","Printmaking","Woodcut","Etching",
        "Engraving","Lithography","Screen Printing","Monotype","Mezzotint","Relief Printing","Intaglio","Digital Printmaking","3D Printing Art","Ceramics",
        "Pottery","Porcelain","Earthenware","Stoneware","Tile Art","Sculpture","Relief Sculpture","Free-Standing Sculpture","Kinetic Sculpture","Assemblage Sculpture",
        "Bronze Sculpture","Marble Sculpture","Wood Sculpture","Ice Sculpture","Sand Sculpture","Glass Art","Blown Glass","Stained Glass","Fused Glass","Cold Glass",
        "Metalwork","Goldsmithing","Silversmithing","Ironwork","Blacksmithing","Jewelry Art","Adornment Art","Mask Making","Totem Carving","Ivory Carving",
        "Mosaic","Fresco","Encaustic Painting","Tempera Painting","Oil Painting","Acrylic Painting","Watercolor","Gouache","Ink Wash","Spray Paint",
        "Airbrush Art","Digital Painting","Matte Painting","Concept Art","Character Design","Environment Design","Fantasy Art","Sci-Fi Art","Comic Art","Manga Art",
        "Anime Art","Cartoon Art","Illustration","Book Illustration","Children’s Book Illustration","Editorial Illustration","Magazine Art","Zine Art","Graphic Design","Typography",
        "Poster Design","Logo Design","Commercial Art","Advertising Art","Packaging Art","Product Design","Industrial Design","UX/UI Design","Motion Graphics","Infographic Design",
        "Political Cartoon","Caricature","Satirical Art","Humorous Art","Whimsical Art","Naïf Modernism","Neo-Expressionism","Transavantgarde","Bad Painting","Lowbrow Art",
        "Kustom Kulture","Hot Rod Art","Tattoo Art","Body Modification Art","Henna Art","Piercing Art","Performance Tattoo","Street Tattoo","Biomechanical Tattoo","Traditional Tattoo",
        "Contemporary Tattoo","Japanese Tattoo","Tribal Tattoo","Polynesian Tattoo","Maori Tattoo","Celtic Tattoo","Mandala Tattoo","Blackwork Tattoo","Dotwork Tattoo","Minimalist Tattoo",
        "Hyperrealism","Photorealism","Superflat","Comic Realism","Neo-Surrealism","Neo-Futurism","Afrofuturism","Speculative Art","Metamodernism","Post-Internet Art"
    ]


    music = [
        "Pop","Rock","Hip Hop","R&B","Jazz","Blues","Classical","Electronic","Folk","Country",
        "Metal","Punk","Reggae","Soul","Funk","Gospel","Opera","House","Techno","Trance",
        "Dubstep","Drum and Bass","Garage","Disco","EDM","Synthpop","New Wave","Indie Rock","Indie Pop","Alternative Rock",
        "Progressive Rock","Psychedelic Rock","Hard Rock","Soft Rock","Grunge","Shoegaze","Post-Rock","Math Rock","Krautrock","Space Rock",
        "Heavy Metal","Thrash Metal","Death Metal","Black Metal","Doom Metal","Power Metal","Symphonic Metal","Gothic Metal","Folk Metal","Nu Metal",
        "Metalcore","Deathcore","Progressive Metal","Industrial Metal","Sludge Metal","Stoner Metal","Groove Metal","Avant-Garde Metal","Viking Metal","Glam Metal",
        "Rap","Trap","Boom Bap","Drill","Cloud Rap","Mumble Rap","Gangsta Rap","Conscious Hip Hop","Lo-fi Hip Hop","Jazz Rap",
        "Latin Hip Hop","Chopped and Screwed","Crunk","Hyphy","Bounce","Old School Hip Hop","Golden Age Hip Hop","Experimental Hip Hop","Alternative Hip Hop","Freestyle Rap",
        "Reggaeton","Dancehall","Ska","Rocksteady","Dub","Roots Reggae","Lovers Rock","Soca","Calypso","Mento",
        "Afrobeat","Afrobeats","Highlife","Juju","Fuji","Kuduro","Kizomba","Soukous","Makossa","Gqom",
        "Amapiano","Zouglou","Bongo Flava","Hiplife","Palm-Wine Music","Mbalax","Kwela","Marabi","Township Jive","Shangaan Electro",
        "Latin Pop","Salsa","Merengue","Bachata","Cumbia","Tango","Bolero","Ranchera","Mariachi","Norteño",
        "Tejano","Grupera","Duranguense","Corridos","Huapango","Son Cubano","Chicano Rap","Reggaeton Pop","Samba","Bossa Nova",
        "Forró","Axé","Pagode","MPB","Fado","Flamenco","Sevillanas","Rumba","Bollywood Music","Filmi Pop",
        "Qawwali","Bhangra","Ghazal","Hindustani Classical","Carnatic Classical","Indian Folk","Indo-Jazz","Raga Rock","Psytrance","Goa Trance",
        "Eurodance","Eurobeat","Italo Disco","Hi-NRG","Freestyle (Latin)","Tech House","Deep House","Progressive House","Acid House","Electro House",
        "Big Room","Future House","Tropical House","Minimal Techno","Detroit Techno","Berlin School","Ambient Techno","Hardstyle","Jumpstyle","Gabber",
        "Happy Hardcore","UK Hardcore","Frenchcore","J-core","Speedcore","Breakbeat","Big Beat","Jungle","Liquid Funk","Neurofunk",
        "IDM","Glitch","Chiptune","8-Bit Music","Bitpop","Vaporwave","Mallsoft","Simpsonwave","Future Funk","Synthwave",
        "Retrowave","Darkwave","Coldwave","Minimal Wave","Dream Pop","Chillwave","Hypnagogic Pop","Lo-fi Pop","Bedroom Pop","Hyperpop",
        "Bubblegum Pop","Teen Pop","Dance Pop","Electropop","K-pop","J-pop","C-pop","T-pop","Mandopop","Cantopop",
        "Enka","Kayōkyoku","City Pop","Visual Kei","Anison","Vocaloid","Doujin Music","J-rock","Shibuya-kei","Shibuya Pop",
        "Indie Folk","Neo-Folk","Anti-Folk","Americana","Bluegrass","Old-Time","Appalachian Folk","Celtic Folk","Irish Folk","Scottish Folk",
        "Nordic Folk","Medieval Folk","Renaissance Music","Baroque Music","Romantic Era Music","Impressionist Classical","Minimalist Classical","Contemporary Classical","Avant-Garde Classical","Modernism",
        "Neoclassical","Symphonic Poem","Film Score","Soundtrack","Video Game Music","Chiptune Soundtrack","OST Remix","Experimental Music","Noise","Drone",
        "Dark Ambient","Space Ambient","Psybient","New Age","Meditation Music","Healing Music","Chillout","Lounge","Downtempo","Trip Hop",
        "Acid Jazz","Nu Jazz","Smooth Jazz","Jazz Fusion","Cool Jazz","Bebop","Hard Bop","Swing","Big Band","Ragtime",
        "Dixieland","Free Jazz","Gypsy Jazz","Latin Jazz","Third Stream","Avant-Garde Jazz","Post-Bop","Soul Jazz","Jazz-Funk","Jazz Rock",
        "Motown","Philly Soul","Northern Soul","Neo-Soul","Contemporary R&B","Quiet Storm","Alternative R&B","PBR&B","Funk Rock","Psychedelic Soul",
        "G-Funk","Electro-Funk","Boogie","Funk Metal","Disco Funk","Acid Funk","Future Soul","Trap Soul","Dancehall Fusion","Pop Rap",
        "Industrial","EBM","Aggrotech","Dark Electro","Futurepop","Synthpunk","Cyberpunk Music","Witch House","Hauntology","Dark Cabaret",
        "Steampunk Music","Medieval Metal","Folk Punk","Celtic Punk","Gypsy Punk","Garage Rock","Post-Punk","Goth Rock","Deathrock","Darkwave Rock",
        "Emo","Screamo","Pop Punk","Skate Punk","Hardcore Punk","Crust Punk","Anarcho-Punk","Straight Edge","Oi!","Street Punk",
        "Noise Rock","Sludge Rock","Stoner Rock","Southern Rock","Swamp Rock","Country Rock","Alt-Country","Outlaw Country","Red Dirt","Bakersfield Sound",
        "Honky Tonk","Blue-Eyed Soul","Sunshine Pop","Baroque Pop","Art Pop","Chamber Pop","Indie Electronica","Electroclash","Dance-Punk","Disco Polo"
    ]

    gaming = [
        "Action","Adventure","Role-Playing (RPG)","Shooter","Fighting","Platformer","Puzzle","Strategy","Simulation","Sports",
        "Racing","Survival","Sandbox","Horror","Stealth","Rhythm","MMORPG","MOBA","Battle Royale","Roguelike",
        "Roguelite","Metroidvania","Idle/Incremental","Card Game","Board Game","Trivia/Quiz","Party Game","Hack and Slash","Beat 'em Up","Tower Defense",
        "Tactical RPG","JRPG","Western RPG","Action RPG","Turn-Based Strategy","Real-Time Strategy (RTS)","Grand Strategy","City Builder","Colony Sim","Life Simulation",
        "Dating Sim","Farming Sim","Flight Sim","Driving Sim","Tycoon/Business Sim","Survival Horror","Narrative/Visual Novel","Interactive Movie","Text Adventure","Bullet Hell",
        "Shoot 'em Up (Shmup)","Run and Gun","Open World","Sandbox RPG","Walking Simulator","Point-and-Click Adventure","Detective/Mystery","Escape Room","Art Game","Educational",
        "Serious Game","Fitness Game","AR Game","VR Game","Experimental","Immersive Sim","God Game","Physics Puzzle","Logic Puzzle","Word Game",
        "Math Game","Trivia RPG","Cinematic Platformer","4X Strategy","Auto Battler","Gacha","Soulslike","Monster Tamer","Creature Collector","Rhythm RPG",
        "Music Maker","Arena Shooter","Tactical Shooter","Hero Shooter","Extraction Shooter","Light Gun Shooter","On-Rails Shooter","Vehicular Combat","Naval Combat","Space Combat",
        "Kaiju/Brawler","Deckbuilder Roguelike","Social Deduction","Asymmetric Multiplayer","Text-Based RPG","Idle Clicker RPG","Alternate Reality Game (ARG)","Experimental Narrative","Platform Fighter","Arena Fighter",
        "2D Fighter","3D Fighter","Tag-Team Fighter","Weapon Fighter","Rhythm Fighting","Dance Game","Instrument Sim","Singing Game","Drumming Game","DJ Sim",
        "Typing Game","Trivia Party Game","Charades Game","Drawing Game","Murder Mystery Party","Trivia Show","Cooking Sim","Bartending Sim","Hospital Sim","Theme Park Sim",
        "Zoo Sim","Prison Sim","School Sim","Sports Manager","Soccer/Football","Basketball","Baseball","Tennis","Golf","Cricket",
        "Rugby","American Football","Ice Hockey","Lacrosse","Bowling","Wrestling","Boxing","MMA Fighting","Skateboarding","Snowboarding",
        "Surfing","BMX","Track and Field","Esports Manager","Kart Racer","Arcade Racer","Simulation Racer","Drag Racing","Rally Racing","Drifting",
        "Bike Racing","Hover Racing","Futuristic Racing","Combat Racing","Space Racing","Endurance Racing","Text-Based Racing","2D Platformer","3D Platformer","Puzzle Platformer",
        "Physics Platformer","Cinematic Platformer","Endless Runner","Isometric Platformer","Speedrunning Platformer","Competitive Platformer","Steampunk Adventure","Cyberpunk RPG","Fantasy RPG","Sci-Fi RPG",
        "Post-Apocalyptic RPG","Urban RPG","Historical RPG","Dark Fantasy RPG","Light Fantasy RPG","Comedy RPG","Parody RPG","Monster-Hunting RPG","Time-Travel RPG","Open-World RPG",
        "Dungeon Crawler","Grid-Based Dungeon RPG","Action Dungeon Crawler","Turn-Based Dungeon RPG","Puzzle Dungeon RPG","Shooter RPG","Survival RPG","Text RPG","Tabletop RPG","LARP-Inspired RPG",
        "Stealth RPG","Detective RPG","Investigation Adventure","Courtroom Sim","Mystery Puzzle","Psychological Horror","Cosmic Horror","Body Horror","Slasher Horror","Monster Horror",
        "Zombie Survival","Vampire Horror","Werewolf Horror","Lovecraftian Horror","Ghost Horror","Alien Horror","Survival Crafting","Base Builder Survival","Multiplayer Survival","One-Life Survival",
        "Hardcore Survival","Casual Survival","Narrative Survival","Comic Book Adventure","Anime Fighter","Mecha RPG","Kaiju Strategy","Space 4X","Historical 4X","Fantasy 4X",
        "Sci-Fi 4X","Economy Sim","Political Sim","Diplomacy Sim","War Sim","Naval Sim","Submarine Sim","Train Sim","Bus Sim","Truck Sim",
        "Taxi Sim","Ambulance Sim","Firefighter Sim","Police Sim","Military Sim","Hunting Sim","Fishing Sim","Mining Sim","Crafting Sim","Space Exploration Sim",
        "Colonization Sim","Terraforming Sim","Asteroid Mining Sim","Alien Diplomacy Sim","Historical Adventure","Historical Strategy","Historical Simulation","Mythology Adventure","Mythology RPG","Mythology Strategy",
        "Religious Sim","Philosophy Game","Satirical Game","Parody Game","Mashup Genre","Music Puzzle","Music Platformer","Music Shooter","Music Narrative","VR Shooter",
        "VR Puzzle","VR Horror","VR Rhythm","VR Exploration","VR RPG","VR Social","VR Simulation","VR Sports","AR Shooter","AR Puzzle",
        "AR Adventure","AR Horror","AR Fitness","AR Narrative","Pet Sim","Virtual Life","Virtual Pet RPG","Creature Breeding","Monster Arena","Kaiju Sim",
        "AI Dungeon","Procedural Narrative","Generative Music Game","Generative Art Game","Sandbox Physics","Sandbox Construction","Sandbox Destruction","Sandbox Exploration","Sandbox Social","Sandbox RPG Hybrid",
        "MOBA Shooter Hybrid","MOBA RPG Hybrid","MOBA Strategy Hybrid","Tactical MOBA","Casual MOBA","Hardcore MOBA","Mobile MOBA","Browser MOBA","Retro Arcade","Pixel Art RPG",
        "Pixel Art Platformer","Pixel Art Shooter","Voxel Sandbox","Voxel Adventure","Voxel Shooter","Low-Poly Adventure","Low-Poly Horror","Low-Poly RPG","Experimental VR","Experimental Puzzle",
        "Experimental Strategy","Uncategorized Hybrid","Esoteric Game"
    ]

    tech = [
        "Computers","Laptops","Desktops","Servers","Mainframes","Supercomputers","Workstations","Quantum Computers","Edge Devices","IoT Devices",
        "Smartphones","Tablets","Smartwatches","Wearables","AR Glasses","VR Headsets","Mixed Reality Devices","Smart TVs","Game Consoles","Handheld Consoles",
        "Operating Systems","Windows","macOS","Linux","Unix","Android","iOS","ChromeOS","BSD","Haiku OS",
        "Programming","Web Development","Frontend Development","Backend Development","Full Stack Development","Mobile Development","Game Development","Embedded Systems","Systems Programming","Low-Level Programming",
        "Artificial Intelligence","Machine Learning","Deep Learning","Neural Networks","Reinforcement Learning","Generative AI","Natural Language Processing","Computer Vision","Speech Recognition","Recommendation Systems",
        "Data Science","Data Mining","Data Engineering","Big Data","Data Visualization","Data Analytics","Business Intelligence","ETL","Data Warehousing","Database Management",
        "Cloud Computing","Public Cloud","Private Cloud","Hybrid Cloud","Multi-Cloud","Cloud Storage","Cloud Hosting","Serverless Computing","Containerization","Virtualization",
        "Cybersecurity","Encryption","Firewalls","Antivirus","Intrusion Detection","Zero Trust","Penetration Testing","Red Teaming","Blue Teaming","Bug Bounty",
        "Networking","LAN","WAN","VPN","SD-WAN","5G","6G","Wi-Fi","Ethernet","Bluetooth",
        "Blockchain","Cryptocurrency","Bitcoin","Ethereum","NFTs","Decentralized Finance","Smart Contracts","DAOs","Tokenomics","Mining",
        "Robotics","Industrial Robots","Humanoid Robots","Service Robots","Drone Technology","Autonomous Vehicles","Swarm Robotics","Soft Robotics","Medical Robotics","Military Robotics",
        "3D Printing","Additive Manufacturing","FDM Printing","SLA Printing","SLS Printing","Metal Printing","Bioprinting","Resin Printing","Food Printing","Construction Printing",
        "Biotech","Genomics","CRISPR","Synthetic Biology","Bioinformatics","Proteomics","Pharmacogenomics","Stem Cell Tech","Bioprint Organs","Wearable Biotech",
        "Nanotech","Nanomaterials","Nanoelectronics","Nanomedicine","Molecular Machines","Quantum Dots","Nanocoatings","Nanorobotics","Carbon Nanotubes","Graphene Applications",
        "Quantum Tech","Quantum Algorithms","Quantum Cryptography","Quantum Sensors","Quantum Materials","Quantum Communication","Topological Qubits","Photonic Qubits","Quantum Annealing","Post-Quantum Cryptography",
        "Augmented Reality","Virtual Reality","Mixed Reality","XR","Spatial Computing","Immersive Media","360 Video","Virtual Worlds","Haptics","Brain-Computer Interface",
        "Energy Tech","Solar Power","Wind Power","Geothermal","Hydropower","Nuclear Fusion","Nuclear Fission","Battery Tech","Supercapacitors","Hydrogen Fuel Cells","Smart Grids",
        "Green Tech","Carbon Capture","Smart Agriculture","Precision Farming","Vertical Farming","Hydroponics","Aquaponics","Sustainable Materials","Eco-Friendly Manufacturing","Circular Economy",
        "Transportation Tech","Electric Vehicles","Hybrid Vehicles","Self-Driving Cars","Hyperloop","eVTOL Aircraft","Flying Cars","High-Speed Rail","Autonomous Ships","Smart Traffic Systems",
        "Space Tech","Satellites","Rocketry","Space Stations","Space Telescopes","Space Mining","Space Colonization","Reusable Rockets","Astrobiology Instruments","Interstellar Probes",
        "Healthcare Tech","Telemedicine","Wearable Health Tech","Digital Therapeutics","AI Diagnostics","Medical Imaging","Surgical Robots","Personalized Medicine","Electronic Health Records","Health Apps",
        "Fintech","Digital Payments","Mobile Banking","Online Lending","Crowdfunding Platforms","Insurtech","Robo-Advisors","Stock Trading Apps","Cryptocurrency Exchanges","Neobanks",
        "Edtech","Learning Management Systems","MOOCs","E-Learning","Gamified Learning","AI Tutors","Virtual Classrooms","Digital Whiteboards","Language Learning Apps","Skill Platforms",
        "Mediatech","Streaming Services","OTT Platforms","Content Delivery Networks","Podcast Platforms","Digital Publishing","Social Media Apps","Video Platforms","Music Platforms","Gaming Platforms",
        "Martech","SEO Tools","Content Management Systems","Ad Tech","CRM Systems","Marketing Automation","Email Marketing Platforms","Social Media Analytics","Customer Data Platforms","Influencer Platforms",
        "Proptech","Smart Homes","IoT Appliances","Building Automation","Digital Twins","Smart Cities","Property Platforms","3D Home Tours","Online Rentals","Real Estate AI",
        "Agritech","Drone Farming","Crop Monitoring","Soil Sensors","Livestock Monitoring","Smart Irrigation","Farming Robots","Automated Greenhouses","Agricultural Genomics","Agri-Drones",
        "Wearable Tech","Fitness Trackers","Smart Rings","Health Patches","Smart Clothing","Exoskeletons","Sleep Trackers","Hearing Aids","Smart Jewelry","Implantables",
        "Hardware","CPUs","GPUs","TPUs","RAM","ROM","SSDs","HDDs","Motherboards","Power Supplies","Cooling Systems",
        "Software","Productivity Apps","Office Suites","Design Software","CAD Tools","Photo Editing Software","Video Editing Software","Music Production Software","IDE","Version Control Systems",
        "Gaming Tech","Game Engines","Unity","Unreal Engine","CryEngine","Godot","Game Physics Engines","Cloud Gaming","VR Games","AR Games","Esports Tech",
        "Manufacturing Tech","Robotic Arms","CNC Machines","Laser Cutting","Smart Factories","Automation Systems","Supply Chain Tech","Predictive Maintenance","Digital Twins","Industrial IoT",
        "Communication Tech","Email","Messaging Apps","Video Conferencing","Collaboration Tools","VoIP","5G Messaging","Satellite Phones","Walkie Talkies","Fax","Pager",
        "Military Tech","Radar","Sonar","Missile Defense","Cyber Warfare","Drone Swarms","Exosuits","Directed Energy Weapons","Hypersonic Missiles","Stealth Tech","Electronic Warfare",
        "Entertainment Tech","3D Cinema","VR Films","AR Concerts","Interactive TV","Holograms","Projection Mapping","Immersive Theater","Digital Art Installations","Theme Park Tech","Interactive Exhibits",
        "Security Tech","Biometric Authentication","Facial Recognition","Fingerprint Scanners","Retina Scanners","Voice Recognition","Behavioral Biometrics","Smart Locks","Home Security Systems","Surveillance Cameras"
    ]

    science = [
        "Physics","Chemistry","Biology","Astronomy","Geology","Meteorology","Oceanography","Paleontology","Ecology","Botany",
        "Zoology","Microbiology","Genetics","Molecular Biology","Cell Biology","Evolutionary Biology","Biochemistry","Biophysics","Neuroscience","Immunology",
        "Anatomy","Physiology","Pathology","Pharmacology","Toxicology","Virology","Bacteriology","Mycology","Parasitology","Entomology",
        "Herpetology","Ornithology","Ichthyology","Mammalogy","Primatology","Marine Biology","Astrobiology","Biotechnology","Synthetic Biology","Systems Biology",
        "Bioinformatics","Biostatistics","Computational Biology","Structural Biology","Developmental Biology","Comparative Anatomy","Human Biology","Plant Physiology","Agricultural Science","Forestry",
        "Soil Science","Hydrology","Glaciology","Climatology","Atmospheric Science","Seismology","Volcanology","Speleology","Geomorphology","Mineralogy",
        "Petrology","Stratigraphy","Sedimentology","Paleoclimatology","Geochemistry","Geophysics","Planetary Science","Exoplanet Science","Cosmology","Astrophysics",
        "Stellar Astronomy","Galactic Astronomy","Radio Astronomy","Optical Astronomy","Infrared Astronomy","Ultraviolet Astronomy","X-Ray Astronomy","Gamma-Ray Astronomy","Space Science","Aerospace Science",
        "Mathematics","Arithmetic","Algebra","Geometry","Trigonometry","Calculus","Number Theory","Topology","Set Theory","Logic",
        "Statistics","Probability","Game Theory","Graph Theory","Combinatorics","Dynamical Systems","Chaos Theory","Fractals","Mathematical Physics","Mathematical Biology",
        "Theoretical Physics","Experimental Physics","Classical Mechanics","Quantum Mechanics","Relativity","Thermodynamics","Electromagnetism","Optics","Acoustics","Nuclear Physics",
        "Particle Physics","Plasma Physics","Condensed Matter Physics","Solid State Physics","Materials Science","Nanoscience","Surface Science","Quantum Information Science","Quantum Field Theory","Quantum Computing",
        "Analytical Chemistry","Organic Chemistry","Inorganic Chemistry","Physical Chemistry","Theoretical Chemistry","Polymer Chemistry","Biochemistry","Medicinal Chemistry","Green Chemistry","Materials Chemistry",
        "Environmental Chemistry","Geochemistry","Electrochemistry","Photochemistry","Radiochemistry","Supramolecular Chemistry","Computational Chemistry","Crystallography","Astrochemistry","Petrochemistry",
        "Psychology","Cognitive Psychology","Behavioral Psychology","Developmental Psychology","Social Psychology","Personality Psychology","Clinical Psychology","Neuropsychology","Forensic Psychology","Educational Psychology",
        "Anthropology","Cultural Anthropology","Biological Anthropology","Linguistic Anthropology","Archaeology","Ethnography","Ethnology","Paleoanthropology","Medical Anthropology","Primatology",
        "Sociology","Criminology","Demography","Political Science","Economics","Human Geography","Urban Studies","Rural Studies","International Relations","Public Policy",
        "Linguistics","Phonetics","Phonology","Morphology","Syntax","Semantics","Pragmatics","Sociolinguistics","Psycholinguistics","Computational Linguistics",
        "Education Science","Communication Science","Library Science","Information Science","Archival Science","Media Studies","Cultural Studies","Gender Studies","Queer Studies","Ethnic Studies",
        "Philosophy of Science","Logic and Philosophy","Epistemology","Metaphysics","Ethics","Aesthetics","Ontology","Phenomenology","Hermeneutics","Critical Theory",
        "Engineering","Mechanical Engineering","Electrical Engineering","Civil Engineering","Chemical Engineering","Computer Engineering","Aerospace Engineering","Biomedical Engineering","Nuclear Engineering","Environmental Engineering",
        "Industrial Engineering","Systems Engineering","Robotics Engineering","Mechatronics","Materials Engineering","Structural Engineering","Mining Engineering","Ocean Engineering","Petroleum Engineering","Automotive Engineering",
        "Agricultural Engineering","Food Science","Nutrition Science","Dietetics","Sports Science","Kinesiology","Biomechanics","Ergonomics","Exercise Physiology","Health Science",
        "Medical Science","Nursing Science","Dentistry","Pharmacy","Public Health","Epidemiology","Gerontology","Rehabilitation Science","Occupational Therapy","Speech-Language Pathology",
        "Computer Science","Algorithms","Data Structures","Programming Languages","Artificial Intelligence","Machine Learning","Computer Vision","Natural Language Processing","Software Engineering","Human-Computer Interaction",
        "Cybersecurity","Cryptography","Information Theory","Network Science","Cloud Computing","Distributed Systems","Database Systems","Operating Systems","Quantum Information","Bioinformatics Computing",
        "Earth Science","Environmental Science","Sustainability Science","Climate Science","Conservation Science","Wildlife Management","Ecosystem Science","Restoration Ecology","Environmental Engineering","Toxicology Ecology"
    ]

    health = [
        "Medicine","Nursing","Dentistry","Pharmacy","Public Health","Epidemiology","Pathology","Radiology","Oncology","Cardiology",
        "Neurology","Endocrinology","Gastroenterology","Hematology","Nephrology","Pulmonology","Rheumatology","Immunology","Dermatology","Ophthalmology",
        "Otolaryngology","Orthopedics","Urology","Obstetrics","Gynecology","Pediatrics","Geriatrics","Family Medicine","Emergency Medicine","Critical Care",
        "Anesthesiology","Surgery","General Surgery","Cardiac Surgery","Neurosurgery","Orthopedic Surgery","Plastic Surgery","Reconstructive Surgery","Transplant Surgery","Vascular Surgery",
        "Sports Medicine","Occupational Medicine","Aerospace Medicine","Military Medicine","Tropical Medicine","Travel Medicine","Integrative Medicine","Preventive Medicine","Lifestyle Medicine","Rehabilitation Medicine",
        "Physical Therapy","Occupational Therapy","Speech Therapy","Respiratory Therapy","Recreational Therapy","Music Therapy","Art Therapy","Dance Therapy","Drama Therapy","Cognitive Behavioral Therapy",
        "Psychology","Clinical Psychology","Counseling Psychology","Educational Psychology","Neuropsychology","Health Psychology","Sports Psychology","Forensic Psychology","Positive Psychology","Child Psychology",
        "Psychiatry","Addiction Psychiatry","Geriatric Psychiatry","Child and Adolescent Psychiatry","Forensic Psychiatry","Consultation-Liaison Psychiatry","Emergency Psychiatry","Community Psychiatry","Biological Psychiatry","Transcultural Psychiatry",
        "Nutrition","Dietetics","Sports Nutrition","Clinical Nutrition","Pediatric Nutrition","Geriatric Nutrition","Plant-Based Nutrition","Weight Management","Eating Disorder Treatment","Metabolic Health",
        "Fitness","Strength Training","Cardio Training","Yoga","Pilates","CrossFit","HIIT","Aerobics","Martial Arts Fitness","Calisthenics",
        "Wellness","Mindfulness","Meditation","Breathwork","Tai Chi","Qigong","Sound Healing","Energy Healing","Reiki","Chakra Balancing",
        "Alternative Medicine","Traditional Chinese Medicine","Ayurveda","Herbal Medicine","Homeopathy","Naturopathy","Chiropractic","Osteopathy","Acupuncture","Cupping Therapy",
        "Massage Therapy","Swedish Massage","Deep Tissue Massage","Sports Massage","Thai Massage","Shiatsu","Hot Stone Massage","Reflexology","Aromatherapy Massage","Prenatal Massage",
        "Public Health","Health Policy","Health Economics","Global Health","Community Health","Environmental Health","Occupational Health","Rural Health","Urban Health","Disaster Medicine",
        "Epidemiology","Infectious Disease Epidemiology","Chronic Disease Epidemiology","Nutritional Epidemiology","Genetic Epidemiology","Cancer Epidemiology","Molecular Epidemiology","Field Epidemiology","Surveillance Epidemiology","One Health",
        "Diagnostics","Medical Imaging","X-Ray","MRI","CT Scan","Ultrasound","PET Scan","Mammography","Endoscopy","Colonoscopy",
        "Laboratory Medicine","Hematology Lab","Microbiology Lab","Molecular Diagnostics","Clinical Chemistry","Cytology","Histopathology","Immunoassay","Blood Banking","Genetic Testing",
        "Health Informatics","Telemedicine","Electronic Health Records","Wearable Health Tech","Mobile Health Apps","AI in Medicine","Robotics in Surgery","Medical Data Analytics","Remote Monitoring","Virtual Care",
        "Emergency Response","First Aid","CPR","Paramedicine","Disaster Response","Search and Rescue Medicine","Combat Medicine","Triage Systems","Ambulance Services","Helicopter EMS",
        "Dental Specialties","Orthodontics","Endodontics","Periodontics","Prosthodontics","Oral Surgery","Oral Pathology","Pediatric Dentistry","Geriatric Dentistry","Cosmetic Dentistry",
        "Vision Care","Optometry","Ophthalmic Surgery","Cataract Surgery","Laser Eye Surgery","Glaucoma Treatment","Retina Specialist","Low Vision Therapy","Pediatric Optometry","Contact Lens Specialist",
        "Hearing Care","Audiology","Speech-Language Pathology","Cochlear Implants","Hearing Aids","Vestibular Therapy","Deaf Studies","Sign Language Therapy","Tinnitus Therapy","Hearing Conservation",
        "Rehabilitation","Stroke Rehabilitation","Spinal Cord Injury Rehab","Amputation Rehab","Cardiac Rehabilitation","Pulmonary Rehabilitation","Orthopedic Rehab","Neurological Rehab","Occupational Rehab","Addiction Rehab",
        "Maternal Health","Prenatal Care","Postnatal Care","Midwifery","Fertility Treatment","IVF","Neonatal Care","Lactation Consulting","Doula Support","Obstetric Ultrasound",
        "Child Health","Pediatric Oncology","Pediatric Cardiology","Pediatric Neurology","Pediatric Surgery","Adolescent Medicine","School Health","Child Development","Child Psychology","Child Nutrition",
        "Geriatric Health","Memory Care","Alzheimer’s Care","Dementia Care","Palliative Care","Hospice Care","Geriatric Nutrition","Fall Prevention","Mobility Support","Elder Counseling",
        "Addiction Care","Substance Use Treatment","Alcoholism Treatment","Smoking Cessation","Drug Rehabilitation","Opioid Treatment","Gambling Addiction Care","Behavioral Addictions","Support Groups","12-Step Programs",
        "Immunology","Allergy Care","Asthma Care","Autoimmune Disorders","Immunodeficiency Care","Vaccinology","Monoclonal Antibody Therapy","Immune System Research","Inflammatory Disorders","Transplant Immunology",
        "Occupational Safety","Industrial Hygiene","Workplace Ergonomics","Noise Control","Radiation Safety","Chemical Safety","Protective Equipment","Workplace Wellness","Work-Life Balance","Employee Assistance Programs"
    ]

    food = [
        "Pizza","Burger","Hot Dog","Sandwich","Taco","Burrito","Quesadilla","Nachos","Enchilada","Tamale",
        "Pasta","Spaghetti","Lasagna","Ravioli","Tortellini","Fettuccine Alfredo","Carbonara","Penne Arrabiata","Gnocchi","Risotto",
        "Sushi","Sashimi","Nigiri","Maki","Temaki","Udon","Ramen","Soba","Okonomiyaki","Takoyaki",
        "Curry","Chicken Curry","Lamb Curry","Fish Curry","Vegetable Curry","Thai Green Curry","Thai Red Curry","Massaman Curry","Vindaloo","Korma",
        "Fried Rice","Biryani","Pilaf","Paella","Jollof Rice","Nasi Goreng","Chow Mein","Lo Mein","Pad Thai","Pho",
        "Dumplings","Baozi","Gyoza","Momos","Pierogi","Khinkali","Samosa","Spring Roll","Egg Roll","Wonton",
        "Steak","Beef Wellington","Roast Beef","Prime Rib","T-Bone Steak","Ribeye Steak","Sirloin Steak","Filet Mignon","Carne Asada","Shawarma",
        "Kebab","Shish Kebab","Doner Kebab","Seekh Kebab","Satay","Yakitori","Souvlaki","Kofta","Adana Kebab","Tandoori Chicken",
        "BBQ Ribs","Pulled Pork","Brisket","Smoked Sausage","Buffalo Wings","Chicken Nuggets","Chicken Tenders","Fried Chicken","Roast Chicken","Duck Confit",
        "Lamb Chops","Roast Lamb","Gyro","Tagine","Moussaka","Stuffed Grape Leaves","Falafel","Hummus","Baba Ghanoush","Tabbouleh",
        "Soup","Tomato Soup","Chicken Noodle Soup","Miso Soup","French Onion Soup","Clam Chowder","Gazpacho","Minestrone","Lentil Soup","Pumpkin Soup",
        "Salad","Caesar Salad","Greek Salad","Caprese Salad","Nicoise Salad","Cobb Salad","Waldorf Salad","Potato Salad","Coleslaw","Fruit Salad",
        "Bread","Baguette","Ciabatta","Focaccia","Sourdough","Pita","Naan","Roti","Tortilla","Cornbread",
        "Pastries","Croissant","Pain au Chocolat","Danish Pastry","Cinnamon Roll","Baklava","Éclair","Macaron","Profiterole","Strudel",
        "Cakes","Chocolate Cake","Cheesecake","Carrot Cake","Red Velvet Cake","Black Forest Cake","Sponge Cake","Fruit Cake","Pavlova","Tiramisu",
        "Cookies","Chocolate Chip Cookie","Oatmeal Cookie","Peanut Butter Cookie","Shortbread","Sugar Cookie","Macaroon","Fortune Cookie","Biscotti","Gingerbread",
        "Ice Cream","Gelato","Sorbet","Frozen Yogurt","Sundae","Milkshake","Banana Split","Popsicle","Kulfi","Mochi Ice Cream",
        "Pies","Apple Pie","Pumpkin Pie","Pecan Pie","Cherry Pie","Blueberry Pie","Key Lime Pie","Custard Pie","Shepherd’s Pie","Pot Pie",
        "Seafood","Grilled Salmon","Lobster Tail","Crab Cakes","Shrimp Cocktail","Fried Calamari","Ceviche","Oysters Rockefeller","Clam Bake","Fish and Chips",
        "Cheese","Cheddar","Mozzarella","Brie","Camembert","Gorgonzola","Parmesan","Feta","Goat Cheese","Manchego","Blue Cheese",
        "Sausages","Bratwurst","Chorizo","Andouille","Italian Sausage","Breakfast Sausage","Kielbasa","Boudin","Weisswurst","Cumberland Sausage",
        "Breakfast","Pancakes","Waffles","French Toast","Omelette","Scrambled Eggs","Eggs Benedict","Avocado Toast","Hash Browns","Bagel with Cream Cheese",
        "Sandwiches","Club Sandwich","BLT","Reuben","Philly Cheesesteak","Croque Monsieur","Monte Cristo","Grilled Cheese","Panini","Muffuletta","Hoagie",
        "Street Food","Corn Dog","Churros","Crepes","Arepas","Empanadas","Tamales","Elote","Banh Mi","Kofta Wrap","Poffertjes",
        "Snacks","Popcorn","Potato Chips","Pretzels","Trail Mix","Granola Bars","Rice Cakes","Cheese Puffs","Beef Jerky","Fruit Snacks","Nuts",
        "Drinks","Coffee","Espresso","Latte","Cappuccino","Tea","Matcha","Bubble Tea","Smoothie","Hot Chocolate","Lemonade",
        "Alcoholic Drinks","Beer","Wine","Champagne","Whiskey","Vodka","Rum","Gin","Tequila","Cocktails",
        "Global Cuisines","Italian Cuisine","French Cuisine","Spanish Cuisine","Greek Cuisine","Turkish Cuisine","Lebanese Cuisine","Moroccan Cuisine","Indian Cuisine","Pakistani Cuisine",
        "Chinese Cuisine","Japanese Cuisine","Korean Cuisine","Thai Cuisine","Vietnamese Cuisine","Filipino Cuisine","Malaysian Cuisine","Indonesian Cuisine","Ethiopian Cuisine","Nigerian Cuisine",
        "Mexican Cuisine","Brazilian Cuisine","Argentinian Cuisine","Peruvian Cuisine","Chilean Cuisine","American Cuisine","Canadian Cuisine","Caribbean Cuisine","Cuban Cuisine","Jamaican Cuisine",
        "Holiday Foods","Roast Turkey","Stuffing","Pumpkin Pie","Gingerbread House","Yule Log","Latkes","Sufganiyot","Hot Cross Buns","Easter Eggs","Mooncakes",
        "Healthy Foods","Quinoa","Kale Salad","Avocado","Chia Pudding","Acai Bowl","Smoothie Bowl","Tofu Stir Fry","Lentil Stew","Veggie Burger","Vegan Curry",
        "Street Drinks","Ayran","Horchata","Agua Fresca","Sugarcane Juice","Lassi","Falooda","Kombucha","Kvass","Mate","Tereré"
    ]

    fashion = [
        "Haute Couture","Prêt-à-Porter","Streetwear","Casualwear","Formalwear","Businesswear","Athleisure","Loungewear","Resort Wear","Evening Wear",
        "Minimalist Fashion","Maximalist Fashion","Avant-Garde Fashion","Experimental Fashion","Conceptual Fashion","Futuristic Fashion","Cyberpunk Fashion","Steampunk Fashion","Dieselpunk Fashion","Solarpunk Fashion",
        "Bohemian Style","Hippie Style","Grunge","Punk","Goth","Emo","Scene","Indie Sleaze","Y2K Fashion","McBling",
        "Hip Hop Style","Skater Style","Surfer Style","Prep Style","Ivy League Style","Collegiate Fashion","Country Style","Western Wear","Cowboy Fashion","Rodeo Fashion",
        "Androgynous Fashion","Genderless Fashion","Unisex Fashion","Menswear","Womenswear","Childrenswear","Teen Fashion","Maternity Fashion","Plus Size Fashion","Petite Fashion",
        "Runway Fashion","Red Carpet Fashion","Celebrity Style","Luxury Fashion","Fast Fashion","Sustainable Fashion","Ethical Fashion","Slow Fashion","Upcycled Fashion","Vintage Fashion",
        "Retro Fashion","1950s Fashion","1960s Fashion","1970s Fashion","1980s Fashion","1990s Fashion","2000s Fashion","2010s Fashion","Historical Costumes","Period Fashion",
        "Medieval Clothing","Renaissance Clothing","Victorian Fashion","Edwardian Fashion","Art Deco Fashion","Flapper Style","Roaring Twenties Fashion","1940s Fashion","Military Fashion","Utility Fashion",
        "Workwear","Uniforms","Sportswear","Tennis Wear","Golf Wear","Ski Wear","Swimwear","Diving Suits","Yoga Wear","Dancewear",
        "Outerwear","Coats","Jackets","Parkas","Blazers","Trench Coats","Ponchos","Raincoats","Capes","Bomber Jackets",
        "Footwear","Sneakers","Loafers","Oxfords","Derby Shoes","High Heels","Stilettos","Sandals","Flip-Flops","Boots",
        "Ankle Boots","Chelsea Boots","Cowboy Boots","Combat Boots","Platform Shoes","Wedges","Espadrilles","Ballet Flats","Mules","Clogs",
        "Accessories","Handbags","Backpacks","Tote Bags","Wallets","Clutches","Belts","Scarves","Gloves","Hats",
        "Beanies","Berets","Caps","Fedoras","Panama Hats","Sun Hats","Visors","Cowboy Hats","Bowler Hats","Top Hats",
        "Jewelry","Necklaces","Earrings","Bracelets","Rings","Anklets","Brooches","Cufflinks","Body Chains","Chokers",
        "Sunglasses","Eyewear","Prescription Glasses","Aviator Sunglasses","Wayfarers","Round Frames","Cat-Eye Sunglasses","Oversized Sunglasses","Sport Sunglasses","Blue Light Glasses",
        "Traditional Clothing","Kimono","Yukata","Hanbok","Cheongsam","Sari","Salwar Kameez","Kurta","Dashiki","Boubou",
        "Kaftan","Abaya","Thobe","Dirndl","Lederhosen","Kilts","Poncho","Huipil","Guayabera","Sombrero",
        "Festival Fashion","Rave Wear","EDM Style","Burning Man Fashion","Coachella Style","Tribal Fusion","Boho Chic","Eclectic Layering","DIY Fashion","Costume Play (Cosplay)",
        "Cosplay Armor","Cosplay Props","Anime Cosplay","Manga Cosplay","Comic Con Outfits","Movie Replica Costumes","Video Game Cosplay","Stealth Cosplay","LARP Clothing","Fantasy Costumes",
        "High-Tech Fashion","Smart Clothing","Wearable Tech","LED Fashion","3D Printed Fashion","Augmented Reality Clothing","Sustainable Fabrics","Recycled Fabrics","Biodegradable Textiles","Vegan Leather",
        "Denim Fashion","Jeans","Denim Jackets","Denim Shorts","Denim Skirts","Denim Overalls","Distressed Denim","Patchwork Denim","Double Denim","Selvedge Denim",
        "Luxury Brands","Gucci","Prada","Chanel","Dior","Louis Vuitton","Hermès","Balenciaga","Versace","Valentino","Givenchy",
        "Streetwear Brands","Supreme","Off-White","Palace","Stüssy","BAPE","Fear of God","Kith","Anti Social Social Club","Undercover","Neighborhood",
        "Sportswear Brands","Nike","Adidas","Puma","Reebok","New Balance","Fila","Asics","Under Armour","Lululemon","Champion",
        "Fast Fashion Brands","Zara","H&M","Forever 21","Uniqlo","Topshop","Mango","Bershka","Shein","PrettyLittleThing","Fashion Nova",
        "Eco Fashion Brands","Patagonia","Stella McCartney","Reformation","Everlane","Allbirds","Veja","Eileen Fisher","People Tree","Thought Clothing","Organic Basics",
        "Makeup Trends","Natural Makeup","Glam Makeup","Bold Lips","Smokey Eyes","Glitter Makeup","No-Makeup Look","Avant-Garde Makeup","Festival Makeup","K-Beauty Makeup","J-Beauty Makeup",
        "Hairstyles","Pixie Cut","Bob Cut","Lob Cut","Shag Cut","Layers","Perm","Straight Hair","Curly Hair","Braids",
        "Cornrows","Box Braids","Twists","Dreadlocks","Afro","Fade Cut","Undercut","Pompadour","Mohawk","Mullet",
        "Nail Art","French Manicure","Gel Nails","Acrylic Nails","Dip Powder Nails","Chrome Nails","Matte Nails","Stiletto Nails","Coffin Nails","Almond Nails",
        "Fashion Subcultures","Mods","Rockers","Teddy Boys","Skinheads","New Romantics","Cyber Goths","Lolita Fashion","Decora","Visual Kei","Harajuku Style",
        "Modern Aesthetics","Cottagecore","Dark Academia","Light Academia","Fairycore","Goblincore","E-girl","E-boy","Soft Grunge","Pastel Goth","Normcore",
        "Workplace Fashion","Business Formal","Business Casual","Smart Casual","Creative Casual","Startup Casual","Power Dressing","Interview Outfits","Office Chic","Tech Wear","Corporate Fashion"
    ]

    lifestyle = [
        "Minimalist Lifestyle","Maximalist Lifestyle","Nomadic Lifestyle","Digital Nomad Lifestyle","Van Life","Tiny House Living","Off-Grid Living","Eco-Friendly Living","Zero Waste Lifestyle","Sustainable Lifestyle",
        "Frugal Living","Simple Living","Slow Living","Hygge Lifestyle","Lagom Lifestyle","Voluntary Simplicity","Decluttering Lifestyle","Essentialist Lifestyle","Mindful Living","Intentional Living",
        "Luxury Lifestyle","High Society Lifestyle","Jet-Set Lifestyle","Celebrity Lifestyle","Influencer Lifestyle","Materialist Lifestyle","Fashion-Forward Lifestyle","Status-Oriented Lifestyle","High-Tech Lifestyle","Smart Home Lifestyle",
        "Urban Lifestyle","Suburban Lifestyle","Rural Lifestyle","Small-Town Lifestyle","Commute-Heavy Lifestyle","City-Dweller Lifestyle","Downtown Lifestyle","Cosmopolitan Lifestyle","Metropolitan Lifestyle","Global Citizen Lifestyle",
        "Workaholic Lifestyle","Corporate Lifestyle","Entrepreneurial Lifestyle","Startup Hustle Lifestyle","Freelancer Lifestyle","Gig Economy Lifestyle","Remote Work Lifestyle","Hybrid Work Lifestyle","Co-Working Lifestyle","Side Hustle Lifestyle",
        "Athletic Lifestyle","Active Lifestyle","Fitness Lifestyle","Bodybuilding Lifestyle","CrossFit Lifestyle","Yoga Lifestyle","Pilates Lifestyle","Martial Arts Lifestyle","Endurance Athlete Lifestyle","Outdoor Adventure Lifestyle",
        "Healthy Lifestyle","Balanced Lifestyle","Holistic Lifestyle","Preventive Health Lifestyle","Wellness Lifestyle","Detox Lifestyle","Biohacker Lifestyle","Longevity Lifestyle","Plant-Based Lifestyle","Vegan Lifestyle",
        "Vegetarian Lifestyle","Pescatarian Lifestyle","Flexitarian Lifestyle","Raw Food Lifestyle","Organic Food Lifestyle","Farm-to-Table Lifestyle","Clean Eating Lifestyle","Keto Lifestyle","Paleo Lifestyle","Mediterranean Diet Lifestyle",
        "Cultural Lifestyle","Traditional Lifestyle","Indigenous Lifestyle","Tribal Lifestyle","Nomadic Pastoral Lifestyle","Agrarian Lifestyle","Monastic Lifestyle","Pilgrimage Lifestyle","Religious Lifestyle","Spiritual Lifestyle",
        "Christian Lifestyle","Muslim Lifestyle","Jewish Lifestyle","Buddhist Lifestyle","Hindu Lifestyle","Pagan Lifestyle","New Age Lifestyle","Atheist Lifestyle","Agnostic Lifestyle","Secular Humanist Lifestyle",
        "Parenting Lifestyle","Family-Oriented Lifestyle","Single Lifestyle","Bachelor Lifestyle","Bachelorette Lifestyle","Couple Lifestyle","Childfree Lifestyle","Empty Nester Lifestyle","Multigenerational Living","Community Living",
        "Student Lifestyle","Academic Lifestyle","Scholar Lifestyle","Fraternity/Sorority Lifestyle","Campus Lifestyle","Boarding School Lifestyle","Study Abroad Lifestyle","Researcher Lifestyle","Grad School Lifestyle","Dropout Lifestyle",
        "Artistic Lifestyle","Creative Lifestyle","Bohemian Lifestyle","Hippie Lifestyle","Beatnik Lifestyle","Indie Lifestyle","Maker Lifestyle","DIY Lifestyle","Crafting Lifestyle","Festival Lifestyle",
        "Music-Focused Lifestyle","Rock-and-Roll Lifestyle","Jazz Lifestyle","Punk Lifestyle","Metalhead Lifestyle","Raver Lifestyle","Club Lifestyle","EDM Lifestyle","K-Pop Fan Lifestyle","Fan Community Lifestyle",
        "Fashion Lifestyle","Streetwear Lifestyle","Luxury Brand Lifestyle","Designer Brand Lifestyle","Thrifting Lifestyle","Second-Hand Lifestyle","Sustainable Fashion Lifestyle","Fast Fashion Lifestyle","DIY Fashion Lifestyle","Costume Lifestyle",
        "Tech Lifestyle","Gamer Lifestyle","Esports Lifestyle","Streaming Lifestyle","Crypto Lifestyle","Blockchain Lifestyle","AI Lifestyle","Maker Tech Lifestyle","Hacker Lifestyle","Coder Lifestyle",
        "Travel Lifestyle","Backpacker Lifestyle","Adventure Travel Lifestyle","Budget Travel Lifestyle","Luxury Travel Lifestyle","Gap Year Lifestyle","Expat Lifestyle","Couchsurfing Lifestyle","Road Trip Lifestyle","Cruise Ship Lifestyle",
        "Pet Owner Lifestyle","Dog Owner Lifestyle","Cat Owner Lifestyle","Exotic Pet Lifestyle","Equestrian Lifestyle","Aquarium Keeper Lifestyle","Bird Owner Lifestyle","Reptile Keeper Lifestyle","Pet-Free Lifestyle","Animal Rescue Lifestyle",
        "Environmental Lifestyle","Climate Activist Lifestyle","Conservationist Lifestyle","Nature Enthusiast Lifestyle","Outdoor Lifestyle","Hiking Lifestyle","Camping Lifestyle","Survivalist Lifestyle","Prepper Lifestyle","Wildlife Lover Lifestyle",
        "Political Lifestyle","Activist Lifestyle","Protest Lifestyle","Revolutionary Lifestyle","Anarchist Lifestyle","Communitarian Lifestyle","Democratic Lifestyle","Conservative Lifestyle","Progressive Lifestyle","Centrist Lifestyle",
        "Philosophical Lifestyle","Stoic Lifestyle","Existentialist Lifestyle","Absurdist Lifestyle","Hedonist Lifestyle","Epicurean Lifestyle","Ascetic Lifestyle","Utilitarian Lifestyle","Optimist Lifestyle","Pessimist Lifestyle",
        "Learning Lifestyle","Bookworm Lifestyle","Lifelong Learner Lifestyle","Polymath Lifestyle","Self-Taught Lifestyle","Autodidact Lifestyle","Online Learning Lifestyle","Language Learning Lifestyle","STEM Lifestyle","Humanities Lifestyle",
        "Social Lifestyle","Extroverted Lifestyle","Introverted Lifestyle","Ambivert Lifestyle","Networking Lifestyle","Party Lifestyle","Festival-Goer Lifestyle","Nightlife Lifestyle","Pub Crawl Lifestyle","Cafe Culture Lifestyle",
        "Home Lifestyle","Domestic Lifestyle","Homemaker Lifestyle","DIY Home Lifestyle","Interior Design Lifestyle","Homebody Lifestyle","Gardening Lifestyle","Cooking Lifestyle","Baking Lifestyle","Hosting Lifestyle",
        "Luxury Leisure Lifestyle","Collector Lifestyle","Art Collector Lifestyle","Wine Collector Lifestyle","Car Collector Lifestyle","Sneakerhead Lifestyle","Watch Collector Lifestyle","Toy Collector Lifestyle","Pop Culture Collector Lifestyle","Antique Collector Lifestyle",
        "Adventurous Lifestyle","Extreme Sports Lifestyle","Climbing Lifestyle","Diving Lifestyle","Skydiving Lifestyle","Paragliding Lifestyle","Mountaineering Lifestyle","Exploration Lifestyle","Polar Expedition Lifestyle","Desert Travel Lifestyle"
    ]

    nature = [
        "Forest","Rainforest","Tropical Forest","Temperate Forest","Boreal Forest","Mangrove Forest","Savanna","Grassland","Prairie","Steppe",
        "Desert","Hot Desert","Cold Desert","Semi-Arid Desert","Oasis","Dune Field","Salt Flat","Badlands","Plateau Desert","Rocky Desert",
        "Mountain","Volcano","Stratovolcano","Shield Volcano","Cinder Cone","Caldera","Mountain Range","Himalayas","Andes","Alps",
        "Hill","Valley","Canyon","Gorge","Plateau","Mesa","Butte","Cliff","Escarpment","Karst Landscape",
        "River","Stream","Creek","Brook","Waterfall","Rapids","Delta","Estuary","Lagoon","Bay",
        "Ocean","Sea","Coral Reef","Atoll","Archipelago","Island","Peninsula","Cape","Fjord","Tidepool",
        "Lake","Pond","Reservoir","Glacial Lake","Crater Lake","Salt Lake","Wetlands","Marsh","Swamp","Bog",
        "Tundra","Taiga","Permafrost Region","Polar Ice Cap","Glacier","Iceberg","Ice Shelf","Snowfield","Frozen Lake","Polar Desert",
        "Weather","Rain","Snow","Hail","Sleet","Fog","Mist","Cloud","Thunderstorm","Lightning","Rainbow",
        "Hurricane","Typhoon","Cyclone","Tornado","Waterspout","Blizzard","Dust Storm","Sandstorm","Heatwave","Cold Wave",
        "Geology","Rock","Mineral","Crystal","Gemstone","Ore","Soil","Clay","Sand","Gravel",
        "Flora","Tree","Shrub","Herb","Grass","Fern","Moss","Lichen","Flower","Cactus",
        "Fauna","Mammal","Bird","Fish","Reptile","Amphibian","Insect","Arachnid","Crustacean","Mollusk",
        "Mammals","Lion","Tiger","Elephant","Giraffe","Zebra","Bear","Wolf","Fox","Deer",
        "Marine Mammals","Dolphin","Whale","Seal","Sea Lion","Walrus","Manatee","Otter","Polar Bear","Narwhal",
        "Birds","Eagle","Hawk","Falcon","Owl","Penguin","Parrot","Sparrow","Crow","Swan","Peacock",
        "Reptiles","Crocodile","Alligator","Lizard","Snake","Turtle","Tortoise","Chameleon","Gecko","Iguana",
        "Amphibians","Frog","Toad","Newt","Salamander","Caecilian","Axolotl","Tree Frog","Poison Dart Frog","Hellbender","Mudpuppy",
        "Fish","Shark","Salmon","Tuna","Trout","Cod","Clownfish","Angelfish","Eel","Stingray",
        "Insects","Butterfly","Moth","Bee","Ant","Wasp","Beetle","Ladybug","Dragonfly","Grasshopper","Cricket",
        "Arachnids","Spider","Scorpion","Tick","Mite","Harvestman","Camel Spider","Trapdoor Spider","Tarantula","Orb Weaver",
        "Plants","Oak Tree","Maple Tree","Pine Tree","Birch Tree","Palm Tree","Baobab Tree","Willow Tree","Cedar Tree","Redwood Tree",
        "Flowers","Rose","Tulip","Sunflower","Orchid","Lily","Daffodil","Daisy","Lotus","Magnolia","Cherry Blossom",
        "Crops","Wheat","Rice","Corn","Barley","Oats","Soybeans","Potatoes","Tomatoes","Bananas","Apples",
        "Ecosystems","Coral Reef Ecosystem","Mangrove Ecosystem","Freshwater Ecosystem","Rainforest Ecosystem","Savanna Ecosystem","Desert Ecosystem","Tundra Ecosystem","Taiga Ecosystem","Wetland Ecosystem","Grassland Ecosystem",
        "Natural Phenomena","Aurora Borealis","Aurora Australis","Solar Eclipse","Lunar Eclipse","Meteor Shower","Volcanic Eruption","Earthquake","Tsunami","Geyser","Hot Spring",
        "Biomes","Tropical Rainforest","Temperate Rainforest","Temperate Grassland","Desert Biome","Alpine Biome","Taiga Biome","Tundra Biome","Freshwater Biome","Marine Biome","Savanna Biome",
        "Habitats","Cave Habitat","Coral Habitat","Tree Canopy","Forest Floor","Underground Burrow","Riverbank","Coastal Habitat","Open Ocean","Deep Sea","Intertidal Zone",
        "Endangered Species","Giant Panda","Snow Leopard","Blue Whale","Orangutan","Sea Turtle","Red Panda","Black Rhino","Tiger","Koala","African Penguin",
        "Natural Resources","Freshwater","Timber","Coal","Oil","Natural Gas","Uranium","Iron Ore","Copper","Gold","Diamonds",
        "Conservation Areas","National Park","Wildlife Reserve","Biosphere Reserve","Protected Wetland","Marine Protected Area","World Heritage Site","Nature Reserve","Game Reserve","Forest Preserve","Sanctuary"
    ]

    animals = [
        "Lion","Tiger","Leopard","Cheetah","Jaguar","Cougar","Snow Leopard","Clouded Leopard","Caracal","Lynx",
        "Wolf","Coyote","Jackal","Fox","Dingo","African Wild Dog","Hyena","Otter","Weasel","Badger",
        "Bear","Grizzly Bear","Polar Bear","Brown Bear","Black Bear","Panda","Red Panda","Sloth Bear","Sun Bear","Koala",
        "Elephant","African Elephant","Asian Elephant","Mammoth","Mastodon","Rhino","White Rhino","Black Rhino","Indian Rhino","Javan Rhino",
        "Hippo","Giraffe","Okapi","Zebra","Horse","Donkey","Mule","Camel","Bactrian Camel","Llama",
        "Alpaca","Vicuna","Antelope","Gazelle","Springbok","Impala","Kudu","Oryx","Eland","Saiga",
        "Bison","Buffalo","Yak","Water Buffalo","Musk Ox","Cow","Bull","Calf","Sheep","Goat",
        "Pig","Boar","Warthog","Tapir","Deer","Moose","Elk","Reindeer","Caribou","Fallow Deer",
        "Whale","Blue Whale","Humpback Whale","Sperm Whale","Beluga Whale","Narwhal","Orca","Dolphin","Porpoise","Manatee",
        "Seal","Sea Lion","Walrus","Penguin","Albatross","Seagull","Pelican","Cormorant","Flamingo","Heron",
        "Crane","Stork","Eagle","Hawk","Falcon","Owl","Vulture","Kite","Buzzard","Condor",
        "Parrot","Macaw","Cockatoo","Parakeet","Budgerigar","Lovebird","Toucan","Hornbill","Kingfisher","Woodpecker",
        "Crow","Raven","Magpie","Jay","Sparrow","Finch","Swallow","Robin","Blackbird","Starling",
        "Peacock","Turkey","Chicken","Rooster","Hen","Duck","Goose","Swan","Quail","Pheasant",
        "Dog","Domestic Cat","Horse","Cow","Sheep","Goat","Pig","Rabbit","Hamster","Guinea Pig",
        "Mouse","Rat","Gerbil","Chinchilla","Ferret","Hedgehog","Sugar Glider","Prairie Dog","Capybara","Agouti",
        "Kangaroo","Wallaby","Possum","Bandicoot","Numbat","Quokka","Tasmanian Devil","Wombat","Echidna","Platypus",
        "Crocodile","Alligator","Caiman","Gharial","Komodo Dragon","Monitor Lizard","Gecko","Chameleon","Iguana","Anole",
        "Snake","Python","Boa Constrictor","Anaconda","Cobra","Viper","Rattlesnake","Mamba","Coral Snake","Garter Snake",
        "Turtle","Tortoise","Terrapin","Sea Turtle","Leatherback Turtle","Box Turtle","Snapping Turtle","Painted Turtle","Galápagos Tortoise","Aldabra Tortoise",
        "Frog","Toad","Tree Frog","Poison Dart Frog","Bullfrog","Glass Frog","Axolotl","Newt","Salamander","Hellbender",
        "Shark","Great White Shark","Hammerhead Shark","Tiger Shark","Whale Shark","Mako Shark","Nurse Shark","Bull Shark","Goblin Shark","Basking Shark",
        "Ray","Stingray","Manta Ray","Electric Ray","Eagle Ray","Skate","Guitarfish","Sawfish","Butterfly Ray","Round Ray",
        "Fish","Salmon","Trout","Tuna","Cod","Haddock","Mackerel","Sardine","Anchovy","Clownfish",
        "Butterfly","Moth","Bee","Wasp","Ant","Termite","Dragonfly","Damselfly","Grasshopper","Cricket",
        "Beetle","Ladybug","Firefly","Stag Beetle","Dung Beetle","Weevil","Longhorn Beetle","Leaf Beetle","June Bug","Scarab",
        "Spider","Tarantula","Black Widow","Brown Recluse","Orb Weaver","Jumping Spider","Wolf Spider","Trapdoor Spider","Crab Spider","Camel Spider",
        "Scorpion","Tick","Mite","Horseshoe Crab","Lobster","Crab","Shrimp","Prawn","Crayfish","Krill",
        "Octopus","Squid","Cuttlefish","Nautilus","Jellyfish","Coral","Sea Anemone","Sea Urchin","Starfish","Sea Cucumber",
        "Invertebrate","Earthworm","Leech","Snail","Slug","Clam","Oyster","Mussel","Scallop","Barnacle",
        "Insect","Mosquito","Flea","Butterfly Fish","Angelfish","Seahorse","Pipefish","Mudskipper","Lionfish","Pufferfish"
    ]

    vehicles = [
        "Car","Truck","Van","Bus","Minibus","Taxi","Police Car","Ambulance","Fire Truck","Tow Truck",
        "SUV","Crossover","Pickup Truck","Jeep","ATV","UTV","Dune Buggy","Monster Truck","Campervan","Motorhome",
        "Sedan","Hatchback","Coupe","Convertible","Station Wagon","Limousine","Hot Rod","Muscle Car","Sports Car","Supercar",
        "Hypercar","Concept Car","Electric Car","Hybrid Car","Hydrogen Car","Solar Car","Autonomous Car","Race Car","Formula 1 Car","NASCAR Car",
        "Rally Car","Touring Car","Dragster","Kart","Go-Kart","Soapbox Car","Stock Car","IndyCar","Le Mans Prototype","Drift Car",
        "Motorcycle","Scooter","Moped","Dirt Bike","Cruiser Bike","Sport Bike","Touring Bike","Chopper","Trike","Electric Motorcycle",
        "Bicycle","Road Bike","Mountain Bike","BMX","Folding Bike","Recumbent Bike","Fat Bike","Cyclocross Bike","Track Bike","E-Bike",
        "Train","Steam Locomotive","Diesel Locomotive","Electric Locomotive","Maglev Train","Monorail","High-Speed Train","Bullet Train","Commuter Train","Freight Train",
        "Subway Train","Light Rail","Streetcar","Tram","Trolleybus","Cable Car","Funicular","Railcar","Handcar","Minecart",
        "Ship","Boat","Canoe","Kayak","Raft","Yacht","Sailboat","Catamaran","Ferry","Cruise Ship",
        "Cargo Ship","Container Ship","Tanker","Fishing Boat","Tugboat","Warship","Destroyer","Battleship","Aircraft Carrier","Submarine",
        "Hovercraft","Hydrofoil","Jet Ski","Gondola Boat","Dragon Boat","Banana Boat","Pedal Boat","Rowboat","Dhow","Clipper Ship",
        "Airplane","Jet Airliner","Propeller Plane","Glider","Ultralight Aircraft","Seaplane","Biplane","Fighter Jet","Bomber","Stealth Aircraft",
        "Cargo Plane","Military Transport Plane","Aerial Refueler","AWACS Plane","Bush Plane","Crop Duster","Stunt Plane","Supersonic Jet","Concorde","Private Jet",
        "Helicopter","Attack Helicopter","Rescue Helicopter","Transport Helicopter","News Helicopter","Police Helicopter","Chinook","Black Hawk","Apache","Commuter Helicopter",
        "Drone","Quadcopter","Hexacopter","Octocopter","Fixed-Wing Drone","Surveillance Drone","Delivery Drone","Racing Drone","Military Drone","Kamikaze Drone",
        "Spacecraft","Space Shuttle","Space Capsule","Crew Dragon","Soyuz","Orion Capsule","Starship","Satellite","Space Probe","Space Telescope",
        "Mars Rover","Lunar Rover","Space Station Module","Cargo Spacecraft","Space Tug","Lander","Reusable Rocket","Interplanetary Probe","Interstellar Probe","Asteroid Miner",
        "Rocket","V2 Rocket","Saturn V","Falcon 9","New Glenn","Electron Rocket","Delta IV Heavy","Ariane 5","Long March Rocket","H-II Rocket",
        "Future Vehicles","Flying Car","Hoverboard","Jetpack","Antigravity Vehicle","Hypersonic Plane","Maglev Pod","Hyperloop Pod","Teleport Pod","Exosuit",
        "Emergency Vehicles","Rescue Boat","Fire Helicopter","Rescue Plane","Coast Guard Ship","Mountain Rescue Vehicle","All-Terrain Ambulance","Hazmat Truck","Prison Transport Van","Armored Vehicle",
        "Agricultural Vehicles","Tractor","Combine Harvester","Plow Vehicle","Seeder Vehicle","Crop Sprayer","Cotton Picker","Logging Truck","Skidder","Forestry Forwarder",
        "Construction Vehicles","Bulldozer","Excavator","Backhoe","Dump Truck","Cement Mixer","Road Roller","Grader","Crane Truck","Pile Driver",
        "Mining Vehicles","Mining Truck","Bucket Wheel Excavator","Drill Rig","Underground Loader","Continuous Miner","Rock Truck","Mine Locomotive","Shuttle Car","Dragline Excavator","Hydraulic Shovel",
        "Military Vehicles","Tank","Light Tank","Main Battle Tank","Armored Personnel Carrier","Infantry Fighting Vehicle","Self-Propelled Gun","Mobile Missile Launcher","Half-Track","Armored Car",
        "Jeep Military","Humvee","MRAP","Patrol Boat","Amphibious Assault Vehicle","Hover Tank","Railgun Tank","Stealth Submarine","Stealth Bomber","Unmanned Ground Vehicle",
        "Animal Vehicles","Camel Caravan","Horse Carriage","Donkey Cart","Elephant Howdah","Dog Sled","Reindeer Sled","Yak Caravan","Ox Cart","Mule Pack Train","Llama Caravan",
        "Fantasy Vehicles","Chariot","War Chariot","Dragon Mount","Flying Broom","Magic Carpet","Mecha","Battle Mech","Skyship","Airship","Submersible Pod",
        "Sci-Fi Vehicles","Speeder Bike","Landspeeder","Starfighter","Star Destroyer","Tie Fighter","X-Wing","Millennium Falcon","Death Star","Battlestar","Cylon Raider"
    ]

    places_core = [
        "cities", "villages", "towns", "parks", "museums", "libraries",
        "schools", "universities", "hospitals", "temples", "churches",
        "mosques", "synagogues", "markets", "restaurants", "cafes",
        "theaters", "stadiums", "airports", "train stations", "castles",
        "palaces", "monuments", "landmarks", "national parks",
        "New York City","Los Angeles","Chicago","Miami","San Francisco","Las Vegas","Washington D.C.","Boston","Seattle","Houston",
        "London","Paris","Berlin","Rome","Madrid","Barcelona","Amsterdam","Vienna","Prague","Budapest",
        "Tokyo","Osaka","Kyoto","Seoul","Beijing","Shanghai","Hong Kong","Taipei","Bangkok","Singapore",
        "Sydney","Melbourne","Auckland","Wellington","Jakarta","Kuala Lumpur","Manila","Hanoi","Ho Chi Minh City","Phnom Penh",
        "Cairo","Alexandria","Casablanca","Marrakech","Nairobi","Cape Town","Johannesburg","Durban","Lagos","Abuja",
        "Mexico City","Guadalajara","Cancun","Havana","San Juan","Buenos Aires","Rio de Janeiro","São Paulo","Santiago","Lima",
        "Toronto","Vancouver","Montreal","Ottawa","Calgary","Edmonton","Quebec City","Winnipeg","Halifax","Victoria",
        "Moscow","St. Petersburg","Kazan","Novosibirsk","Sochi","Warsaw","Krakow","Tallinn","Riga","Vilnius",
        "Athens","Santorini","Mykonos","Istanbul","Antalya","Ankara","Dubrovnik","Split","Belgrade","Sofia",
        "Jerusalem","Tel Aviv","Dubai","Abu Dhabi","Doha","Kuwait City","Muscat","Riyadh","Jeddah","Mecca",
        "Delhi","Mumbai","Bangalore","Chennai","Hyderabad","Kolkata","Jaipur","Agra","Varanasi","Goa",
        "Kathmandu","Pokhara","Thimphu","Male","Colombo","Karachi","Islamabad","Lahore","Dhaka","Chittagong",
        "Mount Everest","K2","Kilimanjaro","Matterhorn","Mount Fuji","Denali","Aconcagua","Mont Blanc","Mount Elbrus","Table Mountain",
        "Grand Canyon","Niagara Falls","Victoria Falls","Angel Falls","Iguazu Falls","Yosemite Valley","Yellowstone","Banff","Torres del Paine","Fiordland",
        "Sahara Desert","Gobi Desert","Kalahari Desert","Atacama Desert","Mojave Desert","Sonoran Desert","Thar Desert","Namib Desert","Patagonian Desert","Great Victoria Desert",
        "Amazon Rainforest","Congo Rainforest","Daintree Rainforest","Tongass Forest","Black Forest","Sherwood Forest","Redwood Forest","Taiga Forest","Mangrove Forests","Borneo Rainforest",
        "Great Barrier Reef","Belize Barrier Reef","Red Sea Reef","Maldives Atolls","Caribbean Sea","Mediterranean Sea","Baltic Sea","North Sea","Caspian Sea","Dead Sea",
        "Arctic Ocean","Atlantic Ocean","Pacific Ocean","Indian Ocean","Southern Ocean","Lake Baikal","Lake Victoria","Lake Tanganyika","Great Lakes","Lake Titicaca",
        "Suez Canal","Panama Canal","Grand Canal Venice","Great Wall of China","Machu Picchu","Petra","Taj Mahal","Eiffel Tower","Colosseum","Big Ben",
        "Statue of Liberty","Empire State Building","Golden Gate Bridge","Brooklyn Bridge","CN Tower","Burj Khalifa","Burj Al Arab","Sydney Opera House","Christ the Redeemer","Hollywood Sign",
        "Times Square","Central Park","Disneyland","Walt Disney World","Universal Studios","Tokyo Disneyland","Epcot","Magic Kingdom","Legoland","SeaWorld",
        "Stonehenge","Angkor Wat","Borobudur","Shwedagon Pagoda","Potala Palace","Mount Rushmore","Acropolis","Alhambra","Versailles Palace","Louvre Museum",
        "Notre Dame","St. Peter’s Basilica","Sagrada Familia","Westminster Abbey","Hagia Sophia","Blue Mosque","Mezquita of Cordoba","Pantheon Rome","Parthenon Athens","Moai Statues Easter Island",
        "Antarctica","Greenland","Iceland","Faroe Islands","Galápagos Islands","Hawaiian Islands","Azores","Canary Islands","Madeira","Bermuda",
        "Silicon Valley","Wall Street","Hollywood","Las Ramblas","Shibuya Crossing","Oxford Street","Champs-Élysées","Fifth Avenue","Piccadilly Circus","Times Square Broadway",
        "Siberia","Himalayas","Andes","Rocky Mountains","Alps","Appalachians","Carpathians","Caucasus","Pyrenees","Ural Mountains",
        "Serengeti","Okavango Delta","Masai Mara","Kruger Park","Etosha","Chobe","Bwindi Forest","Ngorongoro Crater","Madagascar","Komodo Island",
        "Arctic Circle","Antarctic Circle","Tropics of Cancer","Tropics of Capricorn","Equator","Prime Meridian","International Date Line","Greenwich","South Pole","North Pole",
        "UN Headquarters","EU Parliament Brussels","Vatican City","Monaco","San Marino","Liechtenstein","Andorra","Luxembourg","Malta","Gibraltar"
    ]

    events = [
        "Wedding","Birthday Party","Anniversary","Engagement Party","Baby Shower","Gender Reveal","Bridal Shower","Bachelor Party","Bachelorette Party","Quinceañera",
        "Bar Mitzvah","Bat Mitzvah","Graduation","Prom","Homecoming","School Dance","Class Reunion","Family Reunion","Housewarming","Farewell Party",
        "Retirement Party","Welcome Party","Surprise Party","Block Party","Garden Party","Tea Party","Cocktail Party","Dinner Party","Potluck","Picnic",
        "Festival","Music Festival","Film Festival","Food Festival","Cultural Festival","Art Festival","Literary Festival","Beer Festival","Wine Festival","Tech Festival",
        "Conference","Summit","Symposium","Workshop","Seminar","Webinar","Hackathon","Game Jam","Pitch Day","Demo Day",
        "Trade Show","Expo","Convention","Comic-Con","Fan Expo","Auto Show","Boat Show","Job Fair","College Fair","Science Fair",
        "Tournament","Championship","League Match","Scrimmage","Exhibition Match","Opening Ceremony","Closing Ceremony","Medal Ceremony","Award Show","Red Carpet",
        "Premiere","Screening","Book Launch","Album Release","Listening Party","Gallery Opening","Art Auction","Photo Exhibition","Pop-Up Show","Fashion Show",
        "Parade","Carnival","Street Fair","Night Market","Farmers Market","Craft Fair","Flea Market","Antique Fair","Holiday Market","Swap Meet",
        "Protest","March","Rally","Sit-In","Vigil","Fundraiser","Charity Gala","Benefit Concert","Telethon","Auction",
        "Community Meeting","Town Hall","Council Meeting","Board Meeting","Shareholder Meeting","Club Meeting","Meetup","Networking Event","Mixer","Speed Dating",
        "Religious Service","Mass","Sermon","Prayer Meeting","Bible Study","Torah Study","Meditation Session","Retreat","Pilgrimage","Revival",
        "Sports Day","Field Day","Sports Clinic","Tryouts","Draft Day","Fan Fest","Watch Party","Viewing Party","Tailgate","Victory Parade",
        "Open House","Workshop Day","Info Session","Orientation","Onboarding","Career Day","STEM Day","Hack Day","Demo Session","User Group",
        "Press Conference","Product Launch","Keynote","Fireside Chat","Panel Discussion","Roundtable","Q&A Session","AMA Session","Town Hall Q&A","Media Briefing",
        "Disaster Drill","Fire Drill","Evacuation Drill","Safety Training","First Aid Training","CPR Class","Search and Rescue Drill","Cyber Drill","Tabletop Exercise","After-Action Review",
        "Auction Preview","Estate Sale","Yard Sale","Garage Sale","Moving Sale","Car Boot Sale","Rummage Sale","Silent Auction","Live Auction","Charity Auction",
        "Civic Holiday","National Day","Independence Day","Memorial Day","Veterans Day","Labor Day","Thanksgiving","New Year’s Eve","New Year’s Day","May Day",
        "Religious Holiday","Christmas","Easter","Ramadan","Eid al-Fitr","Eid al-Adha","Hanukkah","Diwali","Holi","Lunar New Year",
        "Seasonal Event","Spring Fair","Summer Fest","Autumn Harvest","Winter Carnival","Oktoberfest","Mardi Gras","Cherry Blossom Viewing","Lantern Festival","Fireworks Show",
        "Market Opening","Ribbon Cutting","Groundbreaking","Dedication","Inauguration","Swearing-In","Oath Ceremony","Graduation Hooding","Commencement","Matriculation",
        "Science Talk","Colloquium","Poster Session","Lab Open Day","Observing Night","Star Party","Makers Fair","Robotics Demo","Code Showcase","Data Night",
        "Wellness Workshop","Yoga Class","Fitness Bootcamp","Meditation Workshop","Breathwork Session","Nutrition Talk","Health Screening","Blood Drive","Vaccine Clinic","Mental Health Talk",
        "Environmental Cleanup","Tree Planting","Recycling Drive","Beach Cleanup","Park Restoration","Trail Day","Earth Day Event","Sustainability Summit","Climate Rally","Energy Expo",
        "Culinary Class","Wine Tasting","Beer Tasting","Coffee Cupping","Chocolate Tasting","Chef’s Table","Pop-Up Dinner","Supper Club","Food Truck Rally","Bake Sale",
        "Cultural Night","International Day","Language Exchange","Storytelling Night","Poetry Slam","Open Mic","Stand-Up Comedy","Improv Show","Theater Performance","Opera Night",
        "eSports Tournament","LAN Party","Speedrun Marathon","Charity Stream","Game Release","Patch Notes Live","Developer AMA","Beta Weekend","Alpha Test","Playtest Night",
        "Pet Adoption Day","Dog Show","Cat Show","Horse Show","4-H Fair","Ag Expo","Livestock Auction","Apiary Demo","Aquarium Expo","Reptile Expo",
        "Car Meet","Cars and Coffee","Track Day","Rally Stage","Drift Night","Dyno Day","Motorcycle Meet","Bike Ride","Group Hike","Climbing Meet",
        "Photo Walk","Art Jam","Sketch Crawl","NaNoWriMo Kickoff","Writers Workshop","Book Club","Library Storytime","Zine Fest","Print Fair","Craft Circle",
        "Space Launch","Rocket Test","Telescope Night","Eclipse Viewing","Meteor Shower Watch","Aurora Watch","Planetarium Show","Space Day","STEM Expo","Astronomy Lecture",
        "Historical Reenactment","Heritage Day","Museum Night","Archive Tour","Archaeology Dig","Site Tour","Architecture Walk","City Tour","Food Tour","Ghost Tour",
        "Legal Hearing","Court Session","Arbitration","Mediation","Debate Night","Model UN","Parliamentary Session","Budget Meeting","Policy Forum","Civic Workshop",
        "Recruiting Session","Auditions","Casting Call","Open Casting","Open Tryouts","Portfolio Review","Critique Night","Design Review","Demo Crit","Show-and-Tell",
        "Coding Interview Day","Career Fair","Resume Workshop","Mock Interview","Portfolio Night","Alumni Night","Mentor Match","Incubator Day","Accelerator Demo","Investor Day",
        "Sustainability Hackathon","Climate Hack","Health Hack","Edu Hack","GovTech Hack","Fintech Hack","AI Hack","Game Jam 48h","Music Hack","Design Sprint",
        "Maker Night","Fix-It Clinic","Repair Café","Tool Library Day","Bike Repair Day","Swap Shop","Skillshare Night","Peer Learning","Lightning Talks","PechaKucha",
        "Charity Run","5K Race","10K Race","Marathon","Ultramarathon","Triathlon","Swim Meet","Cycling Gran Fondo","Obstacle Race","Color Run",
        "Holiday Parade","Light Festival","Tree Lighting","Pumpkin Patch","Haunted House","Easter Egg Hunt","Santa Visit","Ice Sculpture Fest","Snow Day Games","Polar Plunge",
        "Tech Talk","Meet the Founder","Office Hours","User Research Session","Beta Feedback","Bug Bash","Roadmap Review","Product Office Hours","Design Crit","Dev Rel Meetup",
        "NFT Drop","Art Mint","Gallery Talk","Collector Preview","Studio Visit","Artist Talk","Residency Open","Public Art Unveiling","Mural Reveal","Street Performance",
        "Charter Signing","Partnership Announcement","MOU Ceremony","Grant Announcement","Scholarship Award","Dean’s List Ceremony","Honor Society Induction","Prize Giving","Laureate Lecture","Hall of Fame Induction"
    ]

    objects = [
        "Chair","Table","Desk","Sofa","Armchair","Stool","Bench","Bed","Bunk Bed","Nightstand",
        "Dresser","Wardrobe","Bookshelf","Cabinet","Drawer","Closet","Shelf","Coffin","Cradle","High Chair",
        "Lamp","Ceiling Light","Chandelier","Floor Lamp","Desk Lamp","Wall Sconce","Lantern","Flashlight","Torch","Candle",
        "TV","Monitor","Projector","Remote Control","Game Console","Controller","Keyboard","Mouse","Trackpad","Webcam",
        "Laptop","Desktop","Tablet","Smartphone","Smartwatch","E-Reader","Power Bank","USB Drive","External HDD","SSD",
        "Router","Modem","Switch","Hub","Access Point","NAS","Server","Raspberry Pi","Arduino","Microcontroller",
        "Printer","Scanner","Photocopier","Fax Machine","Shredder","Plotter","Label Maker","3D Printer","Laminator","Cash Register",
        "Refrigerator","Freezer","Oven","Stove","Microwave","Dishwasher","Toaster","Blender","Mixer","Coffee Maker",
        "Kettle","Air Fryer","Slow Cooker","Rice Cooker","Pressure Cooker","Juicer","Food Processor","Waffle Maker","Ice Cream Maker","Sous Vide",
        "Washer","Dryer","Vacuum Cleaner","Air Purifier","Humidifier","Dehumidifier","Fan","Heater","Space Heater","Thermostat",
        "Toilet","Sink","Bathtub","Shower","Faucet","Mirror","Towel Rack","Toothbrush","Toothpaste","Soap Dispenser",
        "Broom","Mop","Bucket","Sponge","Brush","Dustpan","Trash Can","Recycling Bin","Compost Bin","Gloves",
        "Hammer","Screwdriver","Wrench","Pliers","Tape Measure","Level","Drill","Saw","Utility Knife","Chisel",
        "Nails","Screws","Bolts","Nuts","Washers","Anchors","Glue","Epoxy","Duct Tape","Zip Ties",
        "Paint Brush","Roller","Paint Tray","Sandpaper","Putty Knife","Caulk Gun","Stud Finder","Ladder","Step Stool","Workbench",
        "Bike","Helmet","Lock","Pump","Tire","Tube","Skateboard","Scooter","Rollerblades","Skis",
        "Backpack","Suitcase","Duffel Bag","Messenger Bag","Wallet","Purse","Tote Bag","Briefcase","Fanny Pack","Camera Bag",
        "Camera","Lens","Tripod","Gimbal","Microphone","Headphones","Earbuds","Speaker","Soundbar","Mixer Board",
        "Watch","Bracelet","Necklace","Ring","Earrings","Sunglasses","Belt","Hat","Cap","Scarf",
        "T-Shirt","Shirt","Blouse","Jacket","Coat","Sweater","Hoodie","Pants","Jeans","Shorts",
        "Skirt","Dress","Suit","Tie","Bow Tie","Socks","Shoes","Boots","Sneakers","Sandals",
        "Book","Notebook","Journal","Planner","Calendar","Clipboard","Folder","Binder","Envelope","Stamp",
        "Pen","Pencil","Marker","Highlighter","Eraser","Sharpener","Ruler","Compass","Protractor","Calculator",
        "Paper","Cardboard","Sticky Notes","Tape","Glue Stick","Stapler","Staples","Paper Clips","Binder Clips","Rubber Bands",
        "Guitar","Piano","Violin","Drums","Flute","Saxophone","Trumpet","Clarinet","Harp","Ukulele",
        "Bed Sheet","Blanket","Pillow","Pillowcase","Duvet","Comforter","Mattress","Mattress Topper","Curtains","Rug",
        "Plate","Bowl","Cup","Mug","Glass","Wine Glass","Fork","Knife","Spoon","Chopsticks",
        "Cutting Board","Pan","Pot","Skillet","Wok","Baking Sheet","Casserole Dish","Colander","Measuring Cup","Measuring Spoon",
        "Thermometer","Hygrometer","Barometer","Blood Pressure Monitor","Pulse Oximeter","Glucose Meter","First Aid Kit","Bandage","Gauze","Antiseptic",
        "Umbrella","Raincoat","Parasol","Sunscreen","Bug Spray","Lip Balm","Hand Sanitizer","Mask","Gloves","Hatchet",
        "Tent","Sleeping Bag","Sleeping Pad","Camp Stove","Water Filter","Canteen","Thermos","Lantern Camping","Compass","Map",
        "Fishing Rod","Reel","Tackle Box","Lure","Hook","Net","Knife Outdoors","Multitool","Firestarter","Whistle",
        "Dumbbell","Barbell","Kettlebell","Resistance Band","Yoga Mat","Foam Roller","Jump Rope","Pull-Up Bar","Treadmill","Exercise Bike",
        "Ball","Soccer Ball","Basketball","Tennis Racket","Baseball Bat","Hockey Stick","Golf Club","Skate Helmet","Shin Guards","Mouthguard",
        "Clock","Alarm Clock","Wall Clock","Timer","Stopwatch","Hourglass","Metronome","Smart Display","Doorbell","Smart Lock",
        "Key","Keychain","ID Card","Credit Card","Coin","Cash","Receipt","Ticket","Boarding Pass","Passport",
        "Plant Pot","Vase","Terrarium","Aquarium","Birdcage","Pet Carrier","Litter Box","Dog Leash","Collar","Pet Bed",
        "Statue","Figurine","Poster","Painting","Canvas","Print","Frame","Sculpture","Bust","Model Kit",
        "Drone","RC Car","RC Plane","RC Boat","Quadcopter","Battery Pack","Charger","Adapter","Power Strip","Extension Cord",
        "Solar Panel","Inverter","Generator","Power Station","Surge Protector","UPS","Cable","HDMI Cable","Ethernet Cable","Audio Cable",
        "Whiteboard","Chalkboard","Chalk","Dry-Erase Marker","Pointer","Projector Screen","Laser Pointer","Clicker","Podium","Lectern",
        "Mouthwash","Deodorant","Razor","Shaver","Hair Dryer","Straightener","Curling Iron","Brush Hair","Comb","Nail Clipper",
        "Bike Light","Headlamp","Tail Light","Reflector","Cat-Eye Reflector","Bell","Horn","Mirror","Fender","Bottle Cage",
        "Mailbox","Door Mat","Coat Rack","Umbrella Stand","Shoe Rack","Boot Tray","Safe","Fire Extinguisher","Smoke Detector","CO Detector",
        "Toolkit","First Aid Pouch","Travel Adapter","Luggage Scale","Neck Pillow","Eye Mask","Earplugs","Toiletry Bag","Packing Cube","Rain Cover"
    ]

    weather = [
        "Sunny","Clear","Mostly Sunny","Partly Sunny","Partly Cloudy","Mostly Cloudy","Overcast","Broken Clouds","Scattered Clouds","High Clouds",
        "Low Clouds","Mid Clouds","Fair Weather","Hazy Sun","Haze","Mist","Fog","Dense Fog","Freezing Fog","Patchy Fog",
        "Drizzle","Light Drizzle","Moderate Drizzle","Heavy Drizzle","Freezing Drizzle","Rain","Light Rain","Moderate Rain","Heavy Rain","Torrential Rain",
        "Showers","Light Showers","Heavy Showers","Passing Showers","Scattered Showers","Isolated Showers","Thundershowers","Thunderstorm","Severe Thunderstorm","Supercell",
        "Lightning","Cloud-to-Ground Lightning","Cloud-to-Cloud Lightning","Dry Lightning","Thunder","Gust Front","Outflow Boundary","Microburst","Downburst","Squall Line",
        "Sleet","Ice Pellets","Freezing Rain","Wintry Mix","Snow","Light Snow","Moderate Snow","Heavy Snow","Blowing Snow","Snow Showers",
        "Flurries","Lake-Effect Snow","Graupel","Snow Grains","Snow Squall","Blizzard","Ground Blizzard","Whiteout","Ice Crust","Black Ice",
        "Hail","Small Hail","Large Hail","Giant Hail","Hail Core","Hailstorm","Frozen Precipitation","Rime Ice","Glaze Ice","Ice Accretion",
        "Wind","Light Breeze","Gentle Breeze","Moderate Breeze","Fresh Breeze","Strong Breeze","Near Gale","Gale","Strong Gale","Storm Force",
        "Hurricane Force","Gusty Winds","Wind Gust","Wind Shear","Katabatic Wind","Anabatic Wind","Chinook","Bora","Mistral","Sirocco",
        "Dust","Dust Haze","Dust Storm","Sand","Sandstorm","Blowing Sand","Saharan Dust","Haboob","Ashfall","Volcanic Ash",
        "Heat","Warm","Hot","Very Hot","Heatwave","Heat Index High","Humid","Muggy","Sultry","Dry Heat",
        "Cold","Cool","Chilly","Cold Snap","Hard Freeze","Freeze","Frost","Hoarfrost","Rime","Wind Chill",
        "Temperature Inversion","Radiational Cooling","Cold Pool","Warm Front","Cold Front","Stationary Front","Occluded Front","Dryline","Trough","Ridge",
        "High Pressure","Low Pressure","Cyclone","Anticyclone","Extratropical Cyclone","Subtropical Cyclone","Tropical Wave","Tropical Depression","Tropical Storm","Hurricane",
        "Typhoon","Super Typhoon","Eye","Eyewall","Rainbands","Storm Surge","King Tide","Rip Current","High Surf","Rough Seas",
        "Calm","Glass Calm","Sea Breeze","Land Breeze","Monsoon","Intertropical Convergence Zone","Trade Winds","Westerlies","Polar Easterlies","Jet Stream",
        "Orographic Lift","Lee Side Downdraft","Rain Shadow","Virga","Fallstreak Hole","Hole-Punch Cloud","Mammatus","Asperitas","Lenticular Cloud","Noctilucent Cloud",
        "Altocumulus","Altostratus","Cirrus","Cirrostratus","Cirrocumulus","Cumulus","Cumulonimbus","Stratus","Nimbostratus","Stratocumulus",
        "Radiation Fog","Advection Fog","Upslope Fog","Valley Fog","Sea Fog","Ice Fog","Steam Fog","Frontal Fog","Pogonip","Patchy Dense Fog",
        "Visibility Good","Visibility Moderate","Visibility Poor","Visibility Very Poor","Ceiling Low","Ceiling Broken","Ceiling Overcast","VFR","MVFR","IFR",
        "Dew","Heavy Dew","Wet Bulb","Dew Point High","Dew Point Low","Relative Humidity High","Relative Humidity Low","Saturation","Supersaturation","Condensation",
        "Evaporation","Sublimation","Deposition","Latent Heat","Sensible Heat","Thermal Gradient","Heat Dome","Urban Heat Island","Cold Air Damming","Polar Vortex",
        "Aurora Borealis","Aurora Australis","Geomagnetic Storm","Solar Radiation High","UV Index High","UV Index Extreme","Sun Halo","Sun Pillar","Sun Dog","Moon Halo",
        "Rainbow","Double Rainbow","Fogbow","Glory","Brocken Spectre","Crepuscular Rays","Anticrepuscular Rays","Green Flash","Mirage","Superior Mirage",
        "Sea Smoke","Lake-Effect Clouds","Snowbelt","Thundersnow","Thunder Ice Pellets","Freezing Spray","Icing Conditions","Mountain Wave","Rotor Cloud","Foehn Wind",
        "Drought","Severe Drought","Flash Drought","Flood","Flash Flood","River Flood","Coastal Flood","Inundation","High Water","Dam Break Flood",
        "Avalanche","Rockfall","Landslide","Debris Flow","Mudslide","Glacial Outburst Flood","Lahar","Dust Devil","Landspout","Waterspout Tornado",
        "Tornado","EF0 Tornado","EF1 Tornado","EF2 Tornado","EF3 Tornado","EF4 Tornado","EF5 Tornado","Cyclogenesis","Bomb Cyclone","Derecho",
        "Storm Watch","Storm Warning","Severe Watch","Severe Warning","Hurricane Watch","Hurricane Warning","Tornado Watch","Tornado Warning","Flood Watch","Flood Warning",
        "Air Quality Good","Air Quality Moderate","Air Quality Unhealthy","Air Quality Very Unhealthy","Air Quality Hazardous","PM2.5 High","PM10 High","Ozone Alert","Smoke","Wildfire Smoke"
    ]

    emotions = [
        "Happiness","Joy","Delight","Excitement","Ecstasy","Euphoria","Contentment","Satisfaction","Relief","Calm",
        "Serenity","Peacefulness","Relaxation","Tranquility","Comfort","Safety","Trust","Affection","Love","Adoration",
        "Fondness","Compassion","Empathy","Kindness","Gratitude","Appreciation","Admiration","Respect","Pride","Hope",
        "Optimism","Anticipation","Curiosity","Surprise","Amazement","Awe","Wonder","Enthusiasm","Interest","Engagement",
        "Passion","Attraction","Infatuation","Desire","Longing","Yearning","Nostalgia","Sentimentality","Melancholy","Sadness",
        "Sorrow","Grief","Heartache","Loneliness","Emptiness","Boredom","Apathy","Indifference","Disappointment","Regret",
        "Remorse","Shame","Guilt","Embarrassment","Awkwardness","Insecurity","Self-Doubt","Vulnerability","Jealousy","Envy",
        "Frustration","Irritation","Annoyance","Impatience","Agitation","Stress","Tension","Overwhelm","Restlessness","Worry",
        "Fear","Anxiety","Dread","Apprehension","Nervousness","Unease","Panic","Shock","Horror","Terror",
        "Anger","Rage","Fury","Outrage","Resentment","Bitterness","Hostility","Hatred","Contempt","Disgust",
        "Revenge","Vindictiveness","Suspicion","Distrust","Cynicism","Skepticism","Disbelief","Confusion","Perplexity","Ambivalence",
        "Surprise Pleasant","Surprise Unpleasant","Startle","Relief After Stress","Catharsis","Empowerment","Confidence","Determination","Motivation","Drive",
        "Inspiration","Creativity","Imagination","Flow","Playfulness","Humor","Amusement","Laughter","Cheerfulness","Lightheartedness",
        "Shyness","Timidity","Modesty","Humility","Politeness","Respectfulness","Obedience","Submission","Devotion","Faith",
        "Spirituality","Transcendence","Connectedness","Harmony","Balance","Equanimity","Acceptance","Forgiveness","Generosity","Altruism",
        "Survivor’s Guilt","Homesickness","Culture Shock","Stage Fright","Test Anxiety","Performance Anxiety","Writer’s Block","Imposter Syndrome","Moral Outrage","Existential Dread",
        "Resilience","Tenacity","Bravery","Courage","Assertiveness","Independence","Autonomy","Freedom","Empowerment","Triumph",
        "Shock Delight","Shock Disgust","Ambition","Greed","Lust","Gluttony","Sloth","Wrath","Envy Complex","Pride Complex"
    ]

    culture = [
        "Language","Dialects","Accents","Writing Systems","Alphabet","Calligraphy","Storytelling","Oral Tradition","Poetry","Proverbs",
        "Mythology","Folklore","Legends","Fairy Tales","Epic Tales","Fables","Superstitions","Rituals","Ceremonies","Festivals",
        "Music","Dance","Theater","Drama","Opera","Ballet","Chanting","Drumming","Singing","Folk Songs",
        "Cuisine","Food Traditions","Regional Dishes","Street Food","Tea Culture","Coffee Culture","Wine Culture","Feasting","Fasting","Dining Etiquette",
        "Clothing","Fashion","Dress Codes","Textiles","Costumes","Uniforms","Adornment","Jewelry","Body Art","Tattoos",
        "Architecture","Monuments","Temples","Mosques","Churches","Synagogues","Shrines","Pagodas","Castles","Palaces",
        "Art","Painting","Sculpture","Mosaics","Murals","Graffiti","Photography","Film","Digital Art","Installations",
        "Crafts","Pottery","Weaving","Knitting","Wood Carving","Metalwork","Glassmaking","Basketry","Paper Art","Origami",
        "Values","Beliefs","Norms","Ethics","Morality","Taboos","Customs","Hospitality","Honor Codes","Etiquette",
        "Kinship","Family","Tribes","Clans","Community","Village Life","Urban Culture","Rural Culture","Generational Culture","Elders",
        "Religion","Christianity","Islam","Judaism","Buddhism","Hinduism","Sikhism","Shinto","Taoism","Confucianism",
        "Spirituality","Animism","Ancestor Worship","Totemism","Mysticism","Shamanism","New Age","Occult","Astrology","Divination",
        "Philosophy","Logic","Reason","Humanism","Stoicism","Epicureanism","Existentialism","Postmodernism","Critical Theory","Pragmatism",
        "Politics","Democracy","Monarchy","Republic","Empire","Socialism","Communism","Capitalism","Anarchism","Fascism",
        "Economics","Trade","Markets","Barter","Money","Banking","Finance","Labor","Industry","Globalization",
        "Education","Schools","Universities","Literacy","Scholarship","Debate","Exams","Graduations","Academic Dress","Ceremonial Titles",
        "Sports","Games","Competitions","Races","Wrestling","Martial Arts","Athletics","Olympics","World Cup","Festive Sports",
        "Media","Newspapers","Magazines","Radio","Television","Cinema","Internet","Podcasts","Streaming","Social Media",
        "Technology","Tools","Machines","Inventions","Innovation","Science Culture","Research Labs","Hacker Culture","Maker Culture","Digital Culture",
        "Symbols","Flags","Icons","Totems","Logos","Seals","National Anthems","Coats of Arms","Emblems","Graffiti Tags",
        "Migration","Diaspora","Refugee Culture","Exile","Colonialism","Imperialism","Indigenous Culture","Cultural Revival","Heritage","Global Citizenship",
        "Work Culture","Corporate Culture","Startup Culture","Professionalism","Work-Life Balance","Entrepreneurship","Freelancing","Gig Economy","Remote Work","Coworking",
        "Leisure","Tourism","Travel","Exploration","Adventure","Entertainment","Clubbing","Festivals","Carnival","Street Culture",
        "Subcultures","Punk","Goth","Hip Hop","Skater","Emo","Raver","Hacker","Otaku","Furry Fandom",
        "Youth Culture","Teen Culture","College Culture","Generation X","Millennials","Gen Z","Boomers","Silent Generation","Intergenerational Culture","Future Generations",
        "Cultural Exchange","Trade Routes","Silk Road","Cultural Diffusion","Hybrid Culture","Fusion Culture","Multiculturalism","Cross-Culturalism","World Fairs","Olympics Opening",
        "Cultural Heritage","UNESCO Sites","World Monuments","Museums","Libraries","Archives","Preservation","Restoration","Cultural Tourism","Heritage Festivals"
    ]

    content_formats = [
        "Book","Ebook","Audiobook","Magazine","Newspaper","Pamphlet","Brochure","Flyer","Zine","Journal",
        "Article","Blog Post","Op-Ed","Editorial","Column","Essay","Research Paper","White Paper","Case Study","Thesis",
        "Dissertation","Report","Memo","Brief","Manual","Handbook","Guidebook","Playbook","FAQ","Glossary",
        "Encyclopedia","Dictionary","Atlas","Almanac","Yearbook","Catalog","Directory","Index","Compendium","Anthology",
        "Novel","Short Story","Novella","Flash Fiction","Poem","Epic Poem","Haiku","Sonnet","Free Verse","Ballad",
        "Script","Screenplay","Teleplay","Stage Play","Radio Play","Podcast Script","Storyboard","Comic Script","Dialogue","Transcript",
        "Comic","Manga","Graphic Novel","Webcomic","Fumetti","Cartoon Strip","Political Cartoon","Storyboard Comic","Digital Comic","Motion Comic",
        "Video","Film","Short Film","Feature Film","Documentary","Mockumentary","Animation","Anime","Cartoon","Motion Picture",
        "Clip","Reel","Vlog","Livestream","Webinar","Lecture Recording","Screencast","Tutorial Video","Explainer Video","Promo Video",
        "Presentation","Slideshow","Pitch Deck","Poster","Infographic","Diagram","Flowchart","Mind Map","Whiteboard Drawing","Data Visualization",
        "Podcast","Radio Show","Talk Show","Interview","Debate","Panel","Roundtable","Q&A Session","Commentary","Reaction Video",
        "Song","Album","Single","EP","Mixtape","Playlist","Live Performance","Concert Recording","Lyric Video","Music Video",
        "Interactive Story","Choose-Your-Own-Adventure","Visual Novel","Interactive Fiction","Hypertext Story","Alternate Reality Game","Simulation","Immersive Theater","Gamebook","Text Adventure",
        "Game","Board Game","Card Game","Video Game","Mobile Game","Arcade Game","Puzzle Game","Role-Playing Game","MMO","Esports Match",
        "Email","Newsletter","Press Release","Internal Memo","Bulletin","Announcement","Public Statement","Open Letter","Letter","Postcard",
        "Message","Text Message","Chat Log","Forum Post","Comment","Tweet","Thread","Facebook Post","Instagram Post","TikTok Video",
        "Snap Story","Insta Story","Reel","YouTube Short","Vine","GIF","Meme","Sticker","Emoji","Bitmoji",
        "3D Model","CAD File","Blueprint","Prototype","Mockup","Wireframe","Design System","Style Guide","Pattern Library","Template",
        "Virtual Tour","VR Experience","AR Filter","MR App","360 Video","Interactive Map","Geo Story","Drone Footage","Time-Lapse","Stop Motion",
        "Survey","Poll","Quiz","Form","Application","Questionnaire","Test","Exam","Worksheet","Workbook",
        "Educational Module","Lesson Plan","Course","Curriculum","MOOC","Workshop Guide","Field Notes","Lab Notebook","Experiment Log","Observation Sheet",
        "Journal Entry","Diary","Scrapbook","Photo Album","Portfolio","Sketchbook","Storyboard Portfolio","Case File","Dossier","Profile",
        "License","Permit","ID Card","Passport","Ticket","Boarding Pass","Coupon","Voucher","Invoice","Receipt",
        "Contract","Agreement","Treaty","Accord","Bill","Law Text","Constitution","Policy Paper","Regulation","Charter",
        "Game Save File","Replay File","Patch Notes","Changelog","Release Notes","Dev Log","Beta Test Notes","Alpha Build Notes","Walkthrough","Strategy Guide"
    ]
    
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

