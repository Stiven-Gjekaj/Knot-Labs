import os
import json
from Mesh.drift_adapter import mesh_user_to_drift_user, mesh_post_to_drift_video, mesh_posts_to_drift_candidates


def test_mesh_user_to_drift_user_basic():
    u = {
        'userID': 'u1',
        'CategoryScores': {'cats': 5, 'dogs': 2},
        'RecentCreators': ['c2'],
        'ViewerScore': {'c1': 3},
        'SeenPosts': ['p1']
    }
    du = mesh_user_to_drift_user(u)
    assert du.id == 'u1'
    assert 'cats' in du.preferred_categories


def test_mesh_post_to_drift_video_and_dir(tmp_path):
    post = {
        'postID': 'p1',
        'creator': 'c1',
        'Category': { 'macro': 'cats', 'meso': 'mammals', 'micro': ['cats','dogs'] },
        'isActive': True,
        'isDeleted': False,
        'isFlagged': False,
        'likesCount': 2,
        'commentsCount': 0,
        'shareCount': 0,
        'giftsCount': 0,
        'payPerViewCount': 0,
        'PostType': 'Video'
    }
    dv = mesh_post_to_drift_video(post)
    assert dv is not None and dv.category == 'cats'

    d = tmp_path / 'Posts'
    d.mkdir()
    with open(d / 'p1.json', 'w', encoding='utf-8') as f:
        json.dump(post, f)
    cands = mesh_posts_to_drift_candidates(str(d))
    assert cands and cands[0].id == 'p1'
