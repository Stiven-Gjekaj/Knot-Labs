from __future__ import annotations

import os
import sys
import types
import numpy as np


def _add_veil_to_path() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    veil_src = os.path.join(root, "Veil", "src")
    if veil_src not in sys.path:
        sys.path.insert(0, veil_src)


def test_veil_run_ann_and_yamnet_path(tmp_path, monkeypatch, capsys):
    _add_veil_to_path()

    # Stub 'clip' before importing veil.run (avoid heavy deps)
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

    # Create a tiny master file
    master = tmp_path / "master.txt"
    master.write_text(
        "\n".join([
            "a video about trains | a photo of trains",
            "a video about cats | a photo of cats",
        ]),
        encoding="utf-8",
    )

    # Stub ANN: 2 labels, 4-dim embeddings
    D = 4
    E = np.stack([
        np.array([1, 0, 0, 0], dtype=np.float32),  # trains
        np.array([0, 1, 0, 0], dtype=np.float32),  # cats
    ], axis=0)
    labels = ["trains", "cats"]

    def _fake_ensure_index(master_path: str, out_dir: str, model_name: str, mode: str):
        return {"emb": E, "labels": labels, "index": None, "npz": str(tmp_path / 'dummy.npz')}

    # Return 2 frames embeddings and pooled
    frames_emb = np.stack([
        np.array([0.9, 0.1, 0, 0], dtype=np.float32),
        np.array([0.8, 0.2, 0, 0], dtype=np.float32),
    ], axis=0)
    pooled = np.array([[0.85, 0.15, 0, 0]], dtype=np.float32)

    def _fake_embed_video(video_path: str, model_name: str, frames: int, device: str):
        return frames_emb, pooled

    def _fake_ann_search(Ea, la, q, k: int, index=None):
        # Return top-2 indices (intentionally reversed to exercise rerank)
        return [(la[1], float(0.51), 1), (la[0], float(0.49), 0)]

    def _fake_rerank_with_frames(top_idx, Ea, frames_emb_local, agg: str = 'mean'):
        # Rerank to prefer index 0 with higher score
        return [(0, 0.9), (1, 0.1)]

    # Stub YAMNet mapping: produce label scores favoring cats
    def _fake_run_yamnet(path: str, topn: int = 10):
        class R:
            top_events = [("meow", 0.9)]
        return R()

    def _fake_score_events_to_labels(path: str, lbls, model_name: str, topn_events: int = 15, label_emb=None):
        return {lbls[0]: 0.2, lbls[1]: 0.8}

    # Apply monkeypatches
    monkeypatch.setattr(vr, "ensure_index", _fake_ensure_index)
    monkeypatch.setattr(vr, "_embed_video_api", _fake_embed_video)
    monkeypatch.setattr(vr, "ann_search", _fake_ann_search)
    monkeypatch.setattr(vr, "rerank_with_frames", _fake_rerank_with_frames)
    # Inject fake yamnet module so veil.run import finds our stubs
    import types as _types
    fake_yam = _types.SimpleNamespace(run_yamnet=_fake_run_yamnet, score_events_to_labels=_fake_score_events_to_labels)
    sys.modules['veil.fusion.yamnet_events'] = fake_yam  # type: ignore

    # Dummy video path
    dummy_video = tmp_path / "dummy.mp4"
    dummy_video.write_bytes(b"not a real video")

    # Drive veil.run via argv
    argv = [
        "veil.run",
        "--mode", "video",
        "--video", str(dummy_video),
        "--master_labels_file", str(master),
        "--use_ann", "true",
        "--ann_k", "2",
        "--ann_agg", "mean",
        "--use_whisper", "false",
        "--w_video", "0.9",
        "--w_speech", "0.0",
        "--w_audio", "0.1",
        "--topk", "2",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    vr.main()
    out = capsys.readouterr().out

    # Expect ANN rerank to make trains rank first
    assert "Predictions:" in out
    pred_line = next((ln for ln in out.splitlines() if ln.startswith("Predictions:")), "")
    assert "trains" in pred_line.split(":", 1)[1]
    # Audio backend should be YAMNet
    assert "Audio (YAMNet) top-k:" in out

