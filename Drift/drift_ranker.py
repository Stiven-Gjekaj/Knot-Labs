from __future__ import annotations
import random
from typing import List, Optional
import math
from models import VideoCandidate, User, RankedVideo


def compute_score(user: User, video: VideoCandidate) -> float:

# To add more score variables:
# 1. Add the new field to VideoCandidate in models.py.
# 2. Update generate_sample_data.py to generate the new field.
# 3. Add a line here to include the new field in the score calculation, e.g.:
#    score += video.new_field * weight

    # Compute score for one video.
    score = 0.0
    # Core engagement signals
    score += video.likes * 1.0
    score += video.comments * 2.0
    score += video.shares * 3.0
    score += video.gift_count * 2.0
    score += video.pay_per_view_count * 0.5
    score += video.star * 20.0

    # Content flags (Knot Drift structure)
    if getattr(video, "is_suggested", False):
        score += 5.0
    if video.is_promotion:
        score -= 10.0
    if video.is_flagged:
        score -= 500.0
    if getattr(video, "content_status", "Active") != "Active": # If video not active, don't suggest
        score = 0
    if getattr(video, "content_type", "Video") != "Video": # Prefer video type slightly
        score -= 25.0

    # User preference alignment
    if video.category in user.preferred_categories:
        score += 25.0
    over = user.recent_creators.count(video.creator_id)
    score -= over * 10.0
    bonus = random.random() * (5.0 if video.creator_id not in user.seen_creators else 2.5)
    score += bonus

    # Engagement-based adjustments
    # videos the user has already watched never appear again
    if video.id in getattr(user, "watched_videos", []):
        score = 0

    # Boost creators the user engages with more (tempered by sqrt)
    ENGAGEMENT_WEIGHT = 15.0
    eng_count = getattr(user, "creator_engagement", {}).get(video.creator_id, 0)
    if eng_count > 0:
        score += math.sqrt(eng_count) * ENGAGEMENT_WEIGHT
    return score


def _apply_limits(
    scored: List[tuple[VideoCandidate, float]],
    limit: int = 20,
    per_creator_limit: int = 2,
    max_category_run: int = 3,
    max_creator_run: int = 2,
) -> List[RankedVideo]:
    # Reorder top results to enforce:
    # - per-creator overall limit (default 2)
    # - no more than `max_category_run` of the same category in a row (default 3)
    # - no more than `max_creator_run` from the same creator in a row (default 2)
    results: List[RankedVideo] = []
    creator_counts: dict[str, int] = {}

    # Track consecutive runs
    last_cat: Optional[str] = None
    last_cat_run: int = 0
    last_creator: Optional[str] = None
    last_creator_run: int = 0

    # Work on a copy since we will remove items as we place them
    pool: List[tuple[VideoCandidate, float]] = list(scored)

    while len(results) < limit and pool:
        placed = False
        # Greedily pick the highest-scoring candidate that doesn't violate constraints
        for idx, (video, score) in enumerate(pool):
            if creator_counts.get(video.creator_id, 0) >= per_creator_limit:
                continue
            if last_cat_run >= max_category_run and last_cat is not None and video.category == last_cat:
                continue
            if last_creator_run >= max_creator_run and last_creator is not None and video.creator_id == last_creator:
                continue

            # Place this candidate
            results.append(RankedVideo(**video.dict(), score=round(score, 2)))
            creator_counts[video.creator_id] = creator_counts.get(video.creator_id, 0) + 1

            # Update category run
            if last_cat == video.category:
                last_cat_run += 1
            else:
                last_cat = video.category
                last_cat_run = 1

            # Update creator run
            if last_creator == video.creator_id:
                last_creator_run += 1
            else:
                last_creator = video.creator_id
                last_creator_run = 1

            # Remove from pool and mark placed
            del pool[idx]
            placed = True
            break

        if not placed:
            # No candidate can be placed without breaking run rules or per-creator limits.
            # Stop to avoid violating the constraints.
            break

    return results


def rank_videos(user: User, videos: List[VideoCandidate]) -> List[RankedVideo]:
    # Return ranked videos.
    scored = [(v, compute_score(user, v)) for v in videos]
    scored.sort(key=lambda x: x[1], reverse=True)
    return _apply_limits(scored)
