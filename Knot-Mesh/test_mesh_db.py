import tempfile

from mesh_db import MeshDB, MeshStore


def test_category_scores_persist_without_top_categories():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = MeshStore(tmpdir)
        db = MeshDB(store)
        db.create_user('u1', 'male')
        db.create_user('creator', 'female')
        db.create_post('p1', 'creator', ['Cat1'])
        db.create_post('p2', 'creator', ['Cat2'])
        db.record_engagement('u1', 'p1', 'like')  # Cat1 +1
        db.record_engagement('u1', 'p2', 'share')  # Cat2 +3
        user = store.load_user('u1')
        assert user['CategoryScores'] == {'Cat1': 1, 'Cat2': 3}
        assert 'TopCategories' not in user
        path, users_data = store._find_user_file('u1')
        assert path is not None and users_data is not None
        assert 'TopCategories' not in users_data['u1']


def test_gift_updates_post_and_user():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = MeshStore(tmpdir)
        db = MeshDB(store)
        db.create_user('u1', 'male')
        db.create_user('creator', 'female')
        db.create_post('p1', 'creator', ['Cat1'])
        db.record_engagement('u1', 'p1', 'gift', gift_amount=5)
        post = store.load_post('p1')
        assert post['gift_number'] == 1
        assert post['Score'] == 5
        user = store.load_user('u1')
        assert user['CategoryScores'] == {'Cat1': 5}
