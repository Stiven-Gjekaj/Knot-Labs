from __future__ import annotations

import json
from Mesh.tools import build_mastercategories as bmc


def test_build_tree_by_total_count(tmp_path, monkeypatch):
    # Avoid network calls for deterministic tests
    monkeypatch.setattr(bmc, "_fetch_wikipedia_subcats", lambda *_args, **_kw: [])
    out_master = tmp_path / "master.txt"
    out_tree = tmp_path / "tree.json"
    # Request N micros via total; should write files and produce <= N lines
    N = 20
    stats = bmc.build_tree_and_write(out_path=str(out_master), tree_out=str(out_tree), total=N)
    assert out_master.is_file(), "mastercategories output not written"
    assert out_tree.is_file(), "tree output not written"
    data = json.loads(out_tree.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    lines = [ln.strip() for ln in out_master.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) > 0
    assert len(lines) <= N
    assert int(stats.get("final", 0)) == len(lines)
    # Format sanity
    assert lines[0].startswith("a video about ") and " | a photo of " in lines[0]
