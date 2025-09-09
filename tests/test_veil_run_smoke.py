from __future__ import annotations

import os
import sys
from typing import Any

import numpy as np
import types


def _add_veil_to_path() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    veil_src = os.path.join(root, "Veil", "src")
    if veil_src not in sys.path:
        sys.path.insert(0, veil_src)


def test_veil_run_smoke_video_only(tmp_path, monkeypatch, capsys):
    _add_veil_to_path()

    # Provide a minimal stub for the 'clip' package before importing veil.run
    if 'clip' not in sys.modules:
        stub = types.SimpleNamespace()
        def _tok(prompts, truncate=False):
            import torch
            return torch.zeros((len(prompts), 77), dtype=torch.long)
        def _load(name, device='cpu'):
            class _M:
                def encode_text(self, tokens):
                    import torch
                    return torch.ones((tokens.shape[0], 512), dtype=torch.float32)
                def encode_image(self, imgs):
                    import torch
                    return torch.ones((imgs.shape[0], 512), dtype=torch.float32)
            return _M(), None
        stub.tokenize = _tok
        stub.load = _load
        sys.modules['clip'] = stub  # type: ignore

    import veil.run as vr  # type: ignore

    # Create a tiny master file with two labels
    master = tmp_path / "master.txt"
    master.write_text(
        "\n".join([
            "a video about trains | a photo of trains",
            "a video about cats | a photo of cats",
        ]),
        encoding="utf-8",
    )

    class _DummyModel:
        def encode_text(self, tokens):
            import torch
            return torch.ones((tokens.shape[0], 512), dtype=torch.float32)
        def encode_image(self, imgs):
            import torch
            return torch.ones((imgs.shape[0], 512), dtype=torch.float32)

    def _fake_get_clip_model(model_name: str, device: str = "cpu"):
        return _DummyModel(), None

    def _fake_classify_video_clip(video_path: str, labels: list[str], **_: Any):
        # Give higher score to labels containing 'train'
        scores = np.asarray([0.9 if "train" in l else 0.1 for l in labels], dtype=np.float32)
        return {"categories": labels, "scores": scores, "frame_count": 1}

    monkeypatch.setattr(vr, "get_clip_model", _fake_get_clip_model)
    monkeypatch.setattr(vr, "classify_video_clip", _fake_classify_video_clip)

    # Prepare argv and dummy video path
    dummy_video = tmp_path / "dummy.mp4"
    dummy_video.write_bytes(b"not a real video")

    argv = [
        "veil.run",
        "--mode", "video",
        "--video", str(dummy_video),
        "--master_labels_file", str(master),
        "--use_ann", "false",
        "--use_whisper", "false",
        "--w_video", "1.0",
        "--w_speech", "0.0",
        "--w_audio", "0.0",
        "--topk", "2",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    vr.main()
    out = capsys.readouterr().out
    # Ensure predictions printed and contain the expected label order (trains first)
    assert "Predictions:" in out
    assert "trains" in out
