import os
import warnings
from typing import List, Optional
import numpy as np
import cv2  # type: ignore
from PIL import Image
import torch


def load_categories(spec: str, modality: Optional[str] = None, master_delim: str = "|") -> List[str]:
    """Load categories from comma string or file path.

    If the file contains rows with a master delimiter (default "|"),
    and a modality is provided ("video" or "photo"), picks the corresponding
    column per line: column 0 for video, column 1 for photo. Falls back to
    the whole line if the delimiter is not present.
    """
    if os.path.isfile(spec):
        base = os.path.basename(spec)
        if base in {"phcategories.txt", "vdcategories.txt"}:
            warnings.warn(
                (
                    f"Deprecated labels file '{base}'. Use 'Knot-Mesh/data/categories/mastercategories.txt' "
                    "or a two-column labels file with 'video | photo' per line."
                ),
                category=UserWarning,
                stacklevel=2,
            )
        with open(spec, 'r', encoding='utf-8') as f:
            rows = [line.strip() for line in f if line.strip()]
        def _strip_prefix(label: str, mod: str) -> str:
            l = label.strip()
            prefixes = (
                ("video", [
                    "a video of ",
                    "a video about ",
                    "video of ",
                    "video about ",
                ]),
                ("photo", [
                    "a photo of ",
                    "photo of ",
                ]),
            )
            for m, pres in prefixes:
                if mod == m:
                    for p in pres:
                        if l.lower().startswith(p):
                            return l[len(p):].strip()
            return l

        if modality and any(master_delim in r for r in rows):
            col_idx = 0 if modality == "video" else 1
            cats: List[str] = []
            for r in rows:
                if master_delim in r:
                    parts = [p.strip() for p in r.split(master_delim)]
                    # Safely pick column by index or fallback to last available
                    pick = parts[col_idx] if col_idx < len(parts) else parts[-1]
                    cats.append(_strip_prefix(pick, modality))
                else:
                    cats.append(_strip_prefix(r, modality))
            return cats
        else:
            # No master delimiter present — optionally strip common prefixes
            if modality:
                return [_strip_prefix(r, modality) for r in rows]
            return rows
    else:
        return [c.strip() for c in spec.split(',') if c.strip()]


def normalize_tensor(x: torch.Tensor) -> torch.Tensor:
    return x / x.norm(dim=-1, keepdim=True)


def min_max_norm(arr: np.ndarray) -> np.ndarray:
    if arr.size == 0:
        return arr
    min_v = arr.min()
    max_v = arr.max()
    if max_v - min_v < 1e-8:
        return np.zeros_like(arr)
    return (arr - min_v) / (max_v - min_v)


def pil_from_np(arr: np.ndarray) -> Image.Image:
    if arr.ndim == 3 and arr.shape[2] == 3:
        arr = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(arr)


def sample_frames_cv2(path: str, max_frames: int = 16, min_gap_sec: float = 0.5) -> List[Image.Image]:
    """Sample frames from ``path`` using random access seeks.

    Instead of iterating through every frame, compute the frame indices to
    sample based on ``min_gap_sec`` and jump directly to each index with
    ``CAP_PROP_POS_FRAMES``. This avoids decoding intermediate frames while
    ensuring the temporal gap between sampled frames respects ``min_gap_sec``.
    """
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    gap = max(int(fps * min_gap_sec), 1)

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if frame_count > 0:
        indices = list(range(0, frame_count, gap))[:max_frames]
    else:
        indices = [i * gap for i in range(max_frames)]

    frames: List[Image.Image] = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(pil_from_np(frame))

    cap.release()
    return frames
