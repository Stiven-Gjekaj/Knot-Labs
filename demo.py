#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Dict, List, Optional, Tuple
from Mesh.tools.gen_videos import make_post, save_post  # type: ignore
from Mesh.category import make_category_from_micro, ensure_category, make_category_with_limits
from Mesh.tools.gen_videos import make_post, save_post  # type: ignore
from Mesh.category import make_category_from_micro, ensure_category


ROOT = os.path.dirname(os.path.abspath(__file__))
MESH_DIR = os.path.join(ROOT, "Mesh")
USERS_DIR = os.path.join(MESH_DIR, "Users")
POSTS_DIR = os.path.join(MESH_DIR, "Posts")
MASTER_PATH = os.path.join(MESH_DIR, "mastercategories.txt")


def _ensure_dirs() -> None:
    os.makedirs(USERS_DIR, exist_ok=True)
    os.makedirs(POSTS_DIR, exist_ok=True)


def _load_json(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: str, data: Dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _find_user(identifier: str) -> Optional[Tuple[str, Dict]]:
    # identifier can be userID or username
    if not os.path.isdir(USERS_DIR):
        return None
    for name in os.listdir(USERS_DIR):
        if not name.endswith(".json"):
            continue
        p = os.path.join(USERS_DIR, name)
        try:
            u = _load_json(p)
        except Exception:
            continue
        if u.get("userID") == identifier or u.get("username") == identifier:
            return (p, u)
    return None


def _find_post(post_id: str) -> Optional[Tuple[str, Dict]]:
    p = os.path.join(POSTS_DIR, f"{post_id}.json")
    if os.path.isfile(p):
        return (p, _load_json(p))
    # fallback: scan
    if not os.path.isdir(POSTS_DIR):
        return None
    for name in os.listdir(POSTS_DIR):
        if not name.endswith(".json"):
            continue
        fp = os.path.join(POSTS_DIR, name)
        try:
            v = _load_json(fp)
        except Exception:
            continue
        if v.get("postID") == post_id:
            return (fp, v)
    return None


def create_test_user(username: Optional[str] = None, gender: Optional[str] = None) -> Dict:
    _ensure_dirs()
    from Mesh.tools.gen_user import make_user, save_user  # type: ignore
    if username is None:
        username = input("Enter a username for the test user: ").strip() or None
    user = make_user(username=username, gender=gender)
    path = save_user(user, USERS_DIR)
    try:
        from Mesh.sqlite_store import save_user as save_user_db  # type: ignore
        save_user_db(user)
    except Exception:
        pass
    # Optional Mongo write-through
    try:
        from Mesh.mongo_store import save_user as save_user_mongo  # type: ignore
        save_user_mongo(user)
    except Exception:
        pass
    print(f"Created user at {path}\n{json.dumps(user, indent=2)}")
    return user


def _run_veil_and_get_categories(media_path: str, topk: int = 14) -> List[str]:
    # Call Veil CLI and parse Predictions line.
    cmd = [
        sys.executable,
        "-m",
        "veil.run",
        "--mode",
        "video",
        "--video",
        media_path,
        "--master_labels_file",
        MASTER_PATH,
        # Enable ANN fusion by default; YAMNet handles audio
        "--use_ann","true",
        "--ann_k","64",
        "--ann_agg","mean",
        "--use_whisper","true",
        "--w_video","0.7",
        "--w_audio","0.3",
        "--topk",
        str(topk),
    ]
    env = os.environ.copy()
    veil_src = os.path.join(ROOT, "Veil", "src")
    env["PYTHONPATH"] = (veil_src + os.pathsep + env.get("PYTHONPATH", ""))
    # Run Veil with a timeout to avoid hanging jobs
    try:
        timeout_s = int(os.environ.get("KNOT_VEIL_TIMEOUT_SEC", "180"))
    except Exception:
        timeout_s = 180
    try:
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                env=env,
                timeout=timeout_s,
            )
        except TypeError:
            # Some test doubles may not accept 'timeout' kwarg; retry without it
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                env=env,
            )
        out = (res.stdout or "") + "\n" + (res.stderr or "")
    except subprocess.TimeoutExpired:
        out = ""
        print(f"Veil classification timed out after {timeout_s}s; using fallback labels.")
    except subprocess.CalledProcessError as e:
        out = (e.stdout or "") + "\n" + (e.stderr or "")
        print("Veil classification failed; attempting fallback.")
    def _to_category(label: str) -> str:
        l = label.strip()
        lowers = l.lower()
        prefixes = [
            "a video about ",
            "a video of ",
            "video about ",
            "video of ",
            "a photo of ",
            "photo of ",
        ]
        for p in prefixes:
            if lowers.startswith(p):
                return l[len(p):].strip()
        return l

    cats: List[str] = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Predictions: "):
            payload = line[len("Predictions: "):].strip()
            cats = [_to_category(c) for c in payload.split(",") if c.strip()]
            break
    if len(cats) < topk:
        # Fallback: fill from Mesh/mastercategories.txt to reach topk
        try:
            fallback: List[str] = []
            with open(MASTER_PATH, "r", encoding="utf-8") as f:
                for raw in f:
                    raw = raw.strip()
                    if not raw or raw.startswith("#"):
                        continue
                    if "|" in raw:
                        left = raw.split("|", 1)[0].strip()
                        fallback.append(_to_category(left))
            for c in fallback:
                if len(cats) >= topk:
                    break
                if c not in cats:
                    cats.append(c)
        except Exception:
            print("Warning: Veil produced insufficient predictions and fallback failed.")
    return cats[:topk]


