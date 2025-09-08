#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os

from api.label_index import ensure_index


def main() -> None:
    ap = argparse.ArgumentParser(description="Embed label prompts and build optional ANN index")
    ap.add_argument("--master", default="Mesh/mastercategories.txt", help="Path to mastercategories.txt")
    ap.add_argument("--out", default="indexes", help="Output directory for embeddings/index")
    ap.add_argument("--model", default="ViT-B/32")
    ap.add_argument("--mode", choices=["video", "image"], default="video")
    args = ap.parse_args()

    d = ensure_index(args.master, out_dir=args.out, model_name=args.model, mode=args.mode)
    print(f"Wrote embeddings: {d['npz']}")
    print(f"Labels: {len(d['labels'])}")


if __name__ == "__main__":
    main()

