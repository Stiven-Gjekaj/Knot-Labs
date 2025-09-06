from __future__ import annotations

import os
import sys


def _add_veil_to_path() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    veil_src = os.path.join(root, "Veil", "src")
    if veil_src not in sys.path:
        sys.path.insert(0, veil_src)


def test_chunk_text_basic() -> None:
    _add_veil_to_path()
    from veil.audio_whisper import _chunk_text  # type: ignore

    text = " ".join(["train"] * 1000)
    chunks = _chunk_text(text, max_tokens=77)
    assert len(chunks) > 1
    assert all(isinstance(c, str) and c for c in chunks)

