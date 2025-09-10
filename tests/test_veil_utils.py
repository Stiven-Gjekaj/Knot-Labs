from __future__ import annotations

import os
import numpy as np
import sys
import types
import importlib.machinery


def test_min_max_norm_and_load_categories() -> None:
    if 'cv2' not in sys.modules:
        cv2_stub = types.ModuleType("cv2")
        cv2_stub.__spec__ = importlib.machinery.ModuleSpec("cv2", loader=None)
        sys.modules['cv2'] = cv2_stub
    from veil.utils import min_max_norm, load_categories  # type: ignore

    arr = np.array([2.0, 4.0, 6.0], dtype=np.float32)
    out = min_max_norm(arr)
    np.testing.assert_allclose(out, np.array([0.0, 0.5, 1.0], dtype=np.float32))

    # Load the master file and ensure prefixes are stripped by modality
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    master = os.path.join(root, "Mesh", "mastercategories.txt")
    vids = load_categories(master, modality="video")
    photos = load_categories(master, modality="photo")

    assert len(vids) == len(photos) > 0
    assert not vids[0].lower().startswith("a video ")
    assert not photos[0].lower().startswith("a photo ")

