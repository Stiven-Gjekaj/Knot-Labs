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

