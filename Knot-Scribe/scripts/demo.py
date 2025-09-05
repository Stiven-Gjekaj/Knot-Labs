#!/usr/bin/env python3
"""Interactive demo for generating data and searching videos."""

import json
import random
import uuid
from pathlib import Path

from generate_categories import random_master_categories
from generate_random_videos import CREATORS, load_categories, random_video

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MASTER_FILE = DATA_DIR / "mastercategories.txt"
VIDEOS_FILE = DATA_DIR / "videos.json"


def generate_categories_cmd(count: int) -> None:
    """Generate *count* random master categories."""
    lines = random_master_categories(count)
    MASTER_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"generated {len(lines)} categories -> {MASTER_FILE}")


def generate_videos_cmd(count: int) -> None:
    """Generate *count* random videos into ``videos.json``."""
    if not MASTER_FILE.is_file():
        print("missing mastercategories.txt; run 'generate categories N' first")
        return
    categories = load_categories(MASTER_FILE)
    videos = []
    for idx in range(count):
        if len(categories) >= 3:
            video = random_video(categories)
        else:
            video = {
                "creator": random.choice(CREATORS),
                "categories": random.sample(categories, k=len(categories)),
            }
        video["id"] = uuid.uuid4().hex
        video["title"] = f"Video {idx + 1}"
        videos.append(video)
    VIDEOS_FILE.write_text(
        json.dumps(videos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"generated {len(videos)} videos -> {VIDEOS_FILE}")


def search_cmd(initial: str = "") -> None:
    """Prompt for a sentence and show the best matching video.

    The previous implementation performed a simple keyword check against
    each video's categories.  This version uses a small sentence
    transformer model to embed the user's query and each video's
    categories, selecting the video with the highest cosine similarity.
    """
    if not VIDEOS_FILE.is_file():
        print("missing videos.json; run 'generate videos N' first")
        return
    query = initial or input("Enter a sentence: ")
    videos = json.loads(VIDEOS_FILE.read_text(encoding="utf-8"))

    # Import lazily so tests that do not exercise search do not pay the
    # startup cost of loading the model.
    from sentence_transformers import SentenceTransformer, util

    model = SentenceTransformer("all-MiniLM-L6-v2")
    corpus = [" ".join(video.get("categories", [])) for video in videos]
    corpus_emb = model.encode(corpus, convert_to_tensor=True)
    query_emb = model.encode(query, convert_to_tensor=True)
    scores = util.cos_sim(query_emb, corpus_emb)[0]
    best_idx = int(scores.argmax().item()) if len(scores) else None
    best = videos[best_idx] if best_idx is not None else None

    if best is None:
        print("no matching video found")
    else:
        print(json.dumps(best, indent=2, ensure_ascii=False))


def main() -> int:
    print(
        "Commands: generate categories N | generate videos N | search \"string\" | quit"
    )
    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not raw:
            continue
        if raw == "quit":
            return 0
        if raw.startswith("generate categories"):
            parts = raw.split()
            if len(parts) == 3 and parts[2].isdigit():
                generate_categories_cmd(int(parts[2]))
            else:
                print("usage: generate categories N")
        elif raw.startswith("generate videos"):
            parts = raw.split()
            if len(parts) == 3 and parts[2].isdigit():
                generate_videos_cmd(int(parts[2]))
            else:
                print("usage: generate videos N")
        elif raw.startswith("search"):
            parts = raw.split(" ", 1)
            query = parts[1].strip().strip('"') if len(parts) > 1 else ""
            search_cmd(query)
        else:
            print("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())

