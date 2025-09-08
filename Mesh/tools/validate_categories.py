from __future__ import annotations

import os
from typing import Tuple


def parse_line(line: str) -> Tuple[str, str, str]:
    raw = line.strip()
    left, right = (raw, "") if "|" not in raw else tuple([s.strip() for s in raw.split("|", 1)])
    cat = ""
    low = left.lower()
    for p in ("a video about ", "a video of ", "video about ", "video of "):
        if low.startswith(p):
            cat = left[len(p):].strip()
            break
    if not cat:
        cat = left
    return left, right, cat


def validate(path: str, expect_min: int = 10) -> int:
    if not os.path.isfile(path):
        print(f"File not found: {path}")
        return 1
    seen = set()
    total = 0
    dupes = 0
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw or raw.startswith("#"):
                continue
            left, right, cat = parse_line(raw)
            total += 1
            if cat in seen:
                dupes += 1
            else:
                seen.add(cat)
    if total < expect_min:
        print(f"Warning: only {total} categories; expected at least {expect_min}")
    if dupes:
        print(f"Warning: {dupes} duplicate entries found")
    return 0