def post_and_classify(creator_identifier: Optional[str] = None, media_path: Optional[str] = None, country: Optional[str] = None) -> Dict:
    _ensure_dirs()
    creator = creator_identifier or input("Enter creator userID or username: ").strip()
    media = media_path or input("Enter path to media file for Veil: ").strip()
    found = _find_user(creator)
    if not found:
        print("Creator not found. Create a user first.")
        return {}
    user_path, user = found
    # Create base post JSON via Mesh tool
    post = make_post(user["userID"], categories=[], country=country)  # start empty
    post_path = save_post(post, POSTS_DIR)
    try:
        from Mesh.sqlite_store import save_post as save_post_db  # type: ignore
        save_post_db(post)
    except Exception:
        pass
    # Optional Mongo write-through
    try:
        from Mesh.mongo_store import save_post as save_post_mongo  # type: ignore
        save_post_mongo(post)
    except Exception:
        pass
    print(f"Created post at {post_path}. Running Veil classification...")
    cats = _run_veil_and_get_categories(media)
    # Limit Veil classification buckets to macro=2, meso=4, micro=8
    post["Category"] = make_category_with_limits(cats[:14], macro_n=2, meso_n=4, micro_n=8)
    _save_json(post_path, post)
    print(f"Updated post category: {post['Category']}")
    return post


def _bump_user_after_action(viewer: Dict, creator: Dict, category: Dict, viewer_delta: int, creator_delta: int) -> Tuple[Dict, Dict]:
    # ViewerScore: map creatorID -> points
    cid = creator.get("userID")
    if cid:
        viewer.setdefault("ViewerScore", {})
        viewer["ViewerScore"][cid] = int(viewer["ViewerScore"].get(cid, 0) + viewer_delta)
    # CategoryScores: bump each micro category
    viewer.setdefault("CategoryScores", {})
    micro = (category.get("micro") if isinstance(category, dict) else []) or []
    for c in micro:
        viewer["CategoryScores"][c] = int(viewer["CategoryScores"].get(c, 0) + max(1, viewer_delta))
    # RecentCreators tracking
    if cid:
        rc = viewer.setdefault("RecentCreators", [])
        rc.append(cid)
        # keep last 20
        if len(rc) > 20:
            del rc[:-20]
    # CreatorScore bump
    creator["CreatorScore"] = int(creator.get("CreatorScore", 0) + creator_delta)
    return viewer, creator


