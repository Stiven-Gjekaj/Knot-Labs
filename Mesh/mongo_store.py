from __future__ import annotations

import os
from typing import Any, Dict, Optional

try:
    from pymongo import MongoClient  # type: ignore
    from pymongo.collection import Collection  # type: ignore
    from pymongo.errors import PyMongoError  # type: ignore
except Exception as e:  # pragma: no cover
    MongoClient = None  # type: ignore
    Collection = None  # type: ignore
    PyMongoError = Exception  # type: ignore

_client: Optional[MongoClient] = None  # type: ignore


def _uri() -> str:
    return os.environ.get("MONGO_URI", "").strip()


def _db_name() -> str:
    return os.environ.get("MONGO_DB", "knot")


def get_client() -> Optional[MongoClient]:  # type: ignore
    global _client
    if _client is not None:
        return _client
    uri = _uri()
    if not uri or MongoClient is None:
        return None
    _client = MongoClient(uri, serverSelectionTimeoutMS=2000)  # type: ignore
    try:
        # light check to initialize
        _client.admin.command("ping")  # type: ignore
    except Exception:
        pass
    return _client


def get_db():  # type: ignore
    cl = get_client()
    if cl is None:
        return None
    return cl[_db_name()]  # type: ignore


def _users_col() -> Optional[Collection]:  # type: ignore
    db = get_db()
    if db is None:
        return None
    col = db["users"]  # type: ignore
    try:
        col.create_index("userID", unique=True)
        col.create_index("username", unique=False)
    except Exception:
        pass
    return col


def _posts_col() -> Optional[Collection]:  # type: ignore
    db = get_db()
    if db is None:
        return None
    col = db["posts"]  # type: ignore
    try:
        col.create_index("postID", unique=True)
        col.create_index("creator", unique=False)
    except Exception:
        pass
    return col


def save_user(user: Dict[str, Any]) -> None:
    col = _users_col()
    if col is None:
        return
    uid = user.get("userID")
    if not uid:
        return
    try:
        col.update_one({"userID": uid}, {"$set": dict(user)}, upsert=True)
    except PyMongoError:
        pass


def save_post(post: Dict[str, Any]) -> None:
    col = _posts_col()
    if col is None:
        return
    pid = post.get("postID")
    if not pid:
        return
    try:
        col.update_one({"postID": pid}, {"$set": dict(post)}, upsert=True)
    except PyMongoError:
        pass


def mongo_health() -> Dict[str, Any]:
    uri = _uri()
    if not uri or MongoClient is None:
        return {"ok": False, "configured": False}
    cl = get_client()
    if cl is None:
        return {"ok": False, "configured": True, "error": "no client"}
    try:
        cl.admin.command("ping")  # type: ignore
        return {"ok": True, "configured": True, "db": _db_name()}
    except Exception as e:
        return {"ok": False, "configured": True, "error": str(e)}

