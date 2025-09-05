"""Veil: simple categorizer assigning exactly 3 categories."""
from __future__ import annotations

import random
from pathlib import Path
from typing import List

from knot.common.hashing import hash_bytes, hash_text


class Veil:
    def __init__(self, mesh):
        self.mesh = mesh

    def analyze(self, media_path: Path) -> dict:
        """Return three categories based on file content or path."""
        cats = self.mesh.master_categories
        if media_path.exists():
            data = media_path.read_bytes()
            seed = hash_bytes(data)
        else:
            seed = hash_text(media_path.as_posix())
        rnd = random.Random(seed)
        categories = rnd.sample(cats, 3)
        return {"categories": categories, "confidence": 1.0}