def _apply_action_to_post(post: Dict, action: str, amount: int | float = 0) -> Dict:
    if action == "like":
        post["likesCount"] = int(post.get("likesCount", 0) + 1)
        post["Score"] = float(post.get("Score", 0.0) + 1.0)
    elif action == "comment":
        post["commentsCount"] = int(post.get("commentsCount", 0) + 1)
        post["Score"] = float(post.get("Score", 0.0) + 2.0)
    elif action == "share":
        post["shareCount"] = int(post.get("shareCount", 0) + 1)
        post["Score"] = float(post.get("Score", 0.0) + 3.0)
    elif action == "gift":
        post["giftsCount"] = int(post.get("giftsCount", 0) + 1)
        post["Score"] = float(post.get("Score", 0.0) + float(amount))
    elif action == "ppv":
        post["payPerViewCount"] = int(post.get("payPerViewCount", 0) + 1)
        post["Score"] = float(post.get("Score", 0.0) + 0.5)
    return post


def _interaction(action: str, viewer_identifier: Optional[str] = None, creator_identifier: Optional[str] = None, post_id: Optional[str] = None, amount: float = 0.0) -> None:
    _ensure_dirs()
    viewer_id = viewer_identifier or input("Enter viewer userID or username: ").strip()
    creator_id = creator_identifier or input("Enter creator userID or username: ").strip()
    if post_id is None:
        post_id = input("Enter postID: ").strip()
    if action == "gift" and amount <= 0:
        try:
            amount = float(input("Enter gift amount (number): ").strip())
        except Exception:
            amount = 1.0
    fv = _find_user(viewer_id)
    fc = _find_user(creator_id)
    fp = _find_post(post_id)
    if not (fv and fc and fp):
        print("Viewer, creator, or post not found.")
        return
    v_path, viewer = fv
    c_path, creator = fc
    p_path, post = fp

    # Apply increments
    category = ensure_category(post)
    if action == "like":
        v_delta, c_delta = 1, 1
    elif action == "comment":
        v_delta, c_delta = 2, 2
    elif action == "share":
        v_delta, c_delta = 3, 3
    elif action == "gift":
        v_delta, c_delta = int(max(1, amount)), int(max(1, amount))
    else:
        v_delta, c_delta = 1, 1

    viewer, creator = _bump_user_after_action(viewer, creator, category, v_delta, c_delta)
    viewer.setdefault("SeenPosts", [])
    viewer["SeenPosts"].append(post.get("postID"))

    post = _apply_action_to_post(post, action, amount)

    # Persist
    _save_json(v_path, viewer)
    _save_json(c_path, creator)
    _save_json(p_path, post)
    print(f"Applied {action}. Updated viewer, creator, and post.")


def like_post(viewer_identifier: Optional[str] = None, creator_identifier: Optional[str] = None, post_id: Optional[str] = None) -> None:
    _interaction("like", viewer_identifier, creator_identifier, post_id)


def comment_post(viewer_identifier: Optional[str] = None, creator_identifier: Optional[str] = None, post_id: Optional[str] = None) -> None:
    _interaction("comment", viewer_identifier, creator_identifier, post_id)


def share_post(viewer_identifier: Optional[str] = None, creator_identifier: Optional[str] = None, post_id: Optional[str] = None) -> None:
    _interaction("share", viewer_identifier, creator_identifier, post_id)


def gift_post(viewer_identifier: Optional[str] = None, creator_identifier: Optional[str] = None, post_id: Optional[str] = None, amount: float = 0.0) -> None:
    _interaction("gift", viewer_identifier, creator_identifier, post_id, amount)


