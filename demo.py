"""CLI demo for the Knot stack."""
from __future__ import annotations

import json
import random
import shlex
import sys
from pathlib import Path

from knot.mesh.db import MeshDB
from knot.veil.analyzer import analyze_media
from knot.drift import ranker
from knot.scribe.search import interpret_query, search_posts
from knot.common.id_gen import make_user_id, make_post_id
from knot.mesh.storage import ensure_dir


def print_json(obj):
    print(json.dumps(obj, indent=2))


def handle_labs(mesh: MeshDB, user_id: str) -> None:
    if not mesh.get_user(user_id):
        mesh.create_user(user_id)
        print(f"created user {user_id}")
    mesh.set_active_user(user_id)
    print(f"active user set to {user_id}")


def handle_post(mesh: MeshDB, post_id: str, path: str) -> None:
    user_id = mesh.get_active_user()
    if not user_id:
        print("no active user; run 'labs \"user\"' first")
        return
    mesh.create_post(post_id, user_id, path)
    cats = analyze_media(path, mesh.get_master_categories())["categories"]
    mesh.set_post_categories(post_id, cats)
    score = ranker.rank_post(mesh, post_id)
    ranker.update_global_feed(mesh)
    print(f"post {post_id} created with categories {cats} score={score:.2f}")


def handle_engage(mesh: MeshDB, kind: str, post_id: str) -> None:
    user_id = mesh.get_active_user()
    if not user_id:
        print("no active user")
        return
    mesh.increment_engagement(post_id, user_id, kind)
    score = ranker.rank_post(mesh, post_id)
    ranker.update_global_feed(mesh)
    print(f"{kind} added to {post_id}; new score {score:.2f}")


def handle_gen_samples(mesh: MeshDB, n: int) -> None:
    random.seed(0)
    cats = mesh.get_master_categories()
    for i in range(1, n + 1):
        uid = make_user_id(i)
        pid = make_post_id(i)
        if not mesh.get_user(uid):
            mesh.create_user(uid)
        media_path = Path("data") / f"sample_{pid}.txt"
        ensure_dir(media_path.parent)
        media_path.write_text(f"sample content {pid}")
        mesh.create_post(pid, uid, str(media_path))
        analyzed = analyze_media(str(media_path), cats)
        mesh.set_post_categories(pid, analyzed["categories"])
        ranker.rank_post(mesh, pid)
    ranker.update_global_feed(mesh)
    print(f"generated {n} users and posts")
    handle_feed(mesh, 10)


def handle_feed(mesh: MeshDB, topk: int = 10) -> None:
    feed = mesh.get_feed(topk)
    for idx, p in enumerate(feed, 1):
        print(f"{idx}. {p['post_id']} by {p['owner_id']} score={p['rank_score']:.2f} cats={p['categories']}")


def handle_search(mesh: MeshDB, query: str) -> None:
    interp = interpret_query(query, mesh.get_master_categories())
    posts = search_posts(mesh, interp)
    for p in posts:
        print(f"{p['post_id']} by {p['owner_id']} score={p['rank_score']:.2f} cats={p['categories']}")


def handle_info(mesh: MeshDB, kind: str, identifier: str) -> None:
    if kind == "post":
        p = mesh.get_post(identifier)
        if p:
            print_json(p)
        else:
            print("post not found")
    elif kind == "user":
        u = mesh.get_user(identifier)
        if u:
            print_json(u)
        else:
            print("user not found")
    else:
        print("unknown info kind")


def process_command(mesh: MeshDB, parts: list[str]) -> bool:
    if not parts:
        return True
    cmd = parts[0]
    try:
        if cmd == "labs" and len(parts) >= 2:
            handle_labs(mesh, parts[1])
        elif cmd == "post" and len(parts) >= 3:
            handle_post(mesh, parts[1], parts[2])
        elif cmd in {"view", "like", "comment", "share", "gift"} and len(parts) >= 2:
            handle_engage(mesh, cmd, parts[1])
        elif cmd == "gen_samples" and len(parts) >= 2:
            handle_gen_samples(mesh, int(parts[1]))
        elif cmd == "feed":
            topk = int(parts[1]) if len(parts) >= 2 else 10
            handle_feed(mesh, topk)
        elif cmd == "search" and len(parts) >= 2:
            handle_search(mesh, " ".join(parts[1:]))
        elif cmd == "info" and len(parts) >= 3:
            handle_info(mesh, parts[1], parts[2])
        elif cmd in {"exit", "quit"}:
            return False
        else:
            print("unknown command")
    except Exception as e:
        print(f"error: {e}")
    return True


def main(argv: list[str]) -> None:
    mesh = MeshDB()
    mesh.get_master_categories()  # ensure setup
    if len(argv) > 1:
        process_command(mesh, argv[1:])
        return
    while True:
        try:
            line = input("knot> ")
        except EOFError:
            break
        parts = shlex.split(line)
        if not process_command(mesh, parts):
            break


if __name__ == "__main__":
    main(sys.argv)

