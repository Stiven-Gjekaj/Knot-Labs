import json
import os
import random
from collections import Counter, defaultdict
from typing import Dict, List, Tuple


categories = ["music", "comedy", "education", "news", "dance", "entertainment"]


def _ensure_dirs() -> Dict[str, str]:
    base = os.path.join("data")
    # Only ensure the base data directory. All files live directly under it.
    os.makedirs(base, exist_ok=True)
    # Keep the same dict shape for minimal downstream changes.
    return {
        "base": base,
        "videos": base,
        "creators": base,
        "users": base,
    }


def _build_candidates(n: int = 10000, creators: int = 200) -> Tuple[List[dict], Dict[str, Tuple[str, str]]]:
    candidates: List[dict] = []
    # Map video_id -> (creator_id, category)
    vid_lookup: Dict[str, Tuple[str, str]] = {}
    for i in range(1, n + 1):
        is_pay = random.random() < 0.05
        content_type = random.choices(["Video", "Image", "Status"], weights=[80, 10, 10], k=1)[0]
        content_status = "Active" if random.random() < 0.98 else "Unavailable"
        creator_id = f"c{random.randint(1, creators)}"
        category = random.choice(categories)
        candidate = {
            "id": f"v{i}",
            "creatorId": creator_id,
            "description": f"Description for v{i}",
            "comment": f"Top-level comment for v{i}",
            "category": category,
            "isPayPerView": is_pay,
            "ContentType": content_type,
            "isPromotion": random.random() < 0.04,
            "isFlagged": random.random() < 0.01,
            "ContentStatus": content_status,
            "payPerViewCount": random.randint(0, 50) if is_pay else 0,
            "likesCount": random.randint(0, 1000),
            "commentsCount": random.randint(0, 500),
            "giftsCount": random.randint(0, 100),
            "shareCount": random.randint(0, 300),
            "gender": random.choice(["male", "female", "other"]),
            "star": random.randint(1, 5),
            "score": -10000,
        }
        candidates.append(candidate)
        vid_lookup[candidate["id"]] = (creator_id, category)
    return candidates, vid_lookup


def _creator_primary_categories(candidates: List[dict]) -> Dict[str, str]:
    by_creator: Dict[str, Counter] = defaultdict(Counter)
    for v in candidates:
        by_creator[v["creatorId"]][v["category"]] += 1
    primary: Dict[str, str] = {}
    for cid, ctr in by_creator.items():
        # Pick the most common category for the creator
        primary[cid] = ctr.most_common(1)[0][0]
    return primary


