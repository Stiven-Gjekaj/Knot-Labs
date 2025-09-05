#!/usr/bin/env python3
"""Validate a generated categories list."""
import argparse
import json
import sys
from pathlib import Path


def validate(categories):
    errors = []
    warnings = []
    if not isinstance(categories, list) or not categories:
        errors.append("categories must be a non-empty list")
        return errors, warnings

    lower_seen = set()
    for idx, category in enumerate(categories):
        if not isinstance(category, str):
            errors.append(f"category {idx} is not a string")
            continue
        if category != category.strip() or "  " in category:
            errors.append(f"category {idx} has bad spacing")
        if not (2 <= len(category) <= 80):
            errors.append(f"category {idx} has invalid length")
        low = category.lower()
        if low in lower_seen:
            errors.append(f"duplicate category: {category}")
        else:
            lower_seen.add(low)
        if "|" in category or any(ord(c) < 32 for c in category):
            warnings.append(f"suspicious characters in category: {category}")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate categories.json")
    data_dir = Path(__file__).resolve().parent.parent / "data"
    parser.add_argument("--categories", default=str(data_dir / "categories.json"))
    args = parser.parse_args()

    path = Path(args.categories)
    if not path.is_file():
        print(f"missing file: {path}", file=sys.stderr)
        return 1

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"invalid json: {exc}", file=sys.stderr)
        return 1

    errors, warnings = validate(data)
    for w in warnings:
        print(f"warning: {w}")
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        return 1
    print("categories.json ok")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