def rank_for_user(identifier: Optional[str] = None) -> List[Tuple[str, float]]:
    # Build Drift user and candidates from Mesh data and rank
    _ensure_dirs()
    if not identifier:
        identifier = input("Enter active userID or username: ").strip()
    found = _find_user(identifier)
    if not found:
        print("User not found.")
        return []
    _, u = found

    from Mesh.drift_adapter import mesh_user_to_drift_user, mesh_posts_to_drift_candidates  # type: ignore
    from Drift.drift_ranker import rank_videos  # type: ignore
    duser = mesh_user_to_drift_user(u)
    candidates = mesh_posts_to_drift_candidates(POSTS_DIR)
    ranked = rank_videos(duser, candidates)
    print("Top 20 for user:")
    out: List[Tuple[str, float]] = []
    for i, rv in enumerate(ranked[:20], 1):
        print(f"{i:2d}. {rv.id} | {rv.creator_id} | {rv.category} | score={rv.score}")
        out.append((rv.id, rv.score))
    return out


def search_posts_ui(query: Optional[str] = None, k: int = 10, backend: str = "bow") -> List[Tuple[str, float]]:
    # Run Scribe search over Mesh posts
    if not query:
        query = input("Enter search query: ").strip()
    if not query:
        print("Empty query")
        return []
    try:
        from Scribe.search import build_index  # type: ignore
    except Exception as e:
        print(f"Search not available: {e}")
        return []
    idx = build_index(POSTS_DIR, backend=backend)
    results = idx.search(query, k=k)
    print("Search results:")
    for pid, sc in results:
        print(f"  {pid} | score={sc:.3f}")
    return results


def simulate_update() -> None:
    # Simulate some interactions across posts for basic sanity
    _ensure_dirs()
    # Load all users and videos
    users: List[Tuple[str, Dict]] = []
    if os.path.isdir(USERS_DIR):
        for n in os.listdir(USERS_DIR):
            if n.endswith(".json"):
                p = os.path.join(USERS_DIR, n)
                try:
                    users.append((p, _load_json(p)))
                except Exception:
                    pass
    videos: List[Tuple[str, Dict]] = []
    if os.path.isdir(POSTS_DIR):
        for n in os.listdir(POSTS_DIR):
            if n.endswith(".json"):
                p = os.path.join(POSTS_DIR, n)
                try:
                    videos.append((p, _load_json(p)))
                except Exception:
                    pass
    if not users or not videos:
        print("Need at least one user and one video.")
        return
    import random
    actions = ["like", "comment", "share", "gift"]
    for _ in range(min(25, len(videos) * 3)):
        v_path, viewer = random.choice(users)
        c_path, creator = random.choice(users)
        p_path, post = random.choice(videos)
        act = random.choice(actions)
        amount = random.choice([1, 2, 5, 10]) if act == "gift" else 0
        category = ensure_category(post)
        v_delta = 1 if act == "like" else 2 if act == "comment" else 3 if act == "share" else int(max(1, amount))
        c_delta = v_delta
        viewer, creator = _bump_user_after_action(viewer, creator, category, v_delta, c_delta)
        post = _apply_action_to_post(post, act, amount)
        _save_json(v_path, viewer)
        _save_json(c_path, creator)        
        _save_json(p_path, post)
    print("Simulated interactions complete.")


def main() -> None:
    _ensure_dirs()
    menu = {
        "1": ("Create test user", create_test_user),
        "2": ("Post (create + Veil analyze)", post_and_classify),
        "3": ("Like a post", like_post),
        "4": ("Comment on a post", comment_post),
        "5": ("Share a post", share_post),
        "6": ("Gift a post", gift_post),
        "7": ("Rank (top 20 for user)", rank_for_user),
        "8": ("Update (simulate interactions)", simulate_update),
        "9": ("Search posts", search_posts_ui),
        "q": ("Quit", None),
    }
    while True:
        print("\nKnot-Labs Demo")
        for k in menu.keys():
            print(f"{k}. {menu[k][0]}")
        choice = input("Choose an option: ").strip()
        if choice == "q" or choice.lower() in {"q", "quit", "exit"}:
            print("Goodbye.")
            break
        item = menu.get(choice)
        if not item:
            print("Invalid choice.")
            continue
        try:
            item[1]()  # type: ignore
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()

