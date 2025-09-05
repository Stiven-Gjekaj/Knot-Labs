from __future__ import annotations
from pydantic import BaseModel, Field
try:
    # Pydantic v2
    from pydantic import ConfigDict  # type: ignore
except Exception:  # pragma: no cover
    ConfigDict = None  # type: ignore
from typing import List, Dict, Optional, Literal

if ConfigDict is not None:
    class _BaseSchema(BaseModel):  # type: ignore
        model_config = ConfigDict(populate_by_name=True)  # type: ignore
else:
    class _BaseSchema(BaseModel):  # type: ignore
        class Config:  # For Pydantic v1
            allow_population_by_field_name = True


class VideoCandidate(_BaseSchema):

# To add more score variables:
# 1. Add the new field below with a comment.
# 2. Update generate_sample_data.py to generate the new field.
# 3. Update drift_ranker.py to use the new field in scoring.

    # Represents a candidate item for ranking using Knot Drift's structure
    id: str  # Unique content identifier
    creator_id: str = Field(alias="creatorId")  # Creator identifier
    description: Optional[str] = None  # Content description text
    comment_text: Optional[str] = Field(default=None, alias="comment")  # A top-level comment/caption
    category: str  # Category of the content

    # Flags and status (flat, Knot Drift style)
    is_pay_per_view: bool = Field(default=False, alias="isPayPerView")
    content_type: Optional[Literal["Image", "Status", "Video"]] = Field(default="Video", alias="ContentType")
    is_promotion: bool = Field(default=False, alias="isPromotion")
    is_flagged: bool = Field(default=False, alias="isFlagged")
    content_status: Optional[Literal["Active", "Unavailable"]] = Field(default="Active", alias="ContentStatus")

    # Engagement counts (Knot Drift naming → our attributes)
    pay_per_view_count: int = Field(default=0, alias="payPerViewCount")
    likes: int = Field(default=0, alias="likesCount")
    comments: int = Field(default=0, alias="commentsCount")
    shares: int = Field(default=0, alias="shareCount")
    gift_count: int = Field(default=0, alias="giftsCount")

    # Other metadata
    gender: Optional[Literal["male", "female", "other"]] = Field(default=None, alias="gender")
    star: int = Field(default=0, alias="star")

    # Note: "score" field present in source JSON is ignored by this model.

class User(_BaseSchema):
    # Represents a user context for ranking.
    id: str  # Unique user identifier
    preferred_categories: List[str] = Field(default_factory=list)  # List of user's preferred video categories
    seen_creators: List[str] = Field(default_factory=list)  # List of creator IDs the user has seen
    recent_creators: List[str] = Field(default_factory=list)  # List of creator IDs the user has recently seen
    watched_videos: List[str] = Field(default_factory=list)  # IDs of videos the user has watched
    creator_engagement: Dict[str, int] = Field(default_factory=dict)  # Creator ID -> engagement count

class RankingRequest(_BaseSchema):
    # Request model for ranking API.
    user: User  # User context for ranking
    candidates: List[VideoCandidate]  # List of candidate videos to rank

class RankedVideo(VideoCandidate):
    # Represents a video with an assigned ranking score.
    score: float  # The ranking score for the video

class RankingResponse(_BaseSchema):
    # Response model for ranking API. 
    results: List[RankedVideo]  # List of ranked videos
