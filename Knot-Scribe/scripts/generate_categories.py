#!/usr/bin/env python3
"""Utilities for working with category lists.

This module can generate a replacement ``mastercategories.txt`` when the
canonical file is missing.  The generator produces lines in the same
format as the original file: ``a video about X | a photo of X``.
"""

import argparse
import json
import random
import sys
from itertools import product
from pathlib import Path

PREFIXES = [
    "a video about",
    "a video of",
    "a photo about",
    "a photo of",
]

ARTICLES = ["a", "an", "the"]

_word_path = Path(__file__).resolve().parent.parent / "data" / "word_lists.json"
try:
    _word_lists = json.loads(_word_path.read_text(encoding="utf-8"))
except OSError:
    # Fallback lists used when ``word_lists.json`` is not present.
    _word_lists = {
        "adjectives": ["quick", "lazy", "happy", "sad", "bright", "dark"],
        "nouns": ["fox", "dog", "cat", "sky", "tree", "river"],
    }

ADJECTIVES = _word_lists["adjectives"]
NOUNS = _word_lists["nouns"]


def normalize(text: str) -> str:
    """Return a normalized category or an empty string."""

    text = text.lower().strip()
    for prefix in PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    for art in ARTICLES:
        if text.startswith(art + " "):
            text = text[len(art) + 1 :]
            break
    return " ".join(text.split())


def extract_categories(lines):
    """Extract normalized categories from iterable of lines."""

    categories = []
    for line in lines:
        raw = line.strip()
        if not raw or raw.startswith("#") or raw.startswith("//"):
            continue
        for part in raw.split("|"):
            category = normalize(part)
            if category:
                categories.append(category)
    return categories


def random_categories(count: int):
    """Return *count* random category strings."""

    all_pairs = [f"{a} {n}" for a, n in product(ADJECTIVES, NOUNS)]
    total_pairs = len(all_pairs)
    if count > total_pairs:
        raise ValueError(
            f"requested {count} categories but only {total_pairs} combinations available"
        )
    return random.sample(all_pairs, count)


def random_master_categories(count: int):
    """Return *count* lines formatted like ``mastercategories.txt``."""

    cats = random_categories(count)
    return [f"a video about {c} | a photo of {c}" for c in cats]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a mastercategories file if it is missing"
    )
    data_dir = Path(__file__).resolve().parent.parent / "data"
    parser.add_argument(
        "--file", dest="outfile", default=str(data_dir / "mastercategories.txt")
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="number of random categories when generating a new file",
    )
    args = parser.parse_args()

    out_path = Path(args.outfile)
    if out_path.exists():
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = random_master_categories(args.count)
    try:
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"write failure: {exc}", file=sys.stderr)
        return 1

    print(f"generated {len(lines)} categories -> {out_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

