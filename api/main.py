from __future__ import annotations

import os
import uuid
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from api.jobs import job_queue

from Mesh.tools.gen_user import make_user, save_user
from Mesh.tools.gen_videos import make_post, save_post
from Mesh.drift_adapter import mesh_user_to_drift_user, mesh_posts_to_drift_candidates
from Drift.drift_ranker import rank_videos
from Scribe.search import build_index
from Mesh.analytics import category_stats


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MESH_DIR = os.path.join(ROOT, 'Mesh')
USERS_DIR = os.path.join(MESH_DIR, 'Users')
POSTS_DIR = os.path.join(MESH_DIR, 'Posts')
MASTER_PATH = os.path.join(MESH_DIR, 'mastercategories.txt')

app = FastAPI(title="Knot-Labs API")


class CreateUser(BaseModel):
    username: Optional[str] = None


class CreatePost(BaseModel):
    creator: str
    description: Optional[str] = "Description Here"
    media_path: Optional[str] = None


class Interaction(BaseModel):
    viewer: str
    creator: str
    post: str
    amount: Optional[float] = 0.0


@app.on_event("startup")
def _startup():
    os.makedirs(USERS_DIR, exist_ok=True)
    os.makedirs(POSTS_DIR, exist_ok=True)
    job_queue.start(_handle_job)


def _handle_job(job: Dict[str, Any]) -> Any:
    if job.get('type') == 'classify_post':
        # Run Veil classification and update post categories
        from demo import _run_veil_and_get_categories, _load_json, _save_json
        post_path = job['post_path']
        media_path = job['media_path']
        cats = _run_veil_and_get_categories(media_path, topk=5)
        post = _load_json(post_path)
        post['Categories'] = cats
        _save_json(post_path, post)
        return {'post': post.get('postID'), 'categories': cats}
    return {'status': 'unknown'}


@app.post("/users")
def api_create_user(req: CreateUser):
    u = make_user(username=req.username)
    save_user(u, USERS_DIR)
    return u


@app.post("/posts")
def api_create_post(req: CreatePost):
    # Find creator by ID or username
    creator_id = req.creator
    # If username was supplied, scan users dir
    if len(creator_id) < 32:  # crude check; usernames likely shorter than UUID
        for name in os.listdir(USERS_DIR):
            if not name.endswith('.json'):
                continue
            import json
            p = os.path.join(USERS_DIR, name)
            try:
                u = json.load(open(p, 'r', encoding='utf-8'))
            except Exception:
                continue
            if u.get('username') == creator_id:
                creator_id = u.get('userID')
                break
    post = make_post(creator_id, categories=[])
    if req.description:
        post['description'] = req.description
    path = save_post(post, POSTS_DIR)
    job_id = None
    if req.media_path:
        job = {
            'id': uuid.uuid4().hex,
            'type': 'classify_post',
            'post_path': path,
            'media_path': req.media_path,
        }
        job_id = job_queue.submit(job)
    return {'post': post, 'job_id': job_id}


@app.get('/jobs/{job_id}')
def api_job_status(job_id: str):
    return job_queue.status(job_id)


@app.post('/interactions/{action}')
def api_interaction(action: str, req: Interaction):
    if action not in {'like','comment','share','gift'}:
        raise HTTPException(400, 'Unknown action')
    from demo import _find_user, _find_post, _apply_action_to_post, _bump_user_after_action, _save_json
    fv = _find_user(req.viewer)
    fc = _find_user(req.creator)
    fp = _find_post(req.post)
    if not (fv and fc and fp):
        raise HTTPException(404, 'Viewer, creator, or post not found')
    v_path, viewer = fv
    c_path, creator = fc
    p_path, post = fp
    amount = float(req.amount or 0)
    cats = post.get('Categories', [])
    v_delta = 1 if action == 'like' else 2 if action == 'comment' else 3 if action == 'share' else int(max(1, amount))
    c_delta = v_delta
    viewer, creator = _bump_user_after_action(viewer, creator, cats, v_delta, c_delta)
    post = _apply_action_to_post(post, action, amount)
    _save_json(v_path, viewer)
    _save_json(c_path, creator)
    _save_json(p_path, post)
    return {'ok': True}


@app.get('/rank')
def api_rank(user: str, k: int = 20):
    # Map Mesh user/posts to Drift
    # Load mesh user by id or username
    u: Optional[Dict[str, Any]] = None
    import json
    for name in os.listdir(USERS_DIR) if os.path.isdir(USERS_DIR) else []:
        if not name.endswith('.json'):
            continue
        p = os.path.join(USERS_DIR, name)
        try:
            uu = json.load(open(p,'r',encoding='utf-8'))
        except Exception:
            continue
        if uu.get('userID') == user or uu.get('username') == user:
            u = uu
            break
    if u is None:
        raise HTTPException(404, 'User not found')
    duser = mesh_user_to_drift_user(u)
    cands = mesh_posts_to_drift_candidates(POSTS_DIR)
    ranked = rank_videos(duser, cands)
    out = [{'id': r.id, 'creator': r.creator_id, 'category': r.category, 'score': r.score} for r in ranked[:k]]
    return {'results': out}


@app.get('/search')
def api_search(q: str, k: int = 10, backend: str = 'bow'):
    idx = build_index(POSTS_DIR, backend=backend)
    res = idx.search(q, k=k)
    return {'results': [{'postID': pid, 'score': sc} for pid, sc in res]}


@app.get('/analytics/categories')
def api_category_stats():
    stats = category_stats(POSTS_DIR)
    return stats

