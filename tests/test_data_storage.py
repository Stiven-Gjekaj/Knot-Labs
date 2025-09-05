from mesh_db import MeshDB, MeshStore


def test_users_and_posts_saved_in_data_folder(tmp_path):
    store = MeshStore(tmp_path)
    db = MeshDB(store)
    # create user and post
    db.create_user('u1', 'male')
    db.create_post('p1', 'u1', ['Cat1', 'Cat2', 'Cat3'])
    users_dir = tmp_path / 'data' / 'Users'
    posts_dir = tmp_path / 'data' / 'Posts'
    user_files = list(users_dir.glob('*.json'))
    post_files = list(posts_dir.glob('*.json'))
    assert user_files, 'user file should be stored in data/Users'
    assert post_files, 'post file should be stored in data/Posts'
    # ensure mesh_data json files are not created
    assert not list(tmp_path.glob('mesh_data*.json'))
