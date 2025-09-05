import json
import os
import random
from typing import Dict, List, Tuple
from models import VideoCandidate, User
from drift_ranker import rank_videos

def load_user_profile(user: User) -> None:
    # Load engagement profile, preferring update_data/user_profile_{id}.json; fall back to root.
    new_dir = "update_data"
    new_path = os.path.join(new_dir, f"user_profile_{user.id}.json")
    legacy_path = f"user_profile_{user.id}.json"
    path = new_path if os.path.exists(new_path) else legacy_path
    if not os.path.exists(path):
        return
    try:
        with open(path, "r") as f:
            profile = json.load(f)
        # Populate fields if available
        user.watched_videos = profile.get("watched_videos", user.watched_videos)
        user.creator_engagement = profile.get("creator_engagement", user.creator_engagement)
    except Exception:
        # If profile is malformed, skip silently to avoid breaking demo
        pass

def save_user_profile(user: User) -> None:
    # Persist engagement profile to update_data/user_profile_{id}.json.
    out_dir = "update_data"
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"user_profile_{user.id}.json")
    profile = {
        "watched_videos": user.watched_videos,
        "creator_engagement": user.creator_engagement,
    }
    with open(path, "w") as f:
        json.dump(profile, f, indent=2)


def _merge_from_file(user: User) -> Tuple[int, int]:
    """Merge updates from user's JSON file into memory and persist.

    Returns a tuple: (watched_added, creators_updated)
    """
    in_dir = "update_data"
    path = os.path.join(in_dir, f"user_profile_{user.id}.json")
    if not os.path.exists(path):
        return (0, 0)
    try:
        with open(path, "r") as f:
            profile = json.load(f)
    except Exception:
        return (0, 0)

    watched_before = set(user.watched_videos)
    file_watched: List[str] = profile.get("watched_videos", []) or []
    # Preserve existing order; append new ones from file order
    added_watch = 0
    for vid in file_watched:
        if vid not in watched_before:
            user.watched_videos.append(vid)
            added_watch += 1
            watched_before.add(vid)

    file_eng: Dict[str, int] = profile.get("creator_engagement", {}) or {}
    # Treat file values as absolute targets if greater than current; otherwise keep current
    # This avoids accidental downgrades while letting manual bumps take effect
    creators_updated = 0
    for cid, target in file_eng.items():
        cur = user.creator_engagement.get(cid, 0)
        if target > cur:
            user.creator_engagement[cid] = target
            creators_updated += 1

    save_user_profile(user)
    return (added_watch, creators_updated)


def _add_manual_updates(user: User, all_video_ids: set, add_watched: List[str], add_eng: Dict[str, int]) -> Tuple[int, int]:
    """Apply manual updates to a user and persist.

    - add_watched: list of video IDs to append if not already present
    - add_eng: dict of creator_id -> increment (added to current)

    Returns a tuple: (watched_added, creators_touched)
    """
    added = 0
    for vid in add_watched:
        if vid in all_video_ids and vid not in user.watched_videos:
            user.watched_videos.append(vid)
            added += 1

    touched = 0
    for cid, inc in add_eng.items():
        if inc == 0:
            continue
        user.creator_engagement[cid] = user.creator_engagement.get(cid, 0) + inc
        touched += 1

    save_user_profile(user)
    return (added, touched)

def rank_and_print(users, videos, header_prefix=""):
    for user in users:
        ranked = rank_videos(user, videos)
        prefs = ", ".join(user.preferred_categories) if user.preferred_categories else "none"
        print(f"\n{header_prefix}User {user.id} (fav: {prefs}) - Ranked videos:")
        for v in ranked:
            print(f"{v.id} | {v.category} | creator {v.creator_id} | score={v.score:.2f}")
    return


def simulate_random_engagement(users, videos, top_pool: int = 20, fav_bias: float = 0.7):
    """Simulate engagement with a bias toward preferred categories.
    - Chooses a random subset size per user (3-7 videos)
    - Samples from the user's current top `top_pool` ranked videos
    - Prefers categories in `user.preferred_categories` (~fav_bias of picks)
    - Increments engagement a bit more for favorites
    """
    fav_bias = max(0.0, min(1.0, fav_bias))
    for user in users:
        ranked = rank_videos(user, videos)
        pool_size = min(top_pool, len(ranked))
        if pool_size == 0:
            continue
        k = min(random.randint(3, 7), pool_size)
        pool = ranked[:pool_size]
        favs = [v for v in pool if v.category in set(user.preferred_categories)]
        others = [v for v in pool if v.category not in set(user.preferred_categories)]

        target_favs = int(round(k * fav_bias)) if favs else 0
        take_favs = min(len(favs), target_favs)
        take_others = min(len(others), k - take_favs)

        chosen = []
        if take_favs > 0:
            chosen.extend(random.sample(favs, take_favs))
        if take_others > 0:
            chosen.extend(random.sample(others, take_others))

        # If still short due to limited pool on one side, fill from the other
        if len(chosen) < k:
            remaining = k - len(chosen)
            leftovers = [v for v in pool if v not in chosen]
            if leftovers:
                chosen.extend(random.sample(leftovers, min(remaining, len(leftovers))))

        for v in chosen:
            if v.id not in user.watched_videos:
                user.watched_videos.append(v.id)
            if v.category in user.preferred_categories:
                inc = random.randint(2, 3)
            else:
                inc = random.randint(1, 2)
            user.creator_engagement[v.creator_id] = user.creator_engagement.get(v.creator_id, 0) + inc
        save_user_profile(user)


