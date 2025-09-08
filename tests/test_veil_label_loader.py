from __future__ import annotations

import os
import sys


def _add_veil_to_path() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    veil_src = os.path.join(root, "Veil", "src")
    if veil_src not in sys.path:
        sys.path.insert(0, veil_src)


def test_load_master_and_select_labels() -> None:
    _add_veil_to_path()
    from veil.fusion.label_loader import load_master_labels, select_labels  # type: ignore

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    master = os.path.join(root, "Mesh", "mastercategories.txt")
    m = load_master_labels(master, expect_exact_count=False)

    # Basic sanity: non-empty, correct prefixes
    assert len(m.video_labels) > 0
    assert len(m.photo_labels) == len(m.video_labels)
    assert m.video_labels[0].startswith("a video about ")
    assert m.photo_labels[0].startswith("a photo of ")

    vids = select_labels(m, "video")
    photos = select_labels(m, "photo")
    assert vids == m.video_labels
    assert photos == m.photo_labels

