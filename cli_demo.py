#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import json
import demo


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
    else:
        p.error("Unknown command")


if __name__ == "__main__":
    main()