def _load_data():
    """Load users and candidate videos from the new data folder.
    Falls back to deprecated sample_data.json if needed (with a warning).
    """
    # Preferred flat files under data/
    users_path = os.path.join("data", "users.json")
    videos_path = os.path.join("data", "videos.json")
    if os.path.exists(users_path) and os.path.exists(videos_path):
        with open(users_path, "r") as f:
            users_data = json.load(f)
        with open(videos_path, "r") as f:
            candidates_data = json.load(f)
        return users_data, candidates_data, False

    # Backward-compat for previous subfolder layout
    old_users_path = os.path.join("data", "users", "users.json")
    old_videos_path = os.path.join("data", "videos", "videos.json")
    if os.path.exists(old_users_path) and os.path.exists(old_videos_path):
        with open(old_users_path, "r") as f:
            users_data = json.load(f)
        with open(old_videos_path, "r") as f:
            candidates_data = json.load(f)
        return users_data, candidates_data, True

    # Deprecated combined file support
    legacy_path = "sample_data.json"
    if os.path.exists(legacy_path):
        with open(legacy_path, "r") as f:
            data = json.load(f)
        users_data = data.get("users") or [data.get("user")]
        candidates_data = data.get("candidates", [])
        return users_data, candidates_data, True

    raise FileNotFoundError(
        "No data files found. Run generate_sample_data.py to create data/users.json and data/videos.json."
    )


