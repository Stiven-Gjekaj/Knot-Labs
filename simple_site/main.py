from __future__ import annotations

import os
import uuid
import json
import time
from typing import List, Dict, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from demo import _run_veil_and_get_categories
from Mesh.tools.gen_videos import make_post, save_post


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MESH_DIR = os.path.join(ROOT, "Mesh")
USERS_DIR = os.path.join(MESH_DIR, "Users")
POSTS_DIR = os.path.join(MESH_DIR, "Posts")
UPLOADS_DIR = os.path.join(MESH_DIR, "Uploads")

app = FastAPI(title="Simple Knot API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LOGS: List[Dict[str, object]] = []

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/ui", StaticFiles(directory=static_dir, html=True), name="ui")


@app.get("/")
def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/ui")


@app.get("/test_api")
def test_api() -> Dict[str, str]:
    LOGS.append({"event": "test_api"})
    return {"status": "ok"}


@app.get("/test_cors")
def test_cors() -> Dict[str, str]:
    LOGS.append({"event": "test_cors"})
    return {"status": "cors ok"}


class LoginRequest(BaseModel):
    userID: str
    username: Optional[str] = None


@app.post("/login")
def login(req: LoginRequest) -> Dict[str, object]:
    os.makedirs(USERS_DIR, exist_ok=True)
    path = os.path.join(USERS_DIR, f"{req.userID}.json")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            user = json.load(f)
    else:
        user = {
            "username": req.username or f"user_{req.userID[:8]}",
            "userID": req.userID,
            "Gender": "other",
            "SeenPosts": [],
            "RecentCreators": [],
            "CreatorScore": 0,
            "ViewerScore": {},
            "CategoryScores": {},
            "created_at": time.time(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(user, f, indent=2, ensure_ascii=False)
    LOGS.append({"event": "login", "userID": req.userID})
    return user


@app.post("/post")
async def create_post(userID: str, file: UploadFile = File(...)) -> Dict[str, object]:
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename)[1]
    upload_path = os.path.join(UPLOADS_DIR, f"{uuid.uuid4().hex}{ext}")
    with open(upload_path, "wb") as f:
        f.write(await file.read())
    cats = _run_veil_and_get_categories(upload_path)
    categories: List[str] = cats if isinstance(cats, list) else []
    post = make_post(userID, categories)
    save_post(post, POSTS_DIR)
    LOGS.append({"event": "post", "userID": userID, "postID": post["postID"]})
    return post

class InteractRequest(BaseModel):
    videoID: str
    viewerID: str
    action: str
    amount: Optional[int] = 1


def _update_user_counts(user_id: str, action: str, received: bool, amount: int) -> None:
    path = os.path.join(USERS_DIR, f"{user_id}.json")
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        user = json.load(f)
    field_map = {
        ("like", True): "likesReceived",
        ("like", False): "likesGiven",
        ("comment", True): "commentsReceived",
        ("comment", False): "commentsGiven",
        ("gift", True): "giftsReceived",
        ("gift", False): "giftsGiven",
        ("share", True): "sharesReceived",
        ("share", False): "sharesGiven",
    }
    field = field_map.get((action, received))
    if not field:
        return
    user[field] = int(user.get(field, 0)) + (amount if action == "gift" else 1)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(user, f, indent=2, ensure_ascii=False)


@app.post("/interact")
def interact(req: InteractRequest) -> Dict[str, str]:
    post_path = os.path.join(POSTS_DIR, f"{req.videoID}.json")
    if not os.path.isfile(post_path):
        raise HTTPException(status_code=404, detail="post not found")
    with open(post_path, "r", encoding="utf-8") as f:
        post = json.load(f)
    action = req.action.lower()
    amt = int(req.amount or 1)
    if action == "like":
        post["likesCount"] = int(post.get("likesCount", 0)) + 1
    elif action == "comment":
        post["commentsCount"] = int(post.get("commentsCount", 0)) + 1
    elif action == "gift":
        post["giftsCount"] = int(post.get("giftsCount", 0)) + amt
    elif action == "share":
        post["shareCount"] = int(post.get("shareCount", 0)) + 1
    else:
        raise HTTPException(status_code=400, detail="invalid action")
    with open(post_path, "w", encoding="utf-8") as f:
        json.dump(post, f, indent=2, ensure_ascii=False)
    creator_id = post.get("creator")
    if creator_id:
        _update_user_counts(creator_id, action, True, amt)
    _update_user_counts(req.viewerID, action, False, amt)
    LOGS.append({
        "event": "interact",
        "action": action,
        "postID": req.videoID,
        "viewerID": req.viewerID,
    })
    return {"status": "ok"}


@app.get("/search")
def search(q: str) -> Dict[str, List[Dict[str, object]]]:
    results: List[Dict[str, object]] = []
    if os.path.isdir(POSTS_DIR):
        for name in os.listdir(POSTS_DIR):
            if not name.endswith(".json"):
                continue
            path = os.path.join(POSTS_DIR, name)
            with open(path, "r", encoding="utf-8") as f:
                post = json.load(f)
            if q.lower() in post.get("description", "").lower():
                results.append(post)
    LOGS.append({"event": "search", "query": q, "results": len(results)})
    return {"results": results}


@app.get("/feed")
def feed() -> Dict[str, List[Dict[str, object]]]:
    posts: List[Dict[str, object]] = []
    if os.path.isdir(POSTS_DIR):
        for name in os.listdir(POSTS_DIR):
            if not name.endswith(".json"):
                continue
            path = os.path.join(POSTS_DIR, name)
            with open(path, "r", encoding="utf-8") as f:
                posts.append(json.load(f))
    posts.sort(key=lambda p: p.get("created_at", 0), reverse=True)
    LOGS.append({"event": "feed", "count": len(posts)})
    return {"results": posts}


@app.get("/logs")
def get_logs() -> Dict[str, List[Dict[str, object]]]:
    return {"logs": LOGS[-100:]}
