import random
from mesh import Mesh
from veil import Veil
from scribe import Scribe
from drift import Drift


def test_end_to_end(tmp_path):
    random.seed(0)
    m = Mesh(str(tmp_path / "data.json"))
    v = Veil(categories=["music", "fun", "travel"])
    s = Scribe(m)
    d = Drift()
    path = "fun_music_clip.mp4"
    tags = v.classify(path)
    pid = m.create_post(path, tags)
    m.increment(pid, "likes")
    results = s.search("#music")
    assert results and results[0][0] == pid
    ranked = d.rank(dict(results))
    assert ranked and ranked[0][0] == pid and ranked[0][2] > 0
