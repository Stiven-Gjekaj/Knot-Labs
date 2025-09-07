#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import time
import uuid
from typing import Dict


GENDERS = ["male", "female", "other"]


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def make_user(username: str | None = None, gender: str | None = None) -> Dict:
    user_id = uuid.uuid4().hex
    if not username:
        username = f"user_{user_id[:8]}"
    if gender is None or gender not in GENDERS:
        gender = random.choice(GENDERS)
    return {
        "username": username,
        "userID": user_id,
        "Gender": gender,
        "SeenPosts": [],
        "RecentCreators": [],
        "CreatorScore": 0,
        "ViewerScore": {},
        "CategoryScores": {},
        "created_at": time.time(),
    }


def save_user(user: Dict, users_dir: str) -> str:
    ensure_dir(users_dir)
    path = os.path.join(users_dir, f"{user['userID']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(user, f, indent=2, ensure_ascii=False)
    return path


def main() -> None:
    p = argparse.ArgumentParser(description="Generate N users under Mesh/Users/")
    p.add_argument("N", type=int, help="number of users to create")
    p.add_argument("--users-dir", default=os.path.join("Mesh", "Users"))
    p.add_argument("--username", help="custom username to use when N=1")
    p.add_argument("--gender", choices=GENDERS, help="optional gender to assign (applies to all created)")
    args = p.parse_args()

    if args.N <= 0:
        raise SystemExit("N must be positive")
    if args.N > 1 and args.username:
        print("--username is ignored when N>1")

    created = []
    for i in range(args.N):
        user = make_user(username=args.username if args.N == 1 else None, gender=args.gender)
        path = save_user(user, args.users_dir)
        created.append((user["userID"], path))
    for uid, path in created:
        print(f"Created user {uid} at {path}")


if __name__ == "__main__":
    main()
