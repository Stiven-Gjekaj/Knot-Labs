from __future__ import annotations

import sys
import types
import importlib.machinery


def test_chunk_text_basic() -> None:
    cv2_stub = types.ModuleType("cv2")
    cv2_stub.__spec__ = importlib.machinery.ModuleSpec("cv2", loader=None)
    sys.modules['cv2'] = cv2_stub
    class Tok:
        def encode(self, text):
            return list(range(len(text.split())))
        def decode(self, ids):
            return " ".join(["w"] * len(ids))
    clip_stub = types.SimpleNamespace(_tokenizer=Tok())
    sys.modules['clip'] = clip_stub  # type: ignore
    sys.modules.pop('veil.clip_utils', None)
    sys.modules.pop('veil.audio_whisper', None)
    from veil.audio_whisper import _chunk_text  # type: ignore

    text = " ".join(["train"] * 1000)
    chunks = _chunk_text(text, max_tokens=77)
    assert len(chunks) > 1
    assert all(isinstance(c, str) and c for c in chunks)