def main():
    # Load data (prefers new layout under data/; falls back with deprecation notice)
    users_data, candidates_data, used_legacy = _load_data()
    if used_legacy:
        print("[deprecated] Loaded from legacy path(s). Please switch to data/users.json and data/videos.json.")

    videos = [VideoCandidate(**v) for v in candidates_data]
    all_video_ids = {v.id for v in videos}

    # Build users and load prior engagement
    users = []
    for user_data in users_data:
        user = User(**user_data)
        load_user_profile(user)
        users.append(user)

    # No automatic printing; use 'show' commands to view rankings

    # Interactive loop with manual update options
    print("\nCommands:")
    print("  show                          -> print current rankings")
    print("  show user <userId>            -> print that user's top 20")
    print("  update                        -> interactively add watched/engagement and save")
    print("  update random [N]             -> simulate N random updates (default 1)")
    print("  update random user <userId> [N] -> simulate N random updates for one user")
    print("  update watched <userId> <v..> -> add video IDs to watched and save")
    print("  update engage <userId> <cid:count ..> -> add creator engagement and save")
    print("  update import [userId]        -> merge from file(s) in update_data and save")
    print("  quit                          -> exit")
    try:
        while True:
            try:
                cmd = input("> ").strip().lower()
            except EOFError:
                break
            if cmd in ("quit", "exit", "q"):
                break
            elif cmd.startswith("show"):
                parts = cmd.split()
                if len(parts) == 1:
                    rank_and_print(users, videos)
                    continue
                if len(parts) >= 3 and parts[1] == "user":
                    uid = parts[2]
                    target_user = None
                    for u in users:
                        if u.id.lower() == uid.lower():
                            target_user = u
                            break
                    if not target_user:
                        print("User not found.")
                        continue
                    rank_and_print([target_user], videos, header_prefix="Top 20 - ")
                    continue
                print("Usage: show OR show user <userId>")
            elif cmd.startswith("update"):
                parts = cmd.split()
                # update random [N]  OR  update random user <userId> [N]
                if len(parts) >= 2 and parts[1] == "random":
                    # Single-user variant
                    if len(parts) >= 3 and parts[2] == "user":
                        if len(parts) < 4:
                            print("Usage: update random user <userId> [N]")
                            continue
                        uid = parts[3]
                        count = 1
                        if len(parts) >= 5:
                            try:
                                count = int(parts[4])
                                if count < 1:
                                    raise ValueError()
                            except ValueError:
                                print("Invalid count. Usage: update random user <userId> [N] where N>=1")
                                continue
                        target_user = None
                        for u in users:
                            if u.id.lower() == uid.lower():
                                target_user = u
                                break
                        if not target_user:
                            print("User not found.")
                            continue
                        for _ in range(count):
                            simulate_random_engagement([target_user], videos, top_pool=20)
                        print(f"Applied {count} random update(s) to {target_user.id}. Use 'show user {target_user.id}' to view.")
                        continue

                    # All-users variant
                    count = 1
                    if len(parts) >= 3:
                        try:
                            count = int(parts[2])
                            if count < 1:
                                raise ValueError()
                        except ValueError:
                            print("Invalid count. Usage: 'update random' or 'update random N' where N>=1")
                            continue
                    for _ in range(count):
                        simulate_random_engagement(users, videos, top_pool=20)
                    print(f"Applied {count} random update(s) to all users. Use 'show' to view rankings.")
                    continue

                # update watched <userId> <v1 v2 ...>
                if len(parts) >= 2 and parts[1] == "watched":
                    if len(parts) < 4:
                        print("Usage: update watched <userId> <v1 v2 ...>")
                        continue
                    uid = parts[2]
                    add_watched = parts[3:]
                    target_user = None
                    for u in users:
                        if u.id.lower() == uid.lower():
                            target_user = u
                            break
                    if not target_user:
                        print("User not found.")
                        continue
                    w_added, _ = _add_manual_updates(target_user, all_video_ids, add_watched, {})
                    print(f"Added {w_added} watched id(s). Saved to update_data. Use 'show' to view rankings.")
                    continue

                # update engage <userId> <cid:count ...>
                if len(parts) >= 2 and parts[1] == "engage":
                    if len(parts) < 4:
                        print("Usage: update engage <userId> <cid:count ...>")
                        continue
                    uid = parts[2]
                    target_user = None
                    for u in users:
                        if u.id.lower() == uid.lower():
                            target_user = u
                            break
                    if not target_user:
                        print("User not found.")
                        continue
                    add_eng: Dict[str, int] = {}
                    for tok in parts[3:]:
                        if ":" not in tok:
                            print(f"Skipping invalid pair '{tok}', expected cid:count")
                            continue
                        cid, sval = tok.split(":", 1)
                        try:
                            inc = int(sval)
                        except ValueError:
                            print(f"Skipping invalid count in '{tok}'")
                            continue
                        add_eng[cid] = add_eng.get(cid, 0) + inc
                    if not add_eng:
                        print("No valid engagement increments provided.")
                        continue
                    _, c_touched = _add_manual_updates(target_user, all_video_ids, [], add_eng)
                    print(f"Updated {c_touched} creator(s). Saved to update_data. Use 'show' to view rankings.")
                    continue

                # update import [userId]
                if len(parts) >= 2 and parts[1] == "import":
                    target_user_id = parts[2] if len(parts) >= 3 else None
                    affected = 0
                    for user in users:
                        if target_user_id and user.id != target_user_id:
                            continue
                        w_add, c_upd = _merge_from_file(user)
                        if w_add or c_upd:
                            affected += 1
                    if affected == 0:
                        print("No changes merged from update_data.")
                    else:
                        print(f"Merged updates for {affected} user(s). Use 'show' to view rankings.")
                    continue

                # Plain 'update' -> interactive manual add
                try:
                    target_user = None
                    uid = input("User ID to update (e.g. user2): ").strip()
                    for u in users:
                        if u.id.lower() == uid.lower():
                            target_user = u
                            break
                    if not target_user:
                        print("User not found.")
                        continue

                    w_line = input("Video IDs to add to watched (space-separated, blank for none): ").strip()
                    e_line = input("Creator engagements to add as cid:count (space-separated, blank for none): ").strip()

                    add_watched: List[str] = [tok for tok in w_line.split() if tok]
                    add_eng: Dict[str, int] = {}
                    for tok in e_line.split():
                        if ":" not in tok:
                            print(f"Skipping invalid pair '{tok}', expected cid:count")
                            continue
                        cid, sval = tok.split(":", 1)
                        try:
                            inc = int(sval)
                        except ValueError:
                            print(f"Skipping invalid count in '{tok}'")
                            continue
                        add_eng[cid] = add_eng.get(cid, 0) + inc

                    w_added, c_touched = _add_manual_updates(target_user, all_video_ids, add_watched, add_eng)
                    print(f"Added {w_added} watched id(s), updated {c_touched} creator(s). Saved to update_data. Use 'show' to view rankings.")
                except KeyboardInterrupt:
                    print("\nCanceled.")
                    continue
            elif cmd == "":
                continue
            else:
                print("Unknown command. Use 'update', 'show', or 'quit'.")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
