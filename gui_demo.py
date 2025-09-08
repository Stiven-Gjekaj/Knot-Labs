#!/usr/bin/env python3
from __future__ import annotations

import os
import json
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog
from tkinter.scrolledtext import ScrolledText
from typing import Optional

import demo as core
from Scribe.search import build_index
from Mesh.tools.gen_user import GENDERS as USER_GENDERS  # type: ignore
from Mesh.tools.gen_videos import COUNTRIES as POST_COUNTRIES  # type: ignore


def _ensure_paths_on_sys_path() -> None:
    # Ensure Veil src path is available for subprocess calls that rely on environment
    root = os.path.dirname(os.path.abspath(__file__))
    veil_src = os.path.join(root, 'Veil', 'src')
    if os.path.isdir(veil_src) and veil_src not in (os.environ.get('PYTHONPATH','').split(os.pathsep)):
        os.environ['PYTHONPATH'] = veil_src + os.pathsep + os.environ.get('PYTHONPATH','')


class TextRedirector:
    def __init__(self, widget: tk.Text):
        self.widget = widget

    def write(self, s: str) -> None:
        if not s:
            return
        # Ensure UI update happens on main thread
        self.widget.after(0, lambda: (self.widget.insert(tk.END, s), self.widget.see(tk.END)))

    def flush(self) -> None:  # pragma: no cover
        pass


