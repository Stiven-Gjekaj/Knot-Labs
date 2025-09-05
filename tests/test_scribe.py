from mesh import Mesh
from scribe import Scribe


def test_search_text_and_tag(tmp_path):
    m = Mesh(str(tmp_path / "data.json"))
    pid = m.create_post("travel_to_paris.mp4", ["travel"])
    s = Scribe(m)
    text_results = s.search("paris")
    tag_results = s.search("#travel")
    assert text_results[0][0] == pid
    assert tag_results[0][0] == pid
