from __future__ import annotations

import json
import os
import sqlite3
from typing import Dict, Optional
from .category import ensure_category


def _db_path() -> str:
    env = os.environ.get("KNOT_DB")
    if env:
        return env
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "Mesh", "knot.db")


def init_db(path: Optional[str] = None) -> None:
    dbp = path or _db_path()
    os.makedirs(os.path.dirname(dbp), exist_ok=True)
    con = sqlite3.connect(dbp)
    try:
        cur = con.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                userID TEXT PRIMARY KEY,
                username TEXT,
                gender TEXT,
                created_at REAL,
                json TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS posts (
                postID TEXT PRIMARY KEY,
                creator TEXT,
                category TEXT,
                country TEXT,
                created_at REAL,
                json TEXT NOT NULL
            )
            """
        )
        con.commit()
    finally:
        con.close()


def save_user(user: Dict, path: Optional[str] = None) -> None:
    dbp = path or _db_path()
    init_db(dbp)
    con = sqlite3.connect(dbp)
    try:
        cur = con.cursor()
        cur.execute(
            "REPLACE INTO users(userID, username, gender, created_at, json) VALUES (?, ?, ?, ?, ?)",
            (
                user.get("userID"),
                user.get("username"),
                user.get("Gender"),
                float(user.get("created_at") or 0.0),
                json.dumps(user, ensure_ascii=False),
            ),
        )
        con.commit()
    finally:
        con.close()


def save_post(post: Dict, path: Optional[str] = None) -> None:
    dbp = path or _db_path()
    init_db(dbp)
    con = sqlite3.connect(dbp)
    try:
        cur = con.cursor()
        cat = ensure_category(post)
        macros = cat.get("macro")
        if isinstance(macros, list) and macros:
            category = macros[0]
        else:
            category = macros if isinstance(macros, str) and macros else (cat.get("micro")[:1] or [None])[0]
        cur.execute(
            "REPLACE INTO posts(postID, creator, category, country, created_at, json) VALUES (?, ?, ?, ?, ?, ?)",
            (
                post.get("postID"),
                post.get("creator"),
                category,
                post.get("country"),
                float(post.get("created_at") or 0.0),
                json.dumps(post, ensure_ascii=False),
            ),
        )
        con.commit()
    finally:
        con.close()
