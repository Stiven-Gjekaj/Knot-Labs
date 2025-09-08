#!/usr/bin/env python3
from __future__ import annotations

"""
Compatibility wrapper for hierarchical builder now infused into build_mastercategories.

Delegates to Mesh.tools.build_mastercategories.{build_tree, write_master_from_tree, build_tree_and_write}.
"""

import argparse
import os
from typing import Dict, List

from .build_mastercategories import build_tree, write_master_from_tree, build_tree_and_write  # type: ignore


def main() -> None:
    ap = argparse.ArgumentParser(description="Build hierarchical mastercategories from a fixed macro tree")
    ap.add_argument('--out', default='Mesh/mastercategories.txt')
    ap.add_argument('--tree_out', default='Mesh/master_tree.json')
    ap.add_argument('--mesos', type=int, default=3, help='meso per macro')
    ap.add_argument('--micros', type=int, default=3, help='micro per meso')
    args = ap.parse_args()

    root = os.path.dirname(os.path.abspath(args.out)) or '.'
    os.makedirs(root, exist_ok=True)
    stats = build_tree_and_write(out_path=args.out, tree_out=args.tree_out, mesos=int(args.mesos), micros=int(args.micros))
    print(f"Wrote {stats.get('final')} labels to {args.out} and tree to {args.tree_out}")


if __name__ == '__main__':
    main()
