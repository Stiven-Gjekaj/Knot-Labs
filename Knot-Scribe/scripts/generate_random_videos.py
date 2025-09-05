#!/usr/bin/env python3
"""Generate random video metadata."""
import argparse
import json
import random
from pathlib import Path

from generate_categories import extract_categories

CREATORS = [
    "Alice",
    "Bob",
    "Charlie",
    "Dana",
    "Elliot",
]

def load_categories(path: Path):
    """Load categories from a ``mastercategories.txt`` file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return sorted(set(extract_categories(lines)))

def random_video(categories):
    """Return a random video description."""
    return {
        "creator": random.choice(CREATORS),
        "categories": random.sample(categories, k=3),
    }

def main() -> int:
    parser = argparse.ArgumentParser(description="Generate random video metadata")
    data_dir = Path(__file__).resolve().parent.parent / "data"
    parser.add_argument("--master", default=str(data_dir / "mastercategories.txt"))
    parser.add_argument("--count", type=int, default=1)
    args = parser.parse_args()

    categories = load_categories(Path(args.master))
    for _ in range(args.count):
        print(json.dumps(random_video(categories), ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
