"""Command line interface for Knot stack."""
from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path
from typing import List

from knot.mesh.db import MeshDB
from knot.veil.analyzer import Veil
from knot.scribe.search import Scribe
from knot.mesh import storage


class CLI:
    def __init__(self, root: Path):
        self.mesh = MeshDB(root / "data")
        self.veil = Veil(self.mesh)
        self.scribe = Scribe(self.mesh)

    # --------------------------------------------------------------
    def run(self, argv: List[str]):
        if not argv:
            return
        cmd = argv[0]
        method = getattr(self, f"cmd_{cmd}", None)
        if not method:
            print(f"Unknown command: {cmd}")
            return
        method(argv[1:])

    # --------------------------------------------------------------
    def cmd_labs(self, args: List[str]):
        if not args:
            print("usage: labs USER")
            return
        user_id = args[0]
        self.mesh.create_user(user_id, user_id)
        self.mesh.set_active_user(user_id)
        print(f"active user -> {user_id}")

    def cmd_whoami(self, args: List[str]):
        user_id = self.mesh.get_active_user_id()
        print(user_id or "no active user")

    def cmd_logout(self, args: List[str]):
        self.mesh.set_active_user(None)
        print("logged out")

    def cmd_post(self, args: List[str]):
        if len(args) < 2:
            print("usage: post POST_ID PATH")
            return
        post_id, path_str = args[0], args[1]
        owner = self.mesh.get_active_user_id()
        if not owner:
            print("no active user")
            return
        path = Path(path_str)
        analysis = self.veil.analyze(path)
        post = self.mesh.create_post(post_id, owner, str(path), analysis["categories"])
        print(f"post {post_id} created with categories: {', '.join(post.categories)}")

    def _engage(self, kind: str, args: List[str]):
        if not args:
            print(f"usage: {kind} POST_ID")
            return
        viewer = self.mesh.get_active_user_id()
        post_id = args[0]
        kind_map = {
            "view": "views",
            "like": "likes",
            "comment": "comments",
            "share": "shares",
            "gift": "gifts",
        }
        post = self.mesh.record_engagement(post_id, kind_map[kind], viewer)
        print(f"{kind} recorded. score={post.rank_score:.2f}")

    def cmd_view(self, args: List[str]):
        self._engage("view", args)

    def cmd_like(self, args: List[str]):
        self._engage("like", args)

    def cmd_comment(self, args: List[str]):
        self._engage("comment", args)

    def cmd_share(self, args: List[str]):
        self._engage("share", args)

    def cmd_gift(self, args: List[str]):
        self._engage("gift", args)

    def cmd_feed(self, args: List[str]):
        top = int(args[0]) if args else 20
        posts = self.mesh.get_feed(top)
        if not posts:
            print("no posts")
            return
        for p in posts:
            print(f"{p.post_id} | {p.owner_id} | {p.rank_score:.2f} | {', '.join(p.categories)}")

    def cmd_search(self, args: List[str]):
        query = " ".join(args)
        interp = self.scribe.interpret_query(query)
        posts = self.scribe.search_posts(interp, 20)
        if not posts:
            print("no results")
            return
        for p in posts:
            print(f"{p.post_id} | {p.owner_id} | {', '.join(p.categories)}")

    def cmd_info(self, args: List[str]):
        if len(args) < 2:
            print("usage: info post|user ID")
            return
        typ, ident = args[0], args[1]
        if typ == "post":
            p = self.mesh.get_post(ident)
            print(p)
        elif typ == "user":
            u = self.mesh.get_user(ident)
            print(u)
        else:
            print("unknown type")

    def cmd_users(self, args: List[str]):
        for uid in self.mesh.list_users():
            print(uid)

    def cmd_posts(self, args: List[str]):
        for pid in self.mesh.list_posts():
            print(pid)

    def cmd_categories(self, args: List[str]):
        cats = self.mesh.master_categories
        if args:
            filt = args[0].lower()
            cats = [c for c in cats if filt in c]
        for c in cats:
            print(c)

    def cmd_gen_samples(self, args: List[str]):
        if not args:
            print("usage: gen_samples N")
            return
        n = int(args[0])
        self.mesh.gen_samples(n)
        print(f"generated {n} samples")

    def cmd_rerank(self, args: List[str]):
        self.mesh.update_feed()
        print("feed reranked")

    def cmd_topcats(self, args: List[str]):
        user_id = self.mesh.get_active_user_id()
        if not user_id:
            print("no active user")
            return
        u = self.mesh.get_user(user_id)
        for c in u.top_categories:
            print(c)

    def cmd_stats(self, args: List[str]):
        user_id = self.mesh.get_active_user_id()
        if not user_id:
            print("no active user")
            return
        u = self.mesh.get_user(user_id)
        print(u.viewer_stats)

    def cmd_unseen(self, args: List[str]):
        user_id = self.mesh.get_active_user_id()
        if not user_id:
            print("no active user")
            return
        u = self.mesh.get_user(user_id)
        unseen = [pid for pid in self.mesh.list_posts() if pid not in u.seen_posts]
        for pid in unseen:
            print(pid)

    def cmd_edit_post(self, args: List[str]):
        if len(args) < 2:
            print("usage: edit_post POST_ID NEW_PATH")
            return
        post = self.mesh.get_post(args[0])
        post.media_path = args[1]
        self.mesh.save_post(post)
        print("post updated")

    def cmd_del_post(self, args: List[str]):
        if not args:
            print("usage: del_post POST_ID")
            return
        pid = args[0]
        try:
            post = self.mesh.get_post(pid)
        except KeyError:
            print("not found")
            return
        path = self.mesh.posts_dir / f"{pid}.json"
        if path.exists():
            path.unlink()
        idx = self.mesh._load_index("posts")
        if pid in idx:
            idx.remove(pid)
            self.mesh._save_index("posts", idx)
        owner = self.mesh.get_user(post.owner_id)
        if pid in owner.posts:
            owner.posts.remove(pid)
            self.mesh.save_user(owner)
        self.mesh.update_feed()
        print("post deleted")

    def cmd_del_user(self, args: List[str]):
        if not args:
            print("usage: del_user USER_ID")
            return
        uid = args[0]
        try:
            user = self.mesh.get_user(uid)
        except KeyError:
            print("not found")
            return
        for pid in list(user.posts):
            self.cmd_del_post([pid])
        path = self.mesh.users_dir / f"{uid}.json"
        if path.exists():
            path.unlink()
        idx = self.mesh._load_index("users")
        if uid in idx:
            idx.remove(uid)
            self.mesh._save_index("users", idx)
        print("user deleted")

    def cmd_reset(self, args: List[str]):
        self.mesh.reset()
        print("database reset")

    def cmd_regen_categories(self, args: List[str]):
        if not args:
            print("usage: regen_categories N")
            return
        n = int(args[0])
        cats = [f"cat{i}" for i in range(n)]
        storage.write_text_atomic(self.mesh.master_file, "\n".join(cats))
        self.mesh._load_master_categories()
        print("categories regenerated")

    def cmd_help(self, args: List[str]):
        print("commands: labs, post, like, comment, share, gift, view, feed, search, info, users, posts, categories, whoami, logout, gen_samples, rerank, topcats, stats, unseen, edit_post, del_post, del_user, reset, regen_categories, help")


# ----------------------------------------------------------------------
def main():
    root = Path(__file__).resolve().parent
    cli = CLI(root)
    if len(sys.argv) > 1 and sys.argv[1] not in {"gui"}:
        cli.run(sys.argv[1:])
        return
    if len(sys.argv) > 1 and sys.argv[1] == "gui":
        try:
            import gui  # noqa: F401
        except Exception:
            print("PySimpleGUI not installed")
            return
    # interactive REPL
    while True:
        try:
            line = input("knot> ")
        except EOFError:
            break
        if not line:
            continue
        if line.strip().lower() in {"exit", "quit"}:
            break
        cli.run(shlex.split(line))


if __name__ == "__main__":
    main()
