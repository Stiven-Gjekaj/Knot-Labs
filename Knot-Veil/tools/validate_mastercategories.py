#!/usr/bin/env python3
"""Validate examples/mastercategories.txt for exact format and count.

Checks:
- File exists and has exactly 1000 non-empty lines.
- Each line contains exactly one pipe '|'.
- Left starts with 'a video about ' and right starts with 'a photo of '.
- No duplicate left sides or right sides.

Prints 'VALID' on success; otherwise prints errors and exits non-zero.
"""
from __future__ import annotations

import os
import sys
from typing import List, Tuple


TARGET_COUNT = 1000


def validate(path: str) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not os.path.isfile(path):
        return False, [f"Missing file: {path}"]
    with open(path, "r", encoding="utf-8") as f:
        raw = [ln.rstrip("\n") for ln in f]
    lines = [ln for ln in raw if ln.strip()]
    if len(lines) != TARGET_COUNT:
        errors.append(f"Expected {TARGET_COUNT} lines, found {len(lines)}")
    lefts: List[str] = []
    rights: List[str] = []
    for i, ln in enumerate(lines, 1):
        if ln.count("|") != 1:
            errors.append(f"Line {i}: must contain exactly one '|' -> {ln}")
            continue
        left, right = [p.strip() for p in ln.split("|", 1)]
        if not left.startswith("a video about "):
            errors.append(f"Line {i}: left must start with 'a video about ': {left}")
        if not right.startswith("a photo of "):
            errors.append(f"Line {i}: right must start with 'a photo of ': {right}")
        lefts.append(left)
        rights.append(right)
    if len(set(lefts)) != len(lefts):
        errors.append("Duplicate left-side entries detected")
    if len(set(rights)) != len(rights):
        errors.append("Duplicate right-side entries detected")
    return (len(errors) == 0), errors


def main() -> None:
    here = os.path.abspath(os.path.dirname(__file__))
    target = os.path.abspath(os.path.join(here, os.pardir, "examples", "mastercategories.txt"))
    ok, errs = validate(target)
    if ok:
        print("VALID")
    else:
        for e in errs:
            print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
