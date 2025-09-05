"""Hash helpers used by Veil."""
from __future__ import annotations

import hashlib


def hash_bytes(data: bytes) -> int:
    return int.from_bytes(hashlib.sha256(data).digest(), "big")


def hash_text(text: str) -> int:
    return hash_bytes(text.encode("utf-8"))
