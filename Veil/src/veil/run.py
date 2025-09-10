from __future__ import annotations

"""
Unified runner for Veil fusion using:
  - CLIP (video/image)
  - Whisper+CLIP (speech)
  - YAMNet (audio events -> label scores)

By default all three modalities are active and the top 14 labels are
returned (2 macro, 4 meso, 8 micro). ANN retrieval is optional and
disabled unless ``--use_ann true`` is provided.

Example:
  python -m veil.run \
    --mode video \
    --video path/to/video.mp4 \
    --master_labels_file Mesh/mastercategories.txt

Notes:
  - FAISS is used for ANN if installed; otherwise falls back to dot product.
  - Audio uses YAMNet by default when w_audio > 0.
  - Precompute label embeddings once with tools/embed_labels.py for best startup time.
"""

import argparse
import os
import warnings
from typing import List, Dict, Optional, Tuple
import numpy as np
import torch
import concurrent.futures

from .fusion.label_loader import load_master_labels, select_labels
from .video_clip import classify_video_clip, _labels_look_like_prompts
from .image_clip import classify_image_clip
from .clip_utils import clip, get_clip_model
from .utils import min_max_norm, normalize_tensor

os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated",
    module="ctranslate2"
)
warnings.filterwarnings(
    "ignore",
    message="Installed 'clip' package lacks '_tokenizer'",
    category=RuntimeWarning,
    module="veil.audio_whisper",
)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="tensorflow")


def _parse_bool(s: str) -> bool:
    t = s.strip().lower()
    return t in {"1", "true", "yes", "y", "on"}


def fuse_scores(
    video_scores: np.ndarray,
    speech_scores: np.ndarray,
    event_scores: np.ndarray,
    w_video: float,
    w_speech: float,
    w_audio: float,
) -> np.ndarray:
    v = min_max_norm(video_scores)
    s = min_max_norm(speech_scores)
    e = min_max_norm(event_scores)
    return w_video * v + w_speech * s + w_audio * e


_LABEL_CACHE: Dict[Tuple[str, str, int], torch.Tensor] = {}


def _cache_key(model_name: str, mode: str, labels: List[str]) -> Tuple[str, str, int]:
    # Use a simple hash of labels list for key stability
    return (model_name, mode, hash(tuple(labels)))


def _strip_prompt_prefix(label: str, mode: str) -> str:
    """Strip common prefixes from master label prompts to get base category.

    Examples:
      - "a video about trains" -> "trains"
      - "a photo of train stations" -> "train stations"
    """
    label_clean = label.strip()
    low = label_clean.lower()
    prefixes = (
        ("video", [
            "a video of ",
            "a video about ",
            "video of ",
            "video about ",
        ]),
        ("photo", [
            "a photo of ",
            "photo of ",
        ]),
    )
    for m, pres in prefixes:
        if mode == m:
            for p in pres:
                if low.startswith(p):
                    return label_clean[len(p):].strip()
    return label_clean

# Optional ANN helpers (shared with API)
try:
    from api.label_index import ensure_index, embed_video as _embed_video_api, ann_search, rerank_with_frames  # type: ignore
except Exception:
    ensure_index = None  # type: ignore
    _embed_video_api = None  # type: ignore
    ann_search = None  # type: ignore
    rerank_with_frames = None  # type: ignore


