import tempfile

from mesh_db import MeshDB, MeshStore


def test_preferred_categories_tracked():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = MeshStore(tmpdir)
        db = MeshDB(store)
        db.create_user('u1', 'male')
        db.create_user('creator', 'female')
        db.create_post('p1', 'creator', ['Cat1'])
        db.create_post('p2', 'creator', ['Cat2'])
        db.create_post('p3', 'creator', ['Cat3'])
        db.record_engagement('u1', 'p1', 'like')  # Cat1 +1
        db.record_engagement('u1', 'p2', 'share')  # Cat2 +3
        db.record_engagement('u1', 'p3', 'comment')  # Cat3 +2
        user = store.load_user('u1')
        assert user['CategoryScores'] == {'Cat1': 1, 'Cat2': 3, 'Cat3': 2}
        assert user['PreferredCategories'] == ['Cat2', 'Cat3', 'Cat1']


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


def test_post_age_tracked():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = MeshStore(tmpdir)
        db = MeshDB(store)
        db.create_user('u1', 'male')
        db.create_user('creator', 'female')
        db.create_post('p1', 'creator', ['Cat1'])
        db.record_engagement('u1', 'p1', 'like')
        # make post appear 2 hours older
        path, posts_data = store._find_post_file('p1')
        assert path is not None and posts_data is not None
        posts_data['p1']['created_at'] -= 7200
        store._atomic_write(path, posts_data)
        post = store.load_post('p1')
        assert post['Age'] >= 2
