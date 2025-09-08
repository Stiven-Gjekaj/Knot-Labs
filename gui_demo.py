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
        root.geometry("1000x720")
        # Dark theme with light red accents
        try:
            style = ttk.Style(root)
            style.theme_use('clam')
            bg = '#0b0b0e'; card = '#141416'; fg = '#e5e7eb'; border = '#23242a'; primary = '#f87171'
            root.configure(bg=bg)
            style.configure('.', background=bg, foreground=fg)
            style.configure('TFrame', background=bg)
            style.configure('TLabelframe', background=card, foreground=fg, bordercolor=border)
            style.configure('TLabelframe.Label', background=card, foreground=fg)
            style.configure('TLabel', background=card, foreground=fg)
            style.configure('TEntry', fieldbackground='#1a1b1f', foreground=fg)
            style.configure('TCombobox', fieldbackground='#1a1b1f', foreground=fg)
            style.configure('TButton', background=primary, foreground='#1b1b1b', borderwidth=1)
            style.map('TButton', background=[('active', '#ef4444')])
        except Exception:
            pass

        main = ttk.Frame(root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=1)

        title = ttk.Label(main, text="Knot-Labs GUI", font=("Segoe UI", 14, "bold"))
        title.grid(row=0, column=0, sticky="w", pady=(0, 8))

        # Theme selector (Dark/Light)
        f_theme = ttk.LabelFrame(main, text="Appearance")
        f_theme.grid(row=1, column=0, sticky="ew", pady=4)
        ttk.Label(f_theme, text="Theme").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.theme_sel = ttk.Combobox(f_theme, values=["Dark","Light"], state="readonly", width=10)
        self.theme_sel.set("Dark")
        self.theme_sel.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Button(f_theme, text="Apply", command=lambda: self.apply_theme(self.theme_sel.get())).grid(row=0, column=2, padx=5, pady=5)

        # Create User
        f_user = ttk.LabelFrame(main, text="Create User")
        f_user.grid(row=2, column=0, sticky="ew", pady=4)
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
        f_post.grid(row=3, column=0, sticky="ew", pady=4)
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
        # Fast classify (ANN) — align with web UI
        ttk.Label(f_post, text="ANN K").grid(row=4, column=0, padx=5, pady=5, sticky="e")
        self.ann_k = ttk.Entry(f_post, width=6)
        self.ann_k.insert(0, "10")
        self.ann_k.grid(row=4, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(f_post, text="Frames").grid(row=4, column=2, padx=5, pady=5, sticky="e")
        self.ann_frames = ttk.Entry(f_post, width=6)
        self.ann_frames.insert(0, "8")
        self.ann_frames.grid(row=4, column=3, padx=5, pady=5, sticky="w")
        ttk.Label(f_post, text="Model").grid(row=5, column=0, padx=5, pady=5, sticky="e")
        self.ann_model = ttk.Combobox(f_post, values=["ViT-B/32","ViT-B/16","ViT-L/14","ViT-H/14","ViT-g/14"], state="readonly", width=10)
        self.ann_model.set("ViT-B/32")
        self.ann_model.grid(row=5, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(f_post, text="Aggregation").grid(row=5, column=2, padx=5, pady=5, sticky="e")
        self.ann_agg = ttk.Combobox(f_post, values=["mean","max","softmax"], state="readonly", width=10)
        self.ann_agg.set("mean")
        self.ann_agg.grid(row=5, column=3, padx=5, pady=5, sticky="w")
        # Audio fusion controls
        self.use_audio = tk.BooleanVar(value=False)
        ttk.Label(f_post, text="Use Audio (CLAP)").grid(row=6, column=0, padx=5, pady=5, sticky="e")
        ttk.Checkbutton(f_post, variable=self.use_audio).grid(row=6, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(f_post, text="Weights v/a").grid(row=6, column=2, padx=5, pady=5, sticky="e")
        self.w_video = ttk.Entry(f_post, width=6); self.w_video.insert(0, "1.0")
        self.w_audio = ttk.Entry(f_post, width=6); self.w_audio.insert(0, "0.0")
        self.w_video.grid(row=6, column=3, padx=2, pady=5, sticky="w")
        self.w_audio.grid(row=6, column=4, padx=2, pady=5, sticky="w")
        ttk.Button(f_post, text="Classify (ANN)", command=self.on_classify_ann).grid(row=7, column=0, padx=5, pady=5, sticky="w")

        # Generators (randomized; only count inputs)
        f_gen = ttk.LabelFrame(main, text="Generators")
        f_gen.grid(row=4, column=0, sticky="ew", pady=4)
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

        # Category Browser (like website)
        f_tree = ttk.LabelFrame(main, text="Category Browser")
        f_tree.grid(row=5, column=0, sticky="nsew", pady=4)
        f_tree.columnconfigure(0, weight=1)
        f_tree.rowconfigure(1, weight=1)
        ttk.Button(f_tree, text="Load Categories", command=self.on_load_categories).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        # Treeview with scrollbar
        tree_frame = ttk.Frame(f_tree)
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(tree_frame, show='tree')
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        # Log
        self.log = ScrolledText(main, height=16, wrap="word")
        self.log.grid(row=9, column=0, sticky="nsew", pady=8)
        main.rowconfigure(9, weight=1)

        # Quit
        ttk.Button(main, text="Quit", command=root.destroy).grid(row=9, column=0, sticky="e")

        # Redirect stdout/stderr
        sys.stdout = TextRedirector(self.log)  # type: ignore
        sys.stderr = TextRedirector(self.log)  # type: ignore

    # UI Actions
    def apply_theme(self, name: str) -> None:
        try:
            style = ttk.Style(self.root)
            style.theme_use('clam')
            if (name or '').lower().startswith('light'):
                bg = '#f5f6f8'; card = '#ffffff'; fg = '#1f2937'; border = '#e5e7eb'; primary = '#ef4444'
            else:
                bg = '#0b0b0e'; card = '#141416'; fg = '#e5e7eb'; border = '#23242a'; primary = '#f87171'
            self.root.configure(bg=bg)
            style.configure('.', background=bg, foreground=fg)
            style.configure('TFrame', background=bg)
            style.configure('TLabelframe', background=card, foreground=fg, bordercolor=border)
            style.configure('TLabelframe.Label', background=card, foreground=fg)
            style.configure('TLabel', background=card, foreground=fg)
            style.configure('TEntry', fieldbackground=('#ffffff' if name.lower().startswith('light') else '#1a1b1f'), foreground=fg)
            style.configure('TCombobox', fieldbackground=('#ffffff' if name.lower().startswith('light') else '#1a1b1f'), foreground=fg)
            style.configure('TButton', background=primary, foreground=('#1b1b1b' if name.lower().startswith('dark') else '#ffffff'), borderwidth=1)
            style.map('TButton', background=[('active', '#ef4444')])
        except Exception:
            pass
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

    def on_classify_ann(self) -> None:
        try:
            media = self.media_path.get().strip()
            if not os.path.isfile(media):
                _notify(self.log, "Select a valid media file")
                return
            try:
                k = int(self.ann_k.get().strip() or "10")
            except Exception:
                k = 10
            # Import locally to avoid hard dependency if missing
            try:
                from api.label_index import ensure_index, embed_video, ann_search, rerank_with_frames, build_label_embeddings_audio, embed_audio_from_video  # type: ignore
            except Exception as e:  # pragma: no cover
                _notify(self.log, f"ANN unavailable: {e}")
                return
            model = (self.ann_model.get() or "ViT-B/32").strip()
            frames = 8
            try:
                frames = int((self.ann_frames.get() or "8").strip())
            except Exception:
                pass
            idx = ensure_index(os.path.join("Mesh", "mastercategories.txt"), out_dir="indexes", model_name=model, mode="video")
            E = idx['emb']; labels = idx['labels']; index = idx['index']
            frames_emb, pooled = embed_video(media, model_name=model, frames=frames, device='cpu')
            top = ann_search(E, labels, pooled, k=int(k), index=index)
            # Optional audio fusion
            try:
                if self.use_audio.get():
                    Ea, labels_a = build_label_embeddings_audio(os.path.join("Mesh","mastercategories.txt"), mode='video')
                    qa = embed_audio_from_video(media)
                    if qa is not None and Ea.size and len(labels_a) == len(labels):
                        import numpy as _np
                        Sv = (pooled @ E.T)[0]; Sa = (qa @ Ea.T)[0]
                        def _mm(x):
                            if not x.size:
                                return x
                            mn, mx = float(x.min(initial=0.0)), float(x.max(initial=0.0))
                            return (x - mn) / (mx - mn + 1e-9)
                        try:
                            wv = float(self.w_video.get().strip() or '1.0'); wa = float(self.w_audio.get().strip() or '0.0')
                        except Exception:
                            wv, wa = 1.0, 0.0
                        fused = wv * _mm(Sv) + wa * _mm(Sa)
                        order = _np.argsort(fused)[::-1][: int(k)]
                        top = [(labels[i], float(fused[i]), int(i)) for i in order]
            except Exception:
                pass
            if top:
                top_idx = [t[2] for t in top]
                agg = (self.ann_agg.get() or 'mean').strip()
                rer = rerank_with_frames(top_idx, E, frames_emb, agg=agg)
                out = [(labels[i], sc) for i, sc in rer[: k]]
                _notify(self.log, f"ANN top-{k}:")
                for lbl, sc in out:
                    _notify(self.log, f"  {lbl}: {round(sc,3)}")
            else:
                _notify(self.log, "No ANN results")
        except Exception as e:
            _notify(self.log, f"Error: {e}")

    def on_load_categories(self) -> None:
        try:
            tree_path = os.path.join("Mesh", "master_tree.json")
            if not os.path.isfile(tree_path):
                _notify(self.log, "Tree not found. Run build_mastercategories_tree.py first.")
                return
            import json
            with open(tree_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # clear tree
            for it in self.tree.get_children():
                self.tree.delete(it)
            # populate
            for macro, mesos in (data or {}).items():
                mid = self.tree.insert('', 'end', text=str(macro))
                if isinstance(mesos, dict):
                    for meso, micros in mesos.items():
                        sid = self.tree.insert(mid, 'end', text=str(meso))
                        if isinstance(micros, list):
                            for mi in micros:
                                self.tree.insert(sid, 'end', text=str(mi))
            _notify(self.log, "Loaded categories tree")
        except Exception as e:
            _notify(self.log, f"Error loading tree: {e}")

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
