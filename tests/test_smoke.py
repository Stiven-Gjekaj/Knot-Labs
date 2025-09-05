from __future__ import annotations

from pathlib import Path

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from demo import CLI


def test_smoke(tmp_path):
    root = tmp_path
    cli = CLI(root)
    mesh = cli.mesh

    # create user and set active
    cli.cmd_labs(["alice"])
    assert mesh.get_active_user_id() == "alice"

    # create a post
    media = tmp_path / "a.txt"
    media.write_text("hello")
    cli.cmd_post(["post1", str(media)])
    post = mesh.get_post("post1")
    assert len(post.categories) == 3
    for c in post.categories:
        assert c in mesh.master_categories

    # like engagement raises score
    before = post.rank_score
    cli.cmd_like(["post1"])
    post = mesh.get_post("post1")
    assert post.engagement["likes"] == 1
    assert post.rank_score > before

    # search by category
    interp = cli.scribe.interpret_query(post.categories[0])
    results = cli.scribe.search_posts(interp, 5)
    assert any(p.post_id == "post1" for p in results)
