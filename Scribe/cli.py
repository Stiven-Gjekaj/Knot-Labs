#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from .search import build_index


def main() -> None:
    p = argparse.ArgumentParser(description="Scribe search over Mesh posts")
    p.add_argument("--posts-dir", default=os.path.join("Mesh", "Posts"))
    p.add_argument("--backend", default="bow", choices=["bow", "st"])  # st = sentence-transformers
    p.add_argument("--k", type=int, default=10)
    p.add_argument("query", nargs="+")
    args = p.parse_args()

    idx = build_index(args.posts_dir, backend=args.backend)
    q = " ".join(args.query)
    results = idx.search(q, k=args.k)
    for pid, sc in results:
        print(f"{pid}\t{sc:.3f}")


if __name__ == "__main__":
    main()

