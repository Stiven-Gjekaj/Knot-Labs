from __future__ import annotations

import os
import sys
import numpy as np


def _add_veil_to_path() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    veil_src = os.path.join(root, "Veil", "src")
    if veil_src not in sys.path:
        sys.path.insert(0, veil_src)


def test_strip_prompt_prefix_and_fuse_scores() -> None:
    _add_veil_to_path()
    import veil.run as vr  # type: ignore

    # _strip_prompt_prefix
    assert vr._strip_prompt_prefix("a video about trains", "video") == "trains"
    assert vr._strip_prompt_prefix("a video of train tracks", "video") == "train tracks"
    assert vr._strip_prompt_prefix("a photo of trains", "photo") == "trains"

    # fuse_scores behavior: normalized weighted sum
    v = np.array([0.2, 0.8, 0.4], dtype=np.float32)
    s = np.array([0.5, 0.5, 0.5], dtype=np.float32)
    e = np.array([0.1, 0.3, 0.9], dtype=np.float32)
    out = vr.fuse_scores(v, s, e, w_video=0.7, w_speech=0.2, w_audio=0.1)
    # Should have same shape and higher weight on visual dimension
    assert out.shape == v.shape
    # Visual top index should dominate
    assert int(out.argmax()) == int(v.argmax())

