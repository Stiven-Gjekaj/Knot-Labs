from __future__ import annotations

import json
import os
from Mesh.tools.export_import import export_ndjson, import_ndjson


def test_export_import_roundtrip(tmp_path):
    users = tmp_path / 'Users'
    posts = tmp_path / 'Posts'
    users.mkdir()
    posts.mkdir()
    # Seed one user and one post
    u = {'userID': 'u1', 'username': 'alice', 'Gender': 'other', 'SeenPosts': [], 'RecentCreators': [], 'CreatorScore': 0, 'ViewerScore': {}, 'CategoryScores': {}, 'created_at': 0}
    p = {'postID': 'p1', 'creator': 'u1', 'Category': {'macro': ['cats'], 'meso': ['pets'], 'micro': ['cats']}, 'country': 'US', 'created_at': 0}
    json.dump(u, open(users / 'u1.json', 'w', encoding='utf-8'))
    json.dump(p, open(posts / 'p1.json', 'w', encoding='utf-8'))

    out = tmp_path / 'dump.ndjson'
    export_ndjson(str(users), str(posts), str(out))
    # Clear dirs
    for d in (users, posts):
        for name in os.listdir(d):
            os.remove(d / name)

    stats = import_ndjson(str(out), str(users), str(posts))
    assert stats['users'] == 1 and stats['posts'] == 1
    assert os.path.isfile(users / 'u1.json') and os.path.isfile(posts / 'p1.json')

