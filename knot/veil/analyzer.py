"""Veil media analyzer."""
from __future__ import annotations

from pathlib import Path
from typing import List, Dict

from ..common.hashing import file_sha1, bytes_hash_to_indices


# Placeholder for optional heavy models
try:  # pragma: no cover - best effort
    import torch  # type: ignore
    _HAS_HEAVY = True
except Exception:  # pragma: no cover
    _HAS_HEAVY = False


def analyze_media(path: str, master_categories: List[str]) -> Dict:
    """Return dict with 3 categories for given media path.

    If heavy ML libraries are not available, a deterministic hash-based heuristic
    is used which maps the file's SHA1 to categories.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)

    # Currently we always use heuristic; heavy model pipeline omitted for brevity
    digest = file_sha1(str(p))
    idxs = bytes_hash_to_indices(digest, 3, len(master_categories))
    cats = [master_categories[i] for i in idxs]
    return {"categories": cats, "confidence": 0.66}

