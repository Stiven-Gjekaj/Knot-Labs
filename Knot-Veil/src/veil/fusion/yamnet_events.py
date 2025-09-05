from __future__ import annotations

"""
YAMNet event scoring and mapping to master label prompts using CLIP text encoder.

This module:
- Loads YAMNet from TensorFlow Hub (lazy singleton)
- Extracts audio from video with ffmpeg (reuse helpers)
- Computes per-class probabilities, averages over time
- Converts top events to a weighted text embedding and maps to label prompts via CLIP
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import os
import numpy as np
import tensorflow as tf  # type: ignore
import tensorflow_hub as hub  # type: ignore
import librosa  # type: ignore
import torch

from ..audio_whisper import _extract_wav_ffmpeg, _read_wav_to_np
from ..utils import normalize_tensor
from ..clip_utils import clip, get_clip_model


_yamnet_layer: Optional[hub.KerasLayer] = None
_yamnet_labels: Optional[List[str]] = None


@dataclass
class YamnetResult:
    event_scores: np.ndarray  # [521]
    class_names: List[str]
    top_events: List[Tuple[str, float]]  # sorted desc by score


def _load_yamnet() -> Tuple[hub.KerasLayer, List[str]]:
    global _yamnet_layer, _yamnet_labels
    # Force TensorFlow to run on CPU
    try:
        tf.config.set_visible_devices([], "GPU")
    except Exception:
        pass
    if _yamnet_layer is None:
        _yamnet_layer = hub.KerasLayer("https://tfhub.dev/google/yamnet/1")
    if _yamnet_labels is None:
        assert _yamnet_layer is not None
        # Label CSV path is provided by the model object
        class_map_path = _yamnet_layer.class_map_path().numpy().decode("utf-8")
        with tf.io.gfile.GFile(class_map_path, "r") as f:
            # CSV has header: index,mid,display_name
            lines = [ln.strip() for ln in f if ln.strip()]
        names: List[str] = []
        for i, ln in enumerate(lines):
            if i == 0 and ln.lower().startswith("index,"):
                continue
            parts = ln.split(",")
            # display_name is last column; keep as-is
            names.append(parts[-1])
        _yamnet_labels = names
    return _yamnet_layer, _yamnet_labels  # type: ignore[return-value]


def _load_audio_mono16k(path: str) -> np.ndarray:
    """Load audio from file into mono float32 @16k using librosa.

    If the input is a video file, first extract a temporary wav via ffmpeg.
    """
    src = path
    cleanup = None
    try:
        # Try direct librosa first; if it fails, extract wav via ffmpeg
        y, sr = librosa.load(src, sr=16000, mono=True)
        return y.astype(np.float32)
    except Exception:
        wav_path, _ = _extract_wav_ffmpeg(path, sr=16000)
        cleanup = wav_path
        try:
            audio, sr = _read_wav_to_np(wav_path)
            return audio.astype(np.float32)
        finally:
            if cleanup and os.path.exists(cleanup):
                try:
                    os.unlink(cleanup)
                except OSError:
                    pass


def run_yamnet(audio_or_video_path: str, topn: int = 10) -> YamnetResult:
    """Run YAMNet on an audio or video file and return averaged class scores.

    Returns topn (name, score) tuples sorted by score descending.
    """
    layer, class_names = _load_yamnet()
    wav = _load_audio_mono16k(audio_or_video_path)
    # YAMNet expects a [n] float32 waveform at 16k. It returns: scores [frames, 521]
    scores, embeddings, spectrogram = layer(wav)
    scores_np = scores.numpy()
    mean_scores = scores_np.mean(axis=0)  # [521]
    idx_desc = np.argsort(mean_scores)[::-1]
    top = [
        (class_names[i], float(mean_scores[i]))
        for i in idx_desc[:topn]
    ]
    return YamnetResult(event_scores=mean_scores, class_names=class_names, top_events=top)


def score_events_to_labels(
    audio_or_video_path: str,
    label_prompts: List[str],
    *,
    model_name: str = "ViT-B/32",
    topn_events: int = 15,
    label_emb: Optional[torch.Tensor] = None,
) -> Dict[str, float]:
    """Map YAMNet event evidence into scores over label prompts using CLIP.

    Approach: take top-N YAMNet event names, encode them with CLIP text encoder,
    compute a weighted average event embedding using YAMNet probabilities,
    then return cosine similarity between label prompt embeddings and the
    weighted event embedding.
    """
    try:
        yres = run_yamnet(audio_or_video_path, topn=topn_events)
    except Exception:
        # Fail open: return zeros
        return {p: 0.0 for p in label_prompts}

    device = "cpu"
    model, _ = get_clip_model(model_name, device=device)

    if label_emb is None:
        # Prepare label embeddings
        with torch.no_grad():
            label_tokens = clip.tokenize(label_prompts).to(device)
            label_emb = normalize_tensor(model.encode_text(label_tokens).float())  # [L, D]
    else:
        label_emb = normalize_tensor(label_emb.to(device).float())

    # Prepare weighted event embedding
    ev_names = [name for (name, s) in yres.top_events]
    ev_weights = np.array([s for (_, s) in yres.top_events], dtype=np.float32)
    if ev_weights.sum() <= 0:
        return {p: 0.0 for p in label_prompts}

    ev_prompts = [f"a sound of {n}" for n in ev_names]
    with torch.no_grad():
        ev_tokens = clip.tokenize(ev_prompts).to(device)
        ev_emb = normalize_tensor(model.encode_text(ev_tokens).float())  # [E, D]
    # Weighted average event embedding
    w = torch.from_numpy(ev_weights).to(ev_emb.device).unsqueeze(1)  # [E,1]
    w = w / w.sum()
    ev_avg = (w * ev_emb).sum(dim=0, keepdim=True)  # [1, D]

    with torch.no_grad():
        sims = (label_emb @ ev_avg.T).cpu().numpy().reshape(-1)  # [L]

    return {label_prompts[i]: float(sims[i]) for i in range(len(label_prompts))}
