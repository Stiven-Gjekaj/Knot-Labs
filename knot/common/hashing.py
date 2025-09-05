"""Hash helpers for deterministic category selection."""
from __future__ import annotations

import hashlib


def file_sha1(path: str) -> str:
    """Return SHA1 hex digest for a file."""
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def bytes_hash_to_indices(hex_digest: str, n_choices: int, modulo: int) -> list[int]:
    """Map hash hex digest to ``n_choices`` indices under ``modulo``.

    The mapping is deterministic and ensures distinct indices by walking the digest.
    """
    ints = []
    for i in range(0, len(hex_digest), 8):
        if len(ints) >= n_choices:
            break
        chunk = hex_digest[i : i + 8]
        idx = int(chunk, 16) % modulo
        if idx not in ints:
            ints.append(idx)
    # If digest produced duplicates, fill remaining with sequential numbers
    next_idx = 0
    while len(ints) < n_choices:
        if next_idx not in ints:
            ints.append(next_idx)
        next_idx += 1
    return ints

