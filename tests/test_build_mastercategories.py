from __future__ import annotations

import os
from typing import List, Tuple

from Mesh.tools.build_mastercategories import normalize, unique_dedup, build_and_write


def test_normalize_basic():
    # '&' replaced with 'and'; punctuation removed, spaces squashed
    assert normalize("Hip-Hop & R&B!") == "hip hop and r and b"
    assert normalize("New   York, City") == "new york city"


def test_unique_dedup_merges_similar():
    cands: List[Tuple[str, str]] = [
        ("MUSIC", normalize("hip hop")),
        ("MUSIC", normalize("hip-hop")),  # identical after normalize
        ("MUSIC", normalize("r and b")),
    ]
    out = unique_dedup(cands, threshold=93.0)
    # First two should dedup into one; third remains
    labels = [c for _, c in out]
    assert "hip hop" in labels
    assert labels.count("hip hop") == 1
    assert any(l for l in labels if l != "hip hop")


def test_build_and_write_count(tmp_path):
    out = tmp_path / "master.txt"
    stats = build_and_write(out_path=str(out), target_count=50)
    assert out.is_file()
    lines = [ln.strip() for ln in out.read_text(encoding="utf-8").splitlines() if ln.strip()]
    # Expect final equals the number of lines written
    assert stats["final"] == len(lines)
    assert 10 <= stats["final"] <= 50
    # Format check
    assert lines[0].startswith("a video about ") and " | a photo of " in lines[0]
