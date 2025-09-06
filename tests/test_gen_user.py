import json
import os
from Mesh.tools.gen_user import make_user, save_user


def test_make_user_structure():
    u = make_user("alice")
    assert u["username"] == "alice"
    assert isinstance(u["userID"], str)
    assert isinstance(u["SeenPosts"], list)
    assert isinstance(u["ViewerScore"], dict)


def test_save_user(tmp_path):
    u = make_user("bob")
    path = save_user(u, str(tmp_path))
    assert os.path.isfile(path)
    data = json.load(open(path, 'r', encoding='utf-8'))
    assert data["userID"] == u["userID"]

