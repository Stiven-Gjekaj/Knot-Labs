from __future__ import annotations

import argparse
from typing import List
from .utils import load_categories, min_max_norm
from .image_clip import classify_image_clip
from .video_clip import classify_video_clip


def main() -> None:
    p = argparse.ArgumentParser(description="Legacy Veil classifier (single-modality)")
    p.add_argument("--mode", choices=["video", "image"], required=True)
    p.add_argument("--video")
    p.add_argument("--image")
    p.add_argument("--labels", default="Mesh/mastercategories.txt")

    args = p.parse_args()

    if args.mode == "video" and not args.video:
        raise SystemExit("--video is required when --mode video")
    if args.mode == "image" and not args.image:
        raise SystemExit("--image is required when --mode image")

    cats: List[str] = load_categories(args.labels, modality=args.mode)
    if args.mode == "video":
        res = classify_video_clip(args.video, cats)
    else:
        res = classify_image_clip(args.image, cats)

    scores = min_max_norm(res["scores"])  # for readability
    print("Top-5:")
    for i in scores.argsort()[::-1][:5]:
        print(f"  {cats[i]}: {scores[i]:.3f}")


if __name__ == "__main__":
    main()

