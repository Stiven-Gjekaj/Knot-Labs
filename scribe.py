"""Scribe module: text and tag search interface."""
from __future__ import annotations
from typing import List, Tuple, Dict

from mesh import Mesh


class Scribe:
    """Searches posts stored in Mesh."""

    def __init__(self, mesh: Mesh) -> None:
        self.mesh = mesh

    def search(self, query: str) -> List[Tuple[str, Dict]]:
        """Search by text or tag (#tag)."""
        query = query.strip().lower()
        if query.startswith("#"):
            return self.mesh.search(tag=query[1:])
        return self.mesh.search(text=query)
