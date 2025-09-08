#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import json
import demo
from typing import Any, Dict

try:
    from api.label_index import ensure_index, embed_video, ann_search, rerank_with_frames
except Exception:
    ensure_index = embed_video = ann_search = rerank_with_frames = None  # type: ignore
try:
    from Mesh.tools import build_mastercategories_tree as tree
except Exception:
    tree = None  # type: ignore


def main() -> None:
    p = argparse.ArgumentParser(description="Knot-Labs CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("create-user")
    s.add_argument("--username")

    s = sub.add_parser("post")
    s.add_argument("--creator", required=True)
    s.add_argument("--media", required=True)

    for name in ("like", "comment", "share"):
        s = sub.add_parser(name)
        s.add_argument("--viewer", required=True)
        s.add_argument("--creator", required=True)
        s.add_argument("--post", required=True)

    s = sub.add_parser("gift")
    s.add_argument("--viewer", required=True)
    s.add_argument("--creator", required=True)
    s.add_argument("--post", required=True)
    s.add_argument("--amount", type=float, default=1.0)

    s = sub.add_parser("rank")
    s.add_argument("--user", required=True)

    s = sub.add_parser("search")
    s.add_argument("--query", required=True)
    s.add_argument("--k", type=int, default=10)
    s.add_argument("--backend", default='bow', choices=['bow','st'])

    sub.add_parser("simulate")

    s = sub.add_parser("embed-labels")
    s.add_argument("--master", default="Mesh/mastercategories.txt")
    s.add_argument("--out", default="indexes")
    s.add_argument("--model", default="ViT-B/32")
    s.add_argument("--mode", default="video", choices=["video","image"])

    s = sub.add_parser("classify-ann")
    s.add_argument("--video", required=True)
    s.add_argument("--k", type=int, default=10)
    s.add_argument("--frames", type=int, default=8)
    s.add_argument("--model", default="ViT-B/32")
    s.add_argument("--agg", default="mean", choices=["mean","max","softmax"])

    s = sub.add_parser("build-tree")
    s.add_argument("--mesos", type=int, default=3)
    s.add_argument("--micros", type=int, default=3)
    s.add_argument("--out", default="Mesh/mastercategories.txt")
    s.add_argument("--tree-out", default="Mesh/master_tree.json")

    args = p.parse_args()

    if args.cmd == "create-user":
        u = demo.create_test_user(args.username)
        print(json.dumps(u, indent=2))
    elif args.cmd == "post":
        post = demo.post_and_classify(args.creator, args.media)
        print(json.dumps(post, indent=2))
    elif args.cmd == "like":
        demo.like_post(args.viewer, args.creator, args.post)
    elif args.cmd == "comment":
        demo.comment_post(args.viewer, args.creator, args.post)
    elif args.cmd == "share":
        demo.share_post(args.viewer, args.creator, args.post)
    elif args.cmd == "gift":
        demo.gift_post(args.viewer, args.creator, args.post, args.amount)
    elif args.cmd == "rank":
        out = demo.rank_for_user(args.user)
        print(json.dumps(out, indent=2))
    elif args.cmd == "search":
        out = demo.search_posts_ui(args.query, k=args.k, backend=args.backend)
        print(json.dumps(out, indent=2))
    elif args.cmd == "simulate":
        demo.simulate_update()
    elif args.cmd == "embed-labels":
        if ensure_index is None:
            print("embed-labels unavailable: import failed", file=sys.stderr)
            sys.exit(2)
        d = ensure_index(args.master, out_dir=args.out, model_name=args.model, mode=args.mode)
        info: Dict[str, Any] = {"npz": d.get("npz"), "labels": len(d.get("labels") or [])}
        print(json.dumps(info, indent=2))
    elif args.cmd == "classify-ann":
        if ensure_index is None or embed_video is None or ann_search is None:
            print("classify-ann unavailable: import failed", file=sys.stderr)
            sys.exit(2)
        idx = ensure_index("Mesh/mastercategories.txt", out_dir="indexes", model_name=args.model, mode="video")
        E = idx['emb']
        labels = idx['labels']
        index = idx['index']
        frames_emb, pooled = embed_video(args.video, model_name=args.model, frames=int(args.frames), device='cpu')
        top = ann_search(E, labels, pooled, k=int(args.k), index=index)
        if top:
            top_idx = [t[2] for t in top]
            rer = rerank_with_frames(top_idx, E, frames_emb, agg=args.agg)
            out = [{'label': labels[i], 'score': sc} for i, sc in rer[: args.k]]
        else:
            out = []
        print(json.dumps({"results": out}, indent=2))
    elif args.cmd == "build-tree":
        if tree is None:
            print("build-tree unavailable: import failed", file=sys.stderr)
            sys.exit(2)
        t = tree.build_tree(per_macro_mesos=args.mesos, per_meso_micros=args.micros)
        n = tree.write_master_from_tree(t, args.out)
        with open(args.tree_out, 'w', encoding='utf-8') as f:
            json.dump(t, f, indent=2, ensure_ascii=False)
        print(json.dumps({"written": n, "out": args.out, "tree": args.tree_out}, indent=2))
    else:
        p.error("Unknown command")


if __name__ == "__main__":
    main()
