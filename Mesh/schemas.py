from __future__ import annotations

from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field


class MeshUser(BaseModel):
    username: str
    userID: str
    Gender: Literal['male','female','other']
    SeenPosts: List[str] = []
    RecentCreators: List[str] = []
    CreatorScore: int = 0
    ViewerScore: Dict[str, int] = {}
    CategoryScores: Dict[str, int] = {}
    created_at: float


class MeshPost(BaseModel):
    postID: str
    creator: str
    description: Optional[str] = "Description Here"
    Score: float = 0.0
    Categories: List[str] = []
    country: Optional[str] = None
    created_at: float
    isPayPerView: bool = False
    PostType: Literal['Video','Photo'] = 'Video'
    isPromotion: bool = False
    isFlagged: bool = False
    isActive: bool = True
    isDeleted: bool = False
    payPerViewCount: int = 0
    likesCount: int = 0
    commentsCount: int = 0
    giftsCount: int = 0
    isSuggested: bool = False
    shareCount: int = 0
    star: int = 0