def _make_user(idx: int, vid_lookup: Dict[str, Tuple[str, str]],
               primary_category_by_creator: Dict[str, str],
               candidates: List[dict]) -> dict:
    uid = f"user{idx}"
    preferred = random.sample(categories, k=random.randint(2, 3))
    # Sample seen creators from the actual creators present in candidates
    seen_pool = sorted({v["creatorId"] for v in candidates})
    ccount = len(seen_pool)
    if ccount == 0:
        seen_creators = []
    else:
        low = max(1, int(ccount * 0.4))
        high = max(low, int(ccount * 0.8))
        seen_creators = random.sample(seen_pool, k=min(random.randint(low, high), ccount))
    # 36-72 recent creators, allowing repeats to simulate overexposure
    recent_base = seen_creators if seen_creators else seen_pool
    recent_creators = [random.choice(recent_base) for _ in range(random.randint(36, 72))] if recent_base else []

    # Build watched_videos with a bias toward preferred categories
    vids_by_cat: Dict[str, List[str]] = defaultdict(list)
    for v in candidates:
        vids_by_cat[v["category"]].append(v["id"])
    watch_target = random.randint(20, 60)
    chosen: set[str] = set()
    # Take up to ~70% from preferred categories
    pref_quota = int(watch_target * 0.7)
    for cat in preferred:
        pool = vids_by_cat.get(cat, [])
        if not pool:
            continue
        take = min(max(1, pref_quota // max(1, len(preferred))), len(pool))
        chosen.update(random.sample(pool, take))
    # Fill the rest from other categories
    all_ids = [v["id"] for v in candidates]
    while len(chosen) < watch_target and len(chosen) < len(all_ids):
        chosen.add(random.choice(all_ids))
    watched_videos = list(chosen)

    # Creator engagement derived from watched videos + a few extras
    creator_engagement: Dict[str, int] = defaultdict(int)
    for vid in watched_videos:
        creator_id, cat = vid_lookup[vid]
        inc = random.randint(2, 3) if cat in preferred else random.randint(1, 2)
        creator_engagement[creator_id] += inc
    # Add some random interaction noise
    extra_eng = random.randint(5, 15)
    for _ in range(extra_eng):
        c = random.choice(seen_creators)
        creator_engagement[c] += random.randint(1, 3)

    # Aggregations
    # Most watched creator/category from watched_videos
    creator_counts: Dict[str, int] = defaultdict(int)
    category_counts: Dict[str, int] = defaultdict(int)
    for vid in watched_videos:
        c, cat = vid_lookup[vid]
        creator_counts[c] += 1
        category_counts[cat] += 1
    mw_creator_id, mw_creator_times = (None, 0)
    if creator_counts:
        mw_creator_id, mw_creator_times = max(creator_counts.items(), key=lambda x: x[1])
    mw_cat_name, mw_cat_times = (None, 0)
    if category_counts:
        mw_cat_name, mw_cat_times = max(category_counts.items(), key=lambda x: x[1])

    # Most interacted with creator/category from creator_engagement
    mi_creator_id, mi_creator_times = (None, 0)
    if creator_engagement:
        mi_creator_id, mi_creator_times = max(creator_engagement.items(), key=lambda x: x[1])
    cat_eng: Dict[str, int] = defaultdict(int)
    for cid, count in creator_engagement.items():
        cat = primary_category_by_creator.get(cid)
        if cat:
            cat_eng[cat] += count
    mi_cat_name, mi_cat_times = (None, 0)
    if cat_eng:
        mi_cat_name, mi_cat_times = max(cat_eng.items(), key=lambda x: x[1])

    return {
        "id": uid,
        "preferred_categories": preferred,
        "seen_creators": seen_creators,
        "recent_creators": recent_creators,
        # Persist richer engagement context
        "watched_videos": watched_videos,
        "creator_engagement": dict(creator_engagement),
        # Aggregated stats requested
        "most_watched_creator": {"id": mw_creator_id, "times": mw_creator_times},
        "most_watched_category": {"name": mw_cat_name, "times": mw_cat_times},
        "most_interacted_with_creator": {"id": mi_creator_id, "times": mi_creator_times},
        "most_interacted_with_category": {"name": mi_cat_name, "times": mi_cat_times},
    }


def main() -> None:
    dirs = _ensure_dirs()

    # Build candidates and lookups
    candidates, vid_lookup = _build_candidates(n=10000, creators=200)
    primary_category_by_creator = _creator_primary_categories(candidates)

    # Build 50 users as requested
    users = [_make_user(i, vid_lookup, primary_category_by_creator, candidates) for i in range(1, 51)]

    # Write split files into data/ subfolders

    # Write flat files into data/
    with open(os.path.join(dirs["videos"], "videos.json"), "w") as f:
        json.dump(candidates, f, indent=2)

    # Minimal creators summary for convenience
    # Compute simple stats (primary category and video count per creator)
    creators_summary: Dict[str, Dict[str, object]] = defaultdict(dict)
    video_count_by_creator: Dict[str, int] = defaultdict(int)
    for v in candidates:
        video_count_by_creator[v["creatorId"]] += 1
    for cid, count in video_count_by_creator.items():
        creators_summary[cid] = {
            "id": cid,
            "primary_category": primary_category_by_creator.get(cid),
            "video_count": count,
        }
    with open(os.path.join(dirs["creators"], "creators.json"), "w") as f:
        json.dump(list(creators_summary.values()), f, indent=2)

    with open(os.path.join(dirs["users"], "users.json"), "w") as f:
        json.dump(users, f, indent=2)


if __name__ == "__main__":
    main()
