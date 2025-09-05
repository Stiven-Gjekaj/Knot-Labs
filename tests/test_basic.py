import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from knot.mesh.db import MeshDB
from knot.veil.analyzer import analyze_media
from knot.drift import ranker


def test_user_post(tmp_path):
    mesh = MeshDB(tmp_path)
    mesh.create_user("u1")
    p = tmp_path / "media.txt"
    p.write_text("hello")
    mesh.create_post("p1", "u1", str(p))
    cats = analyze_media(str(p), mesh.get_master_categories())["categories"]
    mesh.set_post_categories("p1", cats)
    score1 = ranker.rank_post(mesh, "p1")
    assert mesh.get_post("p1")["categories"] == cats
    mesh.increment_engagement("p1", "u2", "view")
    score2 = ranker.rank_post(mesh, "p1")
    assert score2 > score1
    viewer = mesh.get_user("u2")
    assert viewer["viewer_stats"]["u1"]["views"] == 1
    assert viewer["seen_posts"] == ["p1"]


def test_master_category_dedup(tmp_path):
    (tmp_path / "mastercategories.txt").write_text("a\na\nb\n")
    mesh = MeshDB(tmp_path)
    cats = mesh.get_master_categories()
    assert cats == ["a", "b"]
    assert (tmp_path / "mastercategories.txt").read_text().splitlines() == ["a", "b"]