def _notify(text_widget: tk.Text, text: str) -> None:
    text_widget.insert(tk.END, text + "\n")
    text_widget.see(tk.END)


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Knot-Labs GUI")
        root.geometry("900x650")

        main = ttk.Frame(root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=1)

        title = ttk.Label(main, text="Knot-Labs GUI", font=("Segoe UI", 14, "bold"))
        title.grid(row=0, column=0, sticky="w", pady=(0, 8))

        # Create User
        f_user = ttk.LabelFrame(main, text="Create User")
        f_user.grid(row=1, column=0, sticky="ew", pady=4)
        f_user.columnconfigure(1, weight=1)
        ttk.Label(f_user, text="Username").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.user_name = ttk.Entry(f_user)
        self.user_name.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Label(f_user, text="Gender").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.user_gender = ttk.Combobox(f_user, values=USER_GENDERS, state="readonly", width=10)
        self.user_gender.grid(row=0, column=3, padx=5, pady=5, sticky="w")
        self.user_gender.set(USER_GENDERS[0])
        ttk.Button(f_user, text="Create User", command=self.on_create_user).grid(row=0, column=4, padx=5, pady=5)

        # Create Post + Analyze
        f_post = ttk.LabelFrame(main, text="Create Post + Analyze")
        f_post.grid(row=2, column=0, sticky="ew", pady=4)
        for c in range(3):
            f_post.columnconfigure(c, weight=1 if c == 1 else 0)
        ttk.Label(f_post, text="Creator (userID or username)").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.creator_id = ttk.Entry(f_post)
        self.creator_id.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Label(f_post, text="Media File").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.media_path = ttk.Entry(f_post)
        self.media_path.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(f_post, text="Browse", command=self.on_browse).grid(row=1, column=2, padx=5, pady=5)
        ttk.Label(f_post, text="Country").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.post_country = ttk.Combobox(f_post, values=POST_COUNTRIES, state="readonly", width=10)
        self.post_country.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        if POST_COUNTRIES:
            self.post_country.set(POST_COUNTRIES[0])
        self.analyze_btn = ttk.Button(f_post, text="Post & Analyze", command=self.on_post_analyze)
        self.analyze_btn.grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.analyze_prog = ttk.Progressbar(f_post, mode="indeterminate", length=200)
        self.analyze_prog.grid(row=3, column=1, padx=5, pady=5, sticky="w")

        # Generators (randomized; only count inputs)
        f_gen = ttk.LabelFrame(main, text="Generators")
        f_gen.grid(row=3, column=0, sticky="ew", pady=4)
        for c in range(4):
            f_gen.columnconfigure(c, weight=0)
        # Users generator (random gender)
        ttk.Label(f_gen, text="Users N").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.gen_users_n = ttk.Entry(f_gen, width=6)
        self.gen_users_n.insert(0, "1")
        self.gen_users_n.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Button(f_gen, text="Generate Users", command=self.on_gen_users).grid(row=0, column=2, padx=5, pady=5)
        # Posts generator (random creator + country)
        ttk.Label(f_gen, text="Posts N").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.gen_posts_n = ttk.Entry(f_gen, width=6)
        self.gen_posts_n.insert(0, "1")
        self.gen_posts_n.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ttk.Button(f_gen, text="Generate Posts", command=self.on_gen_posts).grid(row=1, column=2, padx=5, pady=5)
        # Labels builder (count)
        ttk.Label(f_gen, text="Labels N").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.gen_labels_n = ttk.Entry(f_gen, width=6)
        self.gen_labels_n.insert(0, "1000")
        self.gen_labels_n.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ttk.Button(f_gen, text="Rebuild Categories", command=self.on_build_labels).grid(row=2, column=2, padx=5, pady=5)

        # Interact
        f_inter = ttk.LabelFrame(main, text="Interact")
        f_inter.grid(row=4, column=0, sticky="ew", pady=4)
        for c in range(8):
            f_inter.columnconfigure(c, weight=1 if c in (1, 3, 5, 7) else 0)
        ttk.Label(f_inter, text="Viewer").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.viewer_id = ttk.Entry(f_inter)
        self.viewer_id.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Label(f_inter, text="Creator").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.author_id = ttk.Entry(f_inter)
        self.author_id.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        ttk.Label(f_inter, text="PostID").grid(row=0, column=4, padx=5, pady=5, sticky="w")
        self.post_id = ttk.Entry(f_inter)
        self.post_id.grid(row=0, column=5, padx=5, pady=5, sticky="ew")
        ttk.Label(f_inter, text="Gift Amount").grid(row=0, column=6, padx=5, pady=5, sticky="e")
        self.gift_amt = ttk.Entry(f_inter, width=8)
        self.gift_amt.insert(0, "1")
        self.gift_amt.grid(row=0, column=7, padx=5, pady=5, sticky="w")
        # Buttons row
        btns = ttk.Frame(f_inter)
        btns.grid(row=1, column=0, columnspan=8, sticky="w", padx=5, pady=5)
        ttk.Button(btns, text="Like", command=lambda: self.on_interact("Like")).grid(row=0, column=0, padx=2)
        ttk.Button(btns, text="Comment", command=lambda: self.on_interact("Comment")).grid(row=0, column=1, padx=2)
        ttk.Button(btns, text="Share", command=lambda: self.on_interact("Share")).grid(row=0, column=2, padx=2)
        ttk.Button(btns, text="Gift", command=lambda: self.on_interact("Gift")).grid(row=0, column=3, padx=2)

        # Rank
        f_rank = ttk.LabelFrame(main, text="Rank")
        f_rank.grid(row=5, column=0, sticky="ew", pady=4)
        f_rank.columnconfigure(1, weight=1)
        ttk.Label(f_rank, text="Active User").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.active_user = ttk.Entry(f_rank)
        self.active_user.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(f_rank, text="Rank Top 20", command=self.on_rank).grid(row=0, column=2, padx=5, pady=5)
        ttk.Label(f_rank, text="Filter Level").grid(row=1, column=0, padx=5, pady=2, sticky="e")
        self.rank_filter_level = ttk.Combobox(f_rank, values=["None","macro","meso"], state="readonly", width=10)
        self.rank_filter_level.grid(row=1, column=1, padx=5, pady=2, sticky="w")
        self.rank_filter_level.set("None")
        ttk.Label(f_rank, text="Filter Value").grid(row=1, column=2, padx=5, pady=2, sticky="e")
        self.rank_filter_value = ttk.Entry(f_rank, width=18)
        self.rank_filter_value.grid(row=1, column=3, padx=5, pady=2, sticky="w")

        # Search
        f_search = ttk.LabelFrame(main, text="Search")
        f_search.grid(row=6, column=0, sticky="ew", pady=4)
        for c in range(5):
            f_search.columnconfigure(c, weight=1 if c == 1 else 0)
        ttk.Label(f_search, text="Query").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.search_q = ttk.Entry(f_search)
        self.search_q.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Label(f_search, text="Top K").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.search_k = ttk.Entry(f_search, width=6)
        self.search_k.insert(0, "10")
        self.search_k.grid(row=0, column=3, padx=5, pady=5, sticky="w")
        ttk.Button(f_search, text="Search", command=self.on_search).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(f_search, text="Filter Level").grid(row=1, column=1, padx=5, pady=5, sticky="e")
        self.search_filter_level = ttk.Combobox(f_search, values=["None","macro","meso"], state="readonly", width=10)
        self.search_filter_level.grid(row=1, column=2, padx=5, pady=5, sticky="w")
        self.search_filter_level.set("None")
        ttk.Label(f_search, text="Filter Value").grid(row=1, column=3, padx=5, pady=5, sticky="e")
        self.search_filter_value = ttk.Entry(f_search, width=18)
        self.search_filter_value.grid(row=1, column=4, padx=5, pady=5, sticky="w")

        # Simulate
        f_sim = ttk.LabelFrame(main, text="Simulate")
        f_sim.grid(row=7, column=0, sticky="ew", pady=4)
        ttk.Button(f_sim, text="Simulate Interactions", command=self.on_simulate).grid(row=0, column=0, padx=5, pady=5, sticky="w")

        # Log
        self.log = ScrolledText(main, height=16, wrap="word")
        self.log.grid(row=8, column=0, sticky="nsew", pady=8)
        main.rowconfigure(8, weight=1)

        # Quit
        ttk.Button(main, text="Quit", command=root.destroy).grid(row=9, column=0, sticky="e")

        # Redirect stdout/stderr
        sys.stdout = TextRedirector(self.log)  # type: ignore
        sys.stderr = TextRedirector(self.log)  # type: ignore

    # UI Actions
    def on_browse(self) -> None:
        path = filedialog.askopenfilename()
        if path:
            self.media_path.delete(0, tk.END)
            self.media_path.insert(0, path)

    def on_create_user(self) -> None:
        try:
            name = self.user_name.get().strip() or None
            gender = self.user_gender.get().strip() or None
            user = core.create_test_user(name, gender)
            _notify(self.log, f"Created user: {user.get('userID')}")
        except Exception as e:
            _notify(self.log, f"Error: {e}")

    def on_post_analyze(self) -> None:
        creator = self.creator_id.get().strip()
        media = self.media_path.get().strip()
        country = self.post_country.get().strip() or None
        if not os.path.isfile(media):
            _notify(self.log, "Select a valid media file")
            return
        self.analyze_btn.configure(state=tk.DISABLED)
        self.analyze_prog.start(12)
        def worker():
            try:
                post = core.post_and_classify(creator, media, country)
                if post:
                    def _msg():
                        cat = post.get('Category') or {}
                        micro = (cat.get('micro') if isinstance(cat, dict) else []) or []
                        _notify(self.log, f"Created post {post.get('postID')} with cats: {micro}")
                    self.root.after(0, _msg)
                else:
                    self.root.after(0, lambda: _notify(self.log, "Post creation failed (check creator)"))
            except Exception as e:
                self.root.after(0, lambda: _notify(self.log, f"Error: {e}"))
            finally:
                self.root.after(0, lambda: (self.analyze_prog.stop(), self.analyze_btn.configure(state=tk.NORMAL)))
        threading.Thread(target=worker, daemon=True).start()

    def on_gen_users(self) -> None:
        try:
            from Mesh.tools.gen_user import make_user, save_user  # type: ignore
            n = int(self.gen_users_n.get().strip() or "1")
            created = []
            for _ in range(max(1, n)):
                u = make_user(gender=None)
                p = save_user(u, os.path.join("Mesh", "Users"))
                created.append(u.get("userID"))
            _notify(self.log, f"Generated users: {', '.join(created)}")
        except Exception as e:
            _notify(self.log, f"Error: {e}")

    def on_gen_posts(self) -> None:
        try:
            from Mesh.tools.gen_videos import make_post, save_post, load_master_categories, load_users  # type: ignore
            n = int(self.gen_posts_n.get().strip() or "1")
            users = load_users(os.path.join("Mesh", "Users"))
            if not users:
                # QoL: auto-create one user if none exist
                try:
                    from Mesh.tools.gen_user import make_user, save_user  # type: ignore
                    u = make_user(gender=None)
                    save_user(u, os.path.join("Mesh", "Users"))
                    users = [u]
                    _notify(self.log, f"No users found; created user {u.get('userID')}")
                except Exception:
                    _notify(self.log, "No users found and could not auto-create one")
                    return
            cats = load_master_categories(os.path.join("Mesh", "mastercategories.txt"))
            posts_dir = os.path.join("Mesh", "Posts")
            created = []
            import random
            for _ in range(max(1, n)):
                # users may be list of dicts or loaded user dicts
                uid = users[0]["userID"] if isinstance(users[0], dict) else users[0].get("userID")
                cid = uid or random.choice(users)["userID"]
                post = make_post(cid, categories=cats, country=None)
                save_post(post, posts_dir)
                created.append(post.get("postID"))
            _notify(self.log, f"Generated posts: {', '.join(created)}")
        except Exception as e:
            _notify(self.log, f"Error: {e}")

    def on_build_labels(self) -> None:
        """Rebuild Mesh/mastercategories.txt using the builder tool."""
        def worker() -> None:
            try:
                from Mesh.tools.build_mastercategories import build_and_write  # type: ignore
                try:
                    n = int(self.gen_labels_n.get().strip() or "1000")
                except Exception:
                    n = 1000
                stats = build_and_write(target_count=max(1, n))
                # Optionally validate
                try:
                    from Mesh.tools.validate_categories import validate  # type: ignore
                    validate(os.path.join("Mesh", "mastercategories.txt"), expect_min=10)
                except Exception:
                    pass
                self.log.after(0, lambda: _notify(self.log, f"Rebuilt mastercategories.txt: final={stats.get('final')} unique={stats.get('unique')} candidates={stats.get('candidates')}"))
            except Exception as e:
                self.log.after(0, lambda: _notify(self.log, f"Error rebuilding categories: {e}"))
        threading.Thread(target=worker, daemon=True).start()

    def on_interact(self, action: str) -> None:
        try:
            viewer = self.viewer_id.get().strip()
            author = self.author_id.get().strip()
            postid = self.post_id.get().strip()
            if action == "Like":
                core.like_post(viewer, author, postid)
                _notify(self.log, "Applied Like")
            elif action == "Comment":
                core.comment_post(viewer, author, postid)
                _notify(self.log, "Applied Comment")
            elif action == "Share":
                core.share_post(viewer, author, postid)
                _notify(self.log, "Applied Share")
            elif action == "Gift":
                try:
                    amt = float(self.gift_amt.get().strip() or "1")
                except Exception:
                    amt = 1.0
                core.gift_post(viewer, author, postid, amt)
                _notify(self.log, f"Applied Gift ({amt})")
        except Exception as e:
            _notify(self.log, f"Error: {e}")

    def on_rank(self) -> None:
        try:
            active = self.active_user.get().strip()
            out = core.rank_for_user(active)
            if out:
                _notify(self.log, "Top 20:")
                # Filter controls
                level = (self.rank_filter_level.get() or "None").strip().lower()
                val = (self.rank_filter_value.get() or "").strip().lower()
                shown = 0
                for pid, sc in out:
                    macro = meso = ""
                    micro = []
                    try:
                        p = os.path.join(core.POSTS_DIR, f"{pid}.json")
                        data = json.load(open(p, 'r', encoding='utf-8'))
                        cat = data.get('Category') or {}
                        raw_macro = cat.get('macro') or []
                        raw_meso = cat.get('meso') or []
                        macro_list = raw_macro if isinstance(raw_macro, list) else [raw_macro]
                        meso_list = raw_meso if isinstance(raw_meso, list) else [raw_meso]
                        macro = ", ".join([m for m in macro_list if isinstance(m, str)])
                        meso = ", ".join([m for m in meso_list if isinstance(m, str)])
                        micro = (cat.get('micro') if isinstance(cat, dict) else []) or []
                    except Exception:
                        pass
                    # Apply filter if requested
                    if level == 'macro' and val:
                        if not any((m or '').lower() == val for m in macro_list if isinstance(m, str)):
                            continue
                    if level == 'meso' and val:
                        if not any((m or '').lower() == val for m in meso_list if isinstance(m, str)):
                            continue
                    _notify(self.log, f"  {pid} | score={sc} | {macro} | {meso} | {micro}")
                    shown += 1
                    if shown >= 20:
                        break
            else:
                _notify(self.log, "No ranking results for user")
        except Exception as e:
            _notify(self.log, f"Error: {e}")

    def on_search(self) -> None:
        try:
            q = self.search_q.get().strip()
            try:
                k = int(self.search_k.get().strip() or "10")
            except Exception:
                k = 10
            if not q:
                _notify(self.log, "Enter a query")
                return
            try:
                idx = build_index(core.POSTS_DIR, backend='bow')
                res = idx.search(q, k=k)
                _notify(self.log, f"Search results ({len(res)}):")
                level = (self.search_filter_level.get() or "None").strip().lower()
                val = (self.search_filter_value.get() or "").strip().lower()
                for pid, sc in res:
                    macro = meso = ""
                    micro = []
                    try:
                        p = os.path.join(core.POSTS_DIR, f"{pid}.json")
                        data = json.load(open(p, 'r', encoding='utf-8'))
                        cat = data.get('Category') or {}
                        raw_macro = cat.get('macro') or []
                        raw_meso = cat.get('meso') or []
                        macro_list = raw_macro if isinstance(raw_macro, list) else [raw_macro]
                        meso_list = raw_meso if isinstance(raw_meso, list) else [raw_meso]
                        macro = ", ".join([m for m in macro_list if isinstance(m, str)])
                        meso = ", ".join([m for m in meso_list if isinstance(m, str)])
                        micro = (cat.get('micro') if isinstance(cat, dict) else []) or []
                    except Exception:
                        pass
                    if level == 'macro' and val:
                        if not any((m or '').lower() == val for m in macro_list if isinstance(m, str)):
                            continue
                    if level == 'meso' and val:
                        if not any((m or '').lower() == val for m in meso_list if isinstance(m, str)):
                            continue
                    _notify(self.log, f"  {pid} | score={sc:.3f} | {macro} | {meso} | {micro}")
            except Exception as e:
                _notify(self.log, f"Search failed: {e}")
        except Exception as e:
            _notify(self.log, f"Error: {e}")

    def on_simulate(self) -> None:
        def run_sim() -> None:
            try:
                core.simulate_update()
                self.log.after(0, lambda: _notify(self.log, 'Simulation complete.'))
            except Exception as e:
                self.log.after(0, lambda: _notify(self.log, f"Error: {e}"))
        threading.Thread(target=run_sim, daemon=True).start()


def main() -> None:
    _ensure_paths_on_sys_path()
    core._ensure_dirs()

    root = tk.Tk()
    app = App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