def _build_label_embeddings(
    base_labels: List[str],
    mode: str,
    model_name: str,
    device: str,
) -> Tuple[torch.Tensor, List[str]]:
    """Create robust label embeddings via multi-template ensembling.

    We form several text prompts per base label (e.g., "a video of a {}",
    "a video of {}") and average their CLIP embeddings. This typically
    improves zero-shot alignment versus relying on a single phrasing like
    "about".
    """
    model, _ = get_clip_model(model_name, device=device)

    if mode == "video":
        templates = [
            "a video of a {}",
            "a video of {}",
            "a clip of a {}",
            "a recording of a {}",
        ]
    else:
        templates = [
            "a photo of a {}",
            "a photo of {}",
            "an image of a {}",
            "a picture of a {}",
        ]

    # Build prompts per template and encode
    emb_accum: Optional[torch.Tensor] = None
    # Keep one representative prompt list for diagnostics (first template)
    rep_prompts = [templates[0].format(c) for c in base_labels]
    for tmpl in templates:
        prompts = [tmpl.format(c) for c in base_labels]
        tokens = clip.tokenize(prompts, truncate=True).to(device)
        with torch.no_grad():
            emb = normalize_tensor(model.encode_text(tokens).float())  # [L, D]
        if emb_accum is None:
            emb_accum = emb
        else:
            emb_accum = emb_accum + emb
    assert emb_accum is not None
    # Average and renormalize per label
    emb_avg = emb_accum / float(len(templates))
    emb_avg = normalize_tensor(emb_avg)
    return emb_avg, rep_prompts


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Veil fusion runner (CLIP + Whisper + YAMNet; ANN disabled by default)"
        )
    )
    p.add_argument("--mode", choices=["video", "image"], required=True)
    p.add_argument("--video")
    p.add_argument("--image")
    p.add_argument("--master_labels_file", default="Mesh/mastercategories.txt")
    p.add_argument("--model", default="ViT-B/32")
    p.add_argument("--frames", type=int, default=8)
    p.add_argument("--topk", type=int, default=14)
    p.add_argument("--threshold", type=float)

    # Speech / audio
    p.add_argument("--use_whisper", default="true")
    p.add_argument("--whisper_model", default="base")
    p.add_argument("--print_event_matches", action="store_true")

    # Weights
    p.add_argument("--w_video", type=float, default=0.5)
    p.add_argument("--w_speech", type=float, default=0.3)
    p.add_argument("--w_audio", type=float, default=0.2)

    # ANN controls
    p.add_argument("--use_ann", default="false")
    p.add_argument("--ann_k", type=int, default=32)
    p.add_argument("--ann_agg", choices=["mean","max","softmax"], default="mean")

    args = p.parse_args()

    # Validate mode vs inputs
    if args.mode == "video" and not args.video:
        raise SystemExit("--video is required when --mode video")
    if args.mode == "image" and not args.image:
        raise SystemExit("--image is required when --mode image")

    # Parse toggles early (used by embedding/ANN path)
    use_whisper = _parse_bool(args.use_whisper)
    use_ann = _parse_bool(args.use_ann)

    # Load labels (prompts)
    master = load_master_labels(args.master_labels_file, expect_exact_count=False)
    labels: List[str] = select_labels(master, "video" if args.mode == "video" else "photo")

    # Build or load label embeddings
    device = "cpu"
    label_emb: torch.Tensor
    E_np: Optional[np.ndarray] = None
    ann_labels: Optional[List[str]] = None
    ann_index = None
    if use_ann and ensure_index is not None and _embed_video_api is not None:
        try:
            idx = ensure_index(
                args.master_labels_file,
                out_dir="indexes",
                model_name=args.model,
                mode=("video" if args.mode == "video" else "image"),
            )
            E_np = idx.get("emb")
            ann_labels = idx.get("labels")
            ann_index = idx.get("index")
            if isinstance(E_np, np.ndarray) and isinstance(ann_labels, list):
                if len(ann_labels) == len(labels):
                    label_emb = torch.from_numpy(E_np)
                    labels = ann_labels
                else:
                    warnings.warn(
                        "ANN label count mismatch; rebuilding label embeddings",
                        RuntimeWarning,
                        stacklevel=2,
                    )
                    raise ValueError("ANN label length mismatch")
            else:
                raise RuntimeError("Invalid ANN embeddings")
        except Exception:
            E_np = None
            ann_labels = None
            ann_index = None
            # Fallback to local build
            base_labels = [
                _strip_prompt_prefix(lbl, "video" if args.mode == "video" else "photo")
                for lbl in labels
            ]
            rep_prompts = [
                ("a video of a {}" if args.mode == "video" else "a photo of a {}").format(c)
                for c in base_labels
            ]
            ck = _cache_key(args.model, args.mode, rep_prompts)
            if ck in _LABEL_CACHE:
                label_emb = _LABEL_CACHE[ck]
            else:
                label_emb, _ = _build_label_embeddings(base_labels, args.mode, args.model, device)
                _LABEL_CACHE[ck] = label_emb
    else:
        base_labels = [
            _strip_prompt_prefix(lbl, "video" if args.mode == "video" else "photo")
            for lbl in labels
        ]
        rep_prompts = [
            ("a video of a {}" if args.mode == "video" else "a photo of a {}").format(c)
            for c in base_labels
        ]
        ck = _cache_key(args.model, args.mode, rep_prompts)
        if ck in _LABEL_CACHE:
            label_emb = _LABEL_CACHE[ck]
        else:
            label_emb, _ = _build_label_embeddings(base_labels, args.mode, args.model, device)
            _LABEL_CACHE[ck] = label_emb

    # Launch modality scorers concurrently

    def _video_task():
        if args.mode == "video" and use_ann and E_np is not None and _embed_video_api is not None:
            frames_emb, pooled = _embed_video_api(
                args.video, model_name=args.model, frames=args.frames, device="cpu"
            )
            Sv = (pooled @ E_np.T)[0]
            try:
                if ann_search is not None:
                    top = ann_search(
                        E_np, labels, pooled, k=max(args.topk, args.ann_k), index=ann_index
                    )
                    top_idx = [t[2] for t in top]
                else:
                    top_idx = []
                if rerank_with_frames is not None and top_idx:
                    rer = rerank_with_frames(top_idx, E_np, frames_emb, agg=args.ann_agg)
                    Sv_rer = np.zeros_like(Sv)
                    for i, sc in rer:
                        Sv_rer[int(i)] = float(sc)
                    Sv = Sv_rer
            except Exception:
                pass
            if Sv.shape[0] != len(labels):
                warnings.warn(
                    "Score vector length mismatch with labels; resetting to zeros",
                    RuntimeWarning,
                    stacklevel=2,
                )
                Sv = np.zeros(len(labels), dtype=np.float32)
            return {
                "categories": labels,
                "scores": Sv,
                "frame_count": frames_emb.shape[0]
                if hasattr(frames_emb, "shape")
                else len(frames_emb),
            }
        if args.mode == "video":
            return classify_video_clip(
                args.video,
                labels,
                model_name=args.model,
                frames=args.frames,
                prompt_template="a video of {}",
                label_emb=label_emb,
            )
        else:
            return classify_image_clip(
                args.image,
                labels,
                model_name=args.model,
                prompt_template="a photo of {}",
            )

    def _speech_task():
        from .audio_whisper import transcribe_audio, score_transcript_with_clip
        transcript = transcribe_audio(args.video, model_size=args.whisper_model)
        return score_transcript_with_clip(
            transcript,
            labels,
            prompt_template=("a video of {}" if args.mode == "video" else "a photo of {}"),
            model_name=args.model,
            label_emb=label_emb,
        )

    def _audio_task():
        # YAMNet-based audio events mapped into label scores
        if args.mode == "video":
            try:
                from .fusion.yamnet_events import run_yamnet, score_events_to_labels
                ydiag_local = run_yamnet(args.video, topn=10)
                emap = score_events_to_labels(
                    args.video,
                    labels,
                    model_name=args.model,
                    topn_events=15,
                    label_emb=label_emb,
                )
                escores_local = np.array([emap[lbl] for lbl in labels], dtype=np.float32)
                return escores_local, ydiag_local, 'yamnet'
            except Exception as e:
                if args.print_event_matches:
                    print(f"YAMNet scoring failed: {e}")
        return np.zeros(len(labels), dtype=np.float32), None, 'none'

    futures: Dict[str, concurrent.futures.Future] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futures["video"] = ex.submit(_video_task)
        if args.mode == "video" and use_whisper and args.w_speech > 0:
            futures["speech"] = ex.submit(_speech_task)
        if args.mode == "video" and args.w_audio > 0:
            futures["audio"] = ex.submit(_audio_task)

    # Gather results
    vres = futures["video"].result()
    if "speech" in futures:
        sres = futures["speech"].result()
    else:
        sres = {"categories": labels, "scores": np.zeros(len(labels)), "chunk_count": 0}

    audio_backend = 'none'
    if "audio" in futures:
        escores, ydiag, audio_backend = futures["audio"].result()
    else:
        escores = np.zeros(len(labels), dtype=np.float32)
        ydiag = None

    # Fuse with simple reliability-based gating for speech/events
    v_mmn = min_max_norm(vres["scores"]) if isinstance(vres.get("scores"), np.ndarray) else np.zeros(len(labels))
    s_mmn = min_max_norm(sres["scores"]) if isinstance(sres.get("scores"), np.ndarray) else np.zeros(len(labels))
    e_mmn = min_max_norm(escores)
    speech_conf = float(s_mmn.max()) if s_mmn.size else 0.0
    event_conf = float(e_mmn.max()) if e_mmn.size else 0.0
    # Scale non-visual weights down when evidence is weak
    w_s_eff = args.w_speech * min(1.0, speech_conf / 0.7)
    w_a_eff = args.w_audio * min(1.0, event_conf / 0.7)
    w_v_eff = args.w_video
    # Optionally renormalize to keep total weight comparable
    total_w = w_v_eff + w_s_eff + w_a_eff
    if total_w > 1e-6:
        scale = (args.w_video + args.w_speech + args.w_audio) / total_w
        w_v_eff *= scale
        w_s_eff *= scale
        w_a_eff *= scale

    fused = fuse_scores(
        video_scores=vres["scores"],
        speech_scores=sres["scores"],
        event_scores=escores,
        w_video=w_v_eff,
        w_speech=w_s_eff,
        w_audio=w_a_eff,
    )

    topk = np.argsort(fused)[::-1][: args.topk]

    print("Visual top-k:")
    for i in np.argsort(min_max_norm(vres["scores"]))[::-1][: args.topk]:
        print(f"  {labels[i]}: {min_max_norm(vres['scores'])[i]:.3f}")
    print("Speech top-k:")
    for i in np.argsort(min_max_norm(sres["scores"]))[::-1][: args.topk]:
        print(f"  {labels[i]}: {min_max_norm(sres['scores'])[i]:.3f}")
    print(("Audio (YAMNet) top-k:" if audio_backend == 'yamnet' else "Audio top-k:"))
    for i in np.argsort(min_max_norm(escores))[::-1][: args.topk]:
        print(f"  {labels[i]}: {min_max_norm(escores)[i]:.3f}")

    print("Fused top-k:")
    for i in topk:
        print(f"  {labels[i]}: {fused[i]:.3f}")

    if args.threshold is not None:
        kept = [i for i in topk if fused[i] >= args.threshold]
        if not kept:
            print("Predictions: unknown")
        else:
            print("Predictions: " + ", ".join(labels[i] for i in kept))
    else:
        print("Predictions: " + ", ".join(labels[i] for i in topk))

    # Diagnostics
    chunks = sres.get("chunk_count", 0)
    print(f"Frames used: {vres['frame_count']} | Transcript chunks: {chunks}")
    if args.print_event_matches and ydiag is not None and audio_backend == 'yamnet':
        print("Top YAMNet events:")
        for name, sc in ydiag.top_events:
            print(f"  {name}: {sc:.3f}")


if __name__ == "__main__":
    main()
