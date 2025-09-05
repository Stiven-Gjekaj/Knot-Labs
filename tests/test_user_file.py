from mesh import Mesh


def test_add_user_custom_id(tmp_path):
    user_id = "demo-user"
    path = tmp_path / f"mesh_data_{user_id}.json"
    m = Mesh(str(path))
    returned = m.add_user("runner", uid=user_id)
    assert returned == user_id
    assert user_id in m._load()["users"]
