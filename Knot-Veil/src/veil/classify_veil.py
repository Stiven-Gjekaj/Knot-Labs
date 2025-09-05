import warnings
warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated",
    module="ctranslate2",
)
warnings.filterwarnings(
    "ignore",
    message="Installed 'clip' package lacks '_tokenizer'",
    category=RuntimeWarning,
    module="veil.audio_whisper",
)

import argparse
import mimetypes
import os
import numpy as np
import torch

from .utils import load_categories, min_max_norm, normalize_tensor
from .fusion.label_loader import load_master_labels, select_labels
from .video_clip import classify_video_clip, _labels_look_like_prompts
from .image_clip import classify_image_clip
from .audio_whisper import (
    transcribe_audio,
    score_transcript_with_clip,
    classify_audio_yamnet,
)
from .clip_utils import clip, get_clip_model


def _infer_modality(path: str) -> str:
    """Return "video" or "image" based on the file's MIME type or extension."""
    mime, _ = mimetypes.guess_type(path)
    if mime:
        if mime.startswith("video"):
            return "video"
        if mime.startswith("image"):
            return "image"
    ext = os.path.splitext(path)[1].lower()
    video_exts = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv"}
    image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}
    if ext in video_exts:
        return "video"
    if ext in image_exts:
        return "image"
    raise SystemExit("Cannot determine file type: expected an image or video file")


def main():
    parser = argparse.ArgumentParser(description="Veil zero-shot audio+video classifier")
    parser.add_argument("path", help="Path to video or image file")
    parser.add_argument("--labels", help="Comma list or file path of categories")
    parser.add_argument("--topk", type=int, default=3, help="Top-k predictions to show")
    parser.add_argument("--frames", type=int, default=16, help="Max frames to sample")
    parser.add_argument("--model", default="ViT-B/32", help="CLIP model name")
    parser.add_argument("--template", default=None, help="Prompt template (auto-set by modality if omitted)")
    parser.add_argument("--threshold", type=float, help="Unknown threshold for fused score")
    parser.add_argument("--audio_weight", type=float, default=None)
    parser.add_argument("--video_weight", type=float, default=None)
    parser.add_argument("--whisper_model", default="base")
    args = parser.parse_args()

    mode = _infer_modality(args.path)

    # Default prompt template per modality if not provided
    if args.template is None:
        args.template = "a video of {}" if mode == "video" else "a photo of {}"

    # Default fusion weights by modality if not provided
    if args.audio_weight is None:
        args.audio_weight = 0.0 if mode == "image" else 0.5
    if args.video_weight is None:
        args.video_weight = 1.0 if mode == "image" else 0.5

    # Load categories: if the labels file looks like master (has '|'),
    # use the exact label prompts returned by label_loader. Otherwise,
    # fall back to legacy loader.
    categories: list[str]
    if args.labels:
        if os.path.isfile(args.labels):
            with open(args.labels, "r", encoding="utf-8") as f:
                head = f.read(4096)
            if "|" in head and ("a video" in head or "a photo" in head):
                master = load_master_labels(args.labels, expect_exact_count=None)
                categories = select_labels(master, "video" if mode == "video" else "photo")
            else:
                categories = load_categories(args.labels, modality=("video" if mode == "video" else "photo"))
        else:
            categories = load_categories(args.labels, modality=("video" if mode == "video" else "photo"))
    else:
        default_labels = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "examples", "mastercategories.txt")
        master = load_master_labels(default_labels, expect_exact_count=False)
        categories = select_labels(master, "video" if mode == "video" else "photo")

    # Precompute label embeddings once
    device = "cpu"
    model, _ = get_clip_model(args.model, device=device)
    if _labels_look_like_prompts(categories):
        label_prompts = categories
    else:
        tmpl = args.template or ("a video of {}" if mode == "video" else "a photo of {}")
        label_prompts = [tmpl.format(c) for c in categories]
    tokens = clip.tokenize(label_prompts, truncate=True).to(device)
    with torch.no_grad():
        label_emb = normalize_tensor(model.encode_text(tokens).float())

    # Visual modality (video or image)
    if mode == "video":
        vid_res = classify_video_clip(
            args.path,
            categories,
            model_name=args.model,
            frames=args.frames,
            prompt_template=args.template,
            label_emb=label_emb,
        )
    else:
        vid_res = classify_image_clip(
            args.path,
            categories,
            model_name=args.model,
            prompt_template=args.template,
        )

    # Audio modality (only for videos)
    if mode == "video" and args.audio_weight and args.audio_weight > 0:
        transcript = transcribe_audio(args.path, model_size=args.whisper_model)
        aud_res = score_transcript_with_clip(
            transcript,
            categories,
            prompt_template=args.template,
            model_name=args.model,
            label_emb=label_emb,
        )
        yamnet_res = classify_audio_yamnet(args.path, topk=args.topk)
    else:
        aud_res = {"categories": categories, "scores": np.zeros(len(categories)), "chunk_count": 0}
        yamnet_res = []

    v_scores = min_max_norm(vid_res["scores"])
    a_scores = min_max_norm(aud_res["scores"])
    fused = args.video_weight * v_scores + args.audio_weight * a_scores

    topk_idx = np.argsort(fused)[::-1][:args.topk]

    print("Visual modality top-k:")
    for i in np.argsort(v_scores)[::-1][:args.topk]:
        print(f"  {categories[i]}: {v_scores[i]:.3f}")
    print("Audio modality top-k:")
    for i in np.argsort(a_scores)[::-1][:args.topk]:
        print(f"  {categories[i]}: {a_scores[i]:.3f}")
    if yamnet_res:
        print("YAMNet top-k:")
        for label, score in yamnet_res:
            print(f"  {label}: {score:.3f}")

    print("Fused top-k:")
    for i in topk_idx:
        print(f"  {categories[i]}: {fused[i]:.3f}")

    # Final prediction summary: show top-k fused categories
    if args.threshold is not None:
        kept = [i for i in topk_idx if fused[i] >= args.threshold]
        if not kept:
            print("Predictions: unknown")
        else:
            labels = ", ".join(categories[i] for i in kept[:args.topk])
            print(f"Predictions: {labels}")
    else:
        labels = ", ".join(categories[i] for i in topk_idx)
        print(f"Predictions: {labels}")

    print(f"Frames used: {vid_res['frame_count']} | Transcript chunks: {aud_res['chunk_count']}")


if __name__ == "__main__":
    main()
