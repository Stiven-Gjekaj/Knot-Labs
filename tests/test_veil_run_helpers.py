from __future__ import annotations

import numpy as np
import sys
import types
import importlib.machinery


def test_strip_prompt_prefix_and_fuse_scores() -> None:
    if 'cv2' not in sys.modules:
        cv2_stub = types.ModuleType("cv2")
        cv2_stub.__spec__ = importlib.machinery.ModuleSpec("cv2", loader=None)
        sys.modules['cv2'] = cv2_stub
    import veil.run as vr  # type: ignore

    # _strip_prompt_prefix
    assert vr._strip_prompt_prefix("a video about trains", "video") == "trains"
    assert vr._strip_prompt_prefix("a video of train tracks", "video") == "train tracks"
    assert vr._strip_prompt_prefix("a photo of trains", "photo") == "trains"

    # fuse_scores behavior: normalized weighted sum
    v = np.array([0.2, 0.8, 0.4], dtype=np.float32)
    s = np.array([0.5, 0.5, 0.5], dtype=np.float32)
    e = np.array([0.1, 0.3, 0.9], dtype=np.float32)
    out = vr.fuse_scores(v, s, e, w_video=0.5, w_speech=0.3, w_audio=0.2)
    # Should have same shape and higher weight on visual dimension
    assert out.shape == v.shape
    # Visual top index should dominate
    assert int(out.argmax()) == int(v.argmax())

