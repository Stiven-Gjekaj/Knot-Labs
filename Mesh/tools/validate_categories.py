#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from typing import Tuple, List, Set


def parse_line(line: str) -> Tuple[str, str, str]:
    line = line.strip()
    if not line or line.startswith("#"):
        return ("", "", "")
    if "|" not in line:
        raise ValueError(f"Missing '|' separator: {line!r}")
    left, right = [p.strip() for p in line.split("|", 1)]
    # Expect exact prompt templates
    if not left.startswith("a video about "):
        raise ValueError(f"Left side must start with 'a video about ': {left!r}")
    if not right.startswith("a photo of "):
        raise ValueError(f"Right side must start with 'a photo of ': {right!r}")
    cat_left = left[len("a video about "):].strip()
    cat_right = right[len("a photo of "):].strip()
    if not cat_left or not cat_right:
        raise ValueError(f"Empty category: {line!r}")
    if cat_left != cat_right:
        raise ValueError(f"Mismatched categories: {line!r}")
    return (left, right, cat_left)


def validate(path: str, expect_min: int = 1) -> int:
    if not os.path.isfile(path):
        print(f"Not found: {path}", file=sys.stderr)
        return 2
    total = 0
    cats: List[str] = []
    seen: Set[str] = set()
    with open(path, "r", encoding="utf-8") as f:
        for ln, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw or raw.startswith("#"):
                continue
            total += 1
            _, _, cat = parse_line(raw)
            cats.append(cat)
            if cat in seen:
                print(f"Duplicate category at line {ln}: {cat}")
            seen.add(cat)
    uniq = len(set(cats))
    print(f"Lines: {total} | Unique categories: {uniq}")
    if total < expect_min:
        print(f"Too few lines: {total} < {expect_min}", file=sys.stderr)
        return 3
    if uniq != total:
        print(f"Warning: {total - uniq} duplicates found")
    print("OK")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Validate Mesh mastercategories.txt format")
    p.add_argument("--file", default=os.path.join("Mesh", "mastercategories.txt"))
    p.add_argument("--expect-min", type=int, default=100)  # not strict 1000 to allow development
    args = p.parse_args()
    rc = validate(args.file, expect_min=args.expect_min)
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
