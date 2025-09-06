from __future__ import annotations

"""
Unified runner for Veil fusion: CLIP (video/image), Whisper+CLIP (speech),
and YAMNet (audio events). Uses the exact master label prompts.

Example:
  python -m veil.run \
    --mode video \
    --video path/to/video.mp4 \
    --master_labels_file Mesh/mastercategories.txt \
    --use_whisper true --whisper_model base \
    --w_video 0.5 --w_speech 0.3 --w_audio 0.2 \
    --threshold 0.25 \
    --print_event_matches

YAMNet runs by default; add --use_yamnet false to disable event scoring.
"""

import warnings
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

import argparse
import os
from typing import List, Dict, Optional, Tuple
import numpy as np
import torch
import concurrent.futures

from .fusion.label_loader import load_master_labels, select_labels
from .video_clip import classify_video_clip, _labels_look_like_prompts
from .image_clip import classify_image_clip
from .clip_utils import clip, get_clip_model
from .utils import min_max_norm, normalize_tensor


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
    l = label.strip()
    low = l.lower()
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
                    return l[len(p):].strip()
    return l


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
    p = argparse.ArgumentParser(description="Veil fusion runner")
    p.add_argument("--mode", choices=["video", "image"], required=True)
    p.add_argument("--video")
    p.add_argument("--image")
    p.add_argument("--master_labels_file", default="Mesh/mastercategories.txt")
    p.add_argument("--model", default="ViT-B/32")
    p.add_argument("--frames", type=int, default=16)
    p.add_argument("--topk", type=int, default=5)
    p.add_argument("--threshold", type=float)

    # Speech / events
    p.add_argument("--use_whisper", default="false")
    p.add_argument("--whisper_model", default="base")
    p.add_argument("--use_yamnet", default="true")
    p.add_argument("--print_event_matches", action="store_true")

    # Weights
    p.add_argument("--w_video", type=float, default=0.5)
    p.add_argument("--w_speech", type=float, default=0.3)
    p.add_argument("--w_audio", type=float, default=0.2)

    args = p.parse_args()

    # Validate mode vs inputs
    if args.mode == "video" and not args.video:
        raise SystemExit("--video is required when --mode video")
    if args.mode == "image" and not args.image:
        raise SystemExit("--image is required when --mode image")

    # Load labels (prompts)
    master = load_master_labels(args.master_labels_file, expect_exact_count=False)
    labels: List[str] = select_labels(master, "video" if args.mode == "video" else "photo")

    # Precompute label embeddings once with multi-template ensembling
    device = "cpu"
    # Derive base category strings from prompts and build robust embeddings
    base_labels = [_strip_prompt_prefix(l, "video" if args.mode == "video" else "photo") for l in labels]
    # Cache by the representative prompt list
    rep_prompts = [
        ("a video of a {}" if args.mode == "video" else "a photo of a {}").format(c)
        for c in base_labels
    ]
    ck = _cache_key(args.model, args.mode, rep_prompts)
    if ck in _LABEL_CACHE:
        label_emb = _LABEL_CACHE[ck]
    else:
        label_emb, rep = _build_label_embeddings(base_labels, args.mode, args.model, device)
        _LABEL_CACHE[ck] = label_emb

    # Launch modality scorers concurrently
    use_whisper = _parse_bool(args.use_whisper)
    use_yamnet = _parse_bool(args.use_yamnet)

    def _video_task():
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

    def _event_task():
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
            return escores_local, ydiag_local
        except Exception as e:
            if args.print_event_matches:
                print(f"YAMNet scoring failed: {e}")
            return np.zeros(len(labels), dtype=np.float32), None

    futures: Dict[str, concurrent.futures.Future] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futures["video"] = ex.submit(_video_task)
        if args.mode == "video" and use_whisper and args.w_speech > 0:
            futures["speech"] = ex.submit(_speech_task)
        if args.mode == "video" and use_yamnet and args.w_audio > 0:
            futures["event"] = ex.submit(_event_task)

    # Gather results
    vres = futures["video"].result()
    if "speech" in futures:
        sres = futures["speech"].result()
    else:
        sres = {"categories": labels, "scores": np.zeros(len(labels)), "chunk_count": 0}

    if "event" in futures:
        escores, ydiag = futures["event"].result()
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
    print("Events top-k:")
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
    if args.print_event_matches and ydiag is not None:
        print("Top YAMNet events:")
        for name, sc in ydiag.top_events:
            print(f"  {name}: {sc:.3f}")


if __name__ == "__main__":
    main()
