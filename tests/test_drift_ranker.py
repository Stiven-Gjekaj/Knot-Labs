from Drift.models import User, VideoCandidate
from Drift.drift_ranker import rank_videos


def make_candidate(id: str, creator: str, category: str, **kwargs):
    base = {
        'id': id,
        'creatorId': creator,
        'category': category,
        'isPayPerView': False,
        'ContentType': 'Video',
        'isPromotion': False,
        'isFlagged': False,
        'ContentStatus': 'Active',
        'payPerViewCount': 0,
        'likesCount': 0,
        'commentsCount': 0,
        'shareCount': 0,
        'giftsCount': 0,
        'star': 0,
    }
    base.update(kwargs)
    return VideoCandidate(**base)


def test_rank_videos_basic():
    user = User(
        id='u1',
        preferred_categories=['cats'],
        seen_creators=[],
        recent_creators=[],
        watched_videos=[],
        creator_engagement={},
    )
    a = make_candidate('a', 'c1', 'cats', likesCount=10)
    b = make_candidate('b', 'c2', 'dogs', likesCount=1)
    ranked = rank_videos(user, [a, b])
    assert len(ranked) >= 2
    assert ranked[0].id == 'a'

