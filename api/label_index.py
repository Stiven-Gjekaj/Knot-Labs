from __future__ import annotations

import os
from typing import List, Tuple, Optional, Dict, Any

import numpy as np
import torch

try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover
    faiss = None  # type: ignore

import clip  # type: ignore


def _normalize(x: torch.Tensor) -> torch.Tensor:
    return torch.nn.functional.normalize(x, dim=-1, eps=1e-9)


def _read_labels(master_path: str, mode: str = "video") -> List[str]:
    labels: List[str] = []
    if not os.path.isfile(master_path):
        return labels
    with open(master_path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if "|" in s:
                # format: video-prompt | photo-prompt
                parts = [p.strip() for p in s.split("|", 1)]
                labels.append(parts[0] if mode == "video" else parts[-1])
            else:
                # plain category -> convert to CLIP-style prompt
                labels.append(f"a video of {s}" if mode == "video" else f"a photo of {s}")
    return labels


def _templates_for_mode(mode: str) -> List[str]:
    if mode == "video":
        return [
            "a video of a {}",
            "a video of {}",
            "a clip of a {}",
            "a recording of a {}",
        ]
    else:
        return [
            "a photo of a {}",
            "a photo of {}",
            "an image of a {}",
            "a picture of a {}",
        ]


def _strip_prompt_prefix(label: str, mode: str) -> str:
    l = label.strip()
    low = l.lower()
    prefixes = (
        ("video", ["a video of ", "a video about ", "video of ", "video about ", "a clip of ", "a recording of "]),
        ("photo", ["a photo of ", "photo of ", "an image of ", "a picture of "]),
    )
    for m, pres in prefixes:
        if mode == m:
            for p in pres:
                if low.startswith(p):
                    return l[len(p):].strip()
    return l


def _encode_texts_batched(model, texts: List[str], device: str, batch_size: Optional[int] = None) -> torch.Tensor:
    """Encode a list of texts with CLIP in smaller batches to avoid OOM.

    Returns a LxD float32 tensor on CPU, normalized per row.
    """
    bs = int(os.environ.get("KNOT_LABEL_BATCH", os.environ.get("VEIL_LABEL_BATCH", "128")))
    if batch_size is not None:
        bs = int(batch_size)
    outputs: List[torch.Tensor] = []
    for i in range(0, len(texts), max(1, bs)):
        chunk = texts[i : i + max(1, bs)]
        tokens = clip.tokenize(chunk, truncate=True).to(device)
        with torch.no_grad():
            emb = _normalize(model.encode_text(tokens).float())
        outputs.append(emb.cpu())
    if not outputs:
        return torch.zeros((0, 1), dtype=torch.float32)
    return torch.cat(outputs, dim=0)


def build_label_embeddings(master_path: str, model_name: str = "ViT-B/32", mode: str = "video", device: str = "cpu") -> Tuple[np.ndarray, List[str]]:
    raw = _read_labels(master_path, mode=mode)
    if not raw:
        return np.zeros((0, 1), dtype=np.float32), []
    # Convert any prompts to base labels for multi-template ensembling
    base_labels = [_strip_prompt_prefix(s, mode) for s in raw]
    templates = _templates_for_mode(mode)
    model, _pre = clip.load(model_name, device=device)
    emb_accum: Optional[torch.Tensor] = None
    for tmpl in templates:
        prompts = [tmpl.format(c) for c in base_labels]
        emb = _encode_texts_batched(model, prompts, device=device)
        emb_accum = emb if emb_accum is None else (emb_accum + emb)
    assert emb_accum is not None
    emb_avg = _normalize(emb_accum / float(len(templates)))
    return emb_avg.cpu().numpy().astype(np.float32), base_labels


def ensure_index(master_path: str, out_dir: str = "indexes", model_name: str = "ViT-B/32", mode: str = "video") -> Dict[str, Any]:
    os.makedirs(out_dir, exist_ok=True)
    key = f"labels_clip_{mode}_{model_name.replace('/', '-')}.npz"
    npz_path = os.path.join(out_dir, key)
    labels: List[str]
    # Allow a "cached-only" mode to avoid expensive first-builds in latency-sensitive paths.
    # When VEIL_CACHED_ONLY=true (or KNOT_LABELS_CACHED_ONLY=true), return an empty index
    # if the NPZ is not present instead of building it.
    cached_only = str(os.environ.get("VEIL_CACHED_ONLY", os.environ.get("KNOT_LABELS_CACHED_ONLY", "false"))).lower() in {"1","true","yes","on"}
    if os.path.isfile(npz_path):
        d = np.load(npz_path, allow_pickle=True)
        E = d["E"].astype(np.float32)
        labels = list(d["labels"].tolist())
    else:
        if cached_only:
            return {"emb": np.zeros((0, 1), dtype=np.float32), "labels": [], "index": None, "npz": npz_path}
        E, labels = build_label_embeddings(master_path, model_name=model_name, mode=mode, device="cpu")
        np.savez_compressed(npz_path, E=E, labels=np.array(labels, dtype=object))
    index = None
    if faiss is not None and E.size > 0:
        dim = E.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(E)
    return {"emb": E, "labels": labels, "index": index, "npz": npz_path}


# NOTE: CLAP-based audio helpers removed. Audio classification now uses
# YAMNet via veil.fusion.yamnet_events (no direct API dependency here).


def _sample_video_frames(video_path: str, max_frames: int = 8) -> List[Any]:
    import cv2  # type: ignore
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    stride = max(1, total // max(1, max_frames))
    frames: List[Any] = []
    i = 0
    while True and len(frames) < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        if i % stride == 0:
            # BGR to RGB
            frames.append(frame[:, :, ::-1])
        i += 1
    cap.release()
    return frames


def embed_video(video_path: str, model_name: str = "ViT-B/32", frames: int = 8, device: str = "cpu") -> Tuple[np.ndarray, np.ndarray]:
    model, preprocess = clip.load(model_name, device=device)
    imgs = _sample_video_frames(video_path, max_frames=frames)
    if not imgs:
        raise RuntimeError("No frames sampled from video")
    # CLIP preprocess expects PIL Images or torch tensors; convert np arrays to PIL
    try:
        from PIL import Image  # type: ignore
    except Exception:
        Image = None  # type: ignore
    proc_inputs = []
    for im in imgs:
        x = im
        if Image is not None and not torch.is_tensor(im):
            try:
                x = Image.fromarray(im)
            except Exception:
                x = im
        proc_inputs.append(preprocess(x))
    img_tensors = torch.stack(proc_inputs).to(device)
    with torch.no_grad():
        vid = _normalize(model.encode_image(img_tensors).float())  # [F, D]
    pooled = _normalize(vid.mean(dim=0, keepdim=True))  # [1, D]
    return vid.cpu().numpy().astype(np.float32), pooled.cpu().numpy().astype(np.float32)


def ann_search(E: np.ndarray, labels: List[str], query: np.ndarray, k: int = 10, index=None) -> List[Tuple[str, float, int]]:
    # query: [1, D]
    if E.size == 0:
        return []
    if index is not None and faiss is not None:
        D, I = index.search(query, min(k, E.shape[0]))
        out: List[Tuple[str, float, int]] = []
        for score, idx in zip(D[0], I[0]):
            out.append((labels[idx], float(score), int(idx)))
        return out
    # Fallback: brute-force inner product
    scores = (query @ E.T)[0]
    order = np.argsort(scores)[::-1][: min(k, E.shape[0])]
    return [(labels[i], float(scores[i]), int(i)) for i in order]


def rerank_with_frames(top_idx: List[int], E: np.ndarray, frames_emb: np.ndarray, agg: str = 'mean') -> List[Tuple[int, float]]:
    # frames_emb: [F, D], E[top_idx]: [K, D]
    if not top_idx:
        return []
    K = len(top_idx)
    E_top = E[top_idx]  # [K, D]
    # Sim per frame per label
    sims = frames_emb @ E_top.T  # [F, K]
    if agg == 'max':
        scores = sims.max(axis=0)
    elif agg == 'softmax':
        # Softmax over frames then average expected similarity
        import numpy as _np
        sm = _np.exp(sims - sims.max(axis=0, keepdims=True))
        sm = sm / (sm.sum(axis=0, keepdims=True) + 1e-9)
        scores = (sm * sims).sum(axis=0)
    else:
        scores = sims.mean(axis=0)
    order = np.argsort(scores)[::-1]
    return [(int(top_idx[i]), float(scores[i])) for i in order]
