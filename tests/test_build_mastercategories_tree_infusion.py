from __future__ import annotations

import json
import os

from Mesh.tools.build_mastercategories import build_tree_and_write


def test_build_tree_and_write(tmp_path):
    out_master = tmp_path / "master.txt"
    out_tree = tmp_path / "tree.json"
    stats = build_tree_and_write(out_path=str(out_master), tree_out=str(out_tree), mesos=1, micros=1)
    # Files exist
    assert out_master.is_file(), "mastercategories output not written"
    assert out_tree.is_file(), "tree output not written"
    # Parse tree
    data = json.loads(out_tree.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    # Check master format
    lines = [ln.strip() for ln in out_master.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert lines and lines[0].startswith("a video about ") and " | a photo of " in lines[0]
    assert int(stats.get("final", 0)) == len(lines)

