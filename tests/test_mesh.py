from mesh import Mesh


def test_mesh_crud(tmp_path):
    path = tmp_path / "data.json"
    m = Mesh(str(path))
    uid = m.add_user("Alice")
    assert uid
    pid = m.create_post("video.mp4", ["fun"])
    assert pid
    post = m.get_post(pid)
    assert post["path"] == "video.mp4"
    m.increment(pid, "likes")
    m.update_post(pid, comments=1)
    results = m.search(tag="fun")
    assert any(r[0] == pid for r in results)
