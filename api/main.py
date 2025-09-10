from __future__ import annotations

import os
import uuid
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Request, Response, UploadFile, File
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import logging
import time as _time
try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST  # type: ignore
except Exception:  # pragma: no cover
    Counter = Histogram = None  # type: ignore
    def generate_latest():  # type: ignore
        return b""
    CONTENT_TYPE_LATEST = "text/plain"
from pydantic import BaseModel
try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None  # type: ignore

from api.jobs import job_queue
import sys
from Mesh.category import make_category_from_micro

from Mesh.tools.gen_user import make_user, save_user
from Mesh.tools.gen_videos import make_post, save_post
from Mesh.drift_adapter import mesh_user_to_drift_user, mesh_posts_to_drift_candidates
from Drift.drift_ranker import rank_videos
from Scribe.search import build_index
from Mesh.analytics import category_stats
from api.label_index import ensure_index, embed_video, ann_search, rerank_with_frames
try:
    from Mesh.mongo_store import mongo_health as _mongo_health, save_user as save_user_mongo, save_post as save_post_mongo  # type: ignore
except Exception:
    _mongo_health = None  # type: ignore
    save_user_mongo = None  # type: ignore
    save_post_mongo = None  # type: ignore


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MESH_DIR = os.path.join(ROOT, 'Mesh')
USERS_DIR = os.path.join(MESH_DIR, 'Users')
POSTS_DIR = os.path.join(MESH_DIR, 'Posts')
MASTER_PATH = os.path.join(MESH_DIR, 'mastercategories.txt')
UPLOADS_DIR = os.path.join(MESH_DIR, 'Uploads')


app = FastAPI(title="Knot-Labs API")

# Structured logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Metrics
REQ_COUNT = Counter('knot_requests_total', 'Total API requests', ['path', 'method']) if Counter else None
REQ_LAT = Histogram('knot_request_latency_seconds', 'Request latency', ['path', 'method']) if Histogram else None
JOBS_COUNT = Counter('knot_jobs_total', 'Jobs processed', ['type', 'status']) if Counter else None

# Static UI mount (simple web UI under /ui)
try:
    static_dir = os.path.join(ROOT, 'api', 'static')
    if os.path.isdir(static_dir):
        app.mount('/ui', StaticFiles(directory=static_dir, html=True), name='ui')
except Exception:
    pass


@app.get('/')
def _root_redirect():
    # Convenience: redirect root to UI if available
    return RedirectResponse(url='/ui')

# Optional CORS (for GitHub Pages or other hosts)
_cors = os.environ.get('KNOT_CORS_ORIGINS', '').strip()
if _cors:
    origins = [o.strip() for o in _cors.split(',') if o.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=['*'],
            allow_headers=['*'],
        )

@app.get('/metrics')
def _metrics():  # type: ignore
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)  # type: ignore

@app.middleware('http')
async def _timing_mw(request: Request, call_next):  # type: ignore
    path = request.url.path
    method = request.method
    start = _time.time()
    try:
        response = await call_next(request)
        return response
    finally:
        dur = max(0.0, _time.time() - start)
        if REQ_COUNT:
            REQ_COUNT.labels(path=path, method=method).inc()
        if REQ_LAT:
            REQ_LAT.labels(path=path, method=method).observe(dur)
        logging.info({'event': 'request', 'path': path, 'method': method, 'latency_s': round(dur, 4)})

# Simple API key auth and rate limiting (in-memory)
API_KEY = os.environ.get("KNOT_API_KEY")
RATE_WINDOW_SECS = 60
DEFAULT_LIMIT = 60  # requests per window
_rate_store: dict[tuple[str, str], list[float]] = {}

# Lightweight cache (Redis if available, else in-memory)
KNOT_CACHE_ENABLED = (os.environ.get("KNOT_CACHE_ENABLED", "1")).lower() in {"1", "true", "yes", "on"}
KNOT_CACHE_TTL = int(os.environ.get("KNOT_CACHE_TTL", "60"))
KNOT_CACHE_PREFIX = os.environ.get("KNOT_CACHE_PREFIX", "knot:cache")
_cache_store: dict[str, tuple[float, str]] = {}

# Serving uploads (disabled by default)
SERVE_UPLOADS = (os.environ.get("KNOT_SERVE_UPLOADS", "0").lower() in {"1", "true", "yes", "on"})

# Optional Redis wiring (config via env)
REDIS_URL = os.environ.get("REDIS_URL", "")
RATE_BACKEND = os.environ.get("KNOT_RATE_BACKEND", "memory").lower()
redis_client: Optional["redis.Redis"] = None  # type: ignore[name-defined]


def _init_redis() -> Optional["redis.Redis"]:  # type: ignore[name-defined]
    if not REDIS_URL or not redis:
        return None
    try:
        import ssl as _ssl  # type: ignore
        _cert_map = {
            'none': getattr(_ssl, 'CERT_NONE', 0),
            'optional': getattr(_ssl, 'CERT_OPTIONAL', 1),
            'required': getattr(_ssl, 'CERT_REQUIRED', 2),
        }
        _ssl_cert_reqs_env = os.environ.get('REDIS_SSL_CERT_REQS', '').strip().lower()
        _ssl_cert_reqs = _cert_map.get(_ssl_cert_reqs_env) if _ssl_cert_reqs_env else None
        kwargs: Dict[str, Any] = {
            'decode_responses': True,
            'socket_connect_timeout': 3,
            'socket_timeout': 3,
            'retry_on_timeout': True,
            'health_check_interval': 30,
        }
        if _ssl_cert_reqs is not None:
            kwargs['ssl_cert_reqs'] = _ssl_cert_reqs
        r = redis.from_url(REDIS_URL, **kwargs)  # type: ignore[attr-defined]
        return r
    except Exception as e:  # pragma: no cover
        logging.warning({'event': 'redis_init_failed', 'error': str(e)})
        return None


def _client_id(req: Request) -> str:
    # Use API key if provided; else fall back to client host
    key = req.headers.get("x-api-key") or ""
    if key:
        return f"key:{key}"
    # On some servers, client host may be None
    return f"ip:{getattr(req.client, 'host', 'unknown')}"


def _check_auth(req: Request) -> None:
    if API_KEY is None:
        return  # auth disabled if key not set
    key = req.headers.get("x-api-key")
    if not key or key != API_KEY:
        raise HTTPException(401, "Unauthorized")


def _check_rate(req: Request, limit: int = DEFAULT_LIMIT) -> None:
    import time
    now = time.time()
    ident = _client_id(req)
    scope = req.url.path
    # Optional Redis-backed fixed window limiting
    if RATE_BACKEND == 'redis' and redis_client is not None:
        try:
            window = int(now // RATE_WINDOW_SECS)
            key = f"knot:ratelimit:{ident}:{scope}:{window}"
            p = redis_client.pipeline()  # type: ignore[attr-defined]
            p.incr(key, amount=1)
            p.expire(key, RATE_WINDOW_SECS + 1)
            count, _ = p.execute()
            if int(count or 0) > limit:
                raise HTTPException(429, "Too Many Requests")
            return
        except HTTPException:
            raise
        except Exception:
            # Fallback to in-memory on Redis errors
            pass
    # In-memory sliding window (default)
    k = (ident, scope)
    arr = _rate_store.get(k) or []
    arr = [t for t in arr if now - t <= RATE_WINDOW_SECS]
    if len(arr) >= limit:
        raise HTTPException(429, "Too Many Requests")
    arr.append(now)
    _rate_store[k] = arr


def _cache_get(key: str) -> Optional[str]:
    if not KNOT_CACHE_ENABLED:
        return None
    # Prefer Redis if connected
    if redis_client is not None:
        try:
            v = redis_client.get(f"{KNOT_CACHE_PREFIX}:{key}")  # type: ignore[attr-defined]
            return v if isinstance(v, str) else (v.decode('utf-8') if v else None)  # type: ignore[no-any-return]
        except Exception:
            # fall back to memory on errors
            pass
    # Memory fallback
    import time
    now = time.time()
    item = _cache_store.get(key)
    if not item:
        return None
    exp, val = item
    if now >= exp:
        _cache_store.pop(key, None)
        return None
    return val


def _cache_set(key: str, val: str, ttl: Optional[int] = None) -> None:
    if not KNOT_CACHE_ENABLED:
        return
    t = int(ttl or KNOT_CACHE_TTL)
    # Prefer Redis if connected
    if redis_client is not None:
        try:
            redis_client.setex(f"{KNOT_CACHE_PREFIX}:{key}", t, val)  # type: ignore[attr-defined]
            return
        except Exception:
            # fall back to memory on errors
            pass
    # Memory fallback
    import time
    _cache_store[key] = (time.time() + t, val)


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
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    job_queue.start(_handle_job)
    # Initialize Redis if configured
    global redis_client
    redis_client = _init_redis()

    # Optionally warm cache store (no-op). This keeps variables referenced.
    if not KNOT_CACHE_ENABLED:
        logging.info({'event': 'cache_disabled'})


@app.on_event("shutdown")
def _shutdown():
    # Stop background worker
    try:
        job_queue.stop()
    except Exception:
        pass
    # Close Redis connection
    global redis_client
    try:
        if redis_client is not None:
            redis_client.close()  # type: ignore[call-arg]
    except Exception:
        pass


def _handle_job(job: Dict[str, Any]) -> Any:
    if job.get('type') == 'classify_post':
        # Run Veil classification and update post categories
        from demo import _run_veil_and_get_categories, _load_json, _save_json
        post_path = job['post_path']
        media_path = job['media_path']
        cats = _run_veil_and_get_categories(media_path, topk=14)
        post = _load_json(post_path)
        post['Category'] = make_category_from_micro(cats)
        _save_json(post_path, post)
        if JOBS_COUNT:
            JOBS_COUNT.labels(type='classify_post', status='ok').inc()
        return {'post': post.get('postID'), 'categories': cats}
    return {'status': 'unknown'}


@app.post("/users")
def api_create_user(req: CreateUser, request: Request):
    _check_auth(request)
    _check_rate(request)
    u = make_user(username=req.username)
    save_user(u, USERS_DIR)
    try:
        from Mesh.sqlite_store import save_user as save_user_db  # type: ignore
        save_user_db(u)
    except Exception:
        pass
    try:
        if save_user_mongo is not None:
            save_user_mongo(u)  # type: ignore
    except Exception:
        pass
    return u


@app.post("/posts")
def api_create_post(req: CreatePost, request: Request):
    _check_auth(request)
    _check_rate(request)
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
    try:
        from Mesh.sqlite_store import save_post as save_post_db  # type: ignore
        save_post_db(post)
    except Exception:
        pass
    try:
        if save_post_mongo is not None:
            save_post_mongo(post)  # type: ignore
    except Exception:
        pass
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
def api_job_status(job_id: str, request: Request):
    _check_rate(request)
    return job_queue.status(job_id)


@app.post('/jobs/{job_id}/cancel')
def api_job_cancel(job_id: str, request: Request):
    _check_auth(request)
    _check_rate(request)
    ok = job_queue.cancel(job_id)
    return {'ok': bool(ok), 'job_id': job_id, 'status': job_queue.status(job_id)}


@app.get('/jobs/debug')
def api_jobs_debug(request: Request):
    _check_auth(request)
    _check_rate(request)
    return job_queue.debug()


def get_redis() -> Optional["redis.Redis"]:  # type: ignore[name-defined]
    return redis_client


@app.get('/health/redis')
def health_redis():
    if not redis_client:
        return {"ok": False, "configured": False}
    try:
        redis_client.ping()  # type: ignore[call-arg]
        return {"ok": True, "configured": True}
    except Exception as e:
        raise HTTPException(503, f"Redis unhealthy: {e}")


@app.get('/ping')
def ping():
    return {"ok": True, "time": int(_time.time())}


class RedisSetReq(BaseModel):
    value: str
    ttl: Optional[int] = None


@app.put('/redis/kv/{key}')
def redis_kv_put(key: str, body: RedisSetReq, request: Request):
    _check_auth(request)
    _check_rate(request)
    if not redis_client:
        raise HTTPException(503, 'Redis not configured')
    try:
        if body.ttl and int(body.ttl) > 0:
            redis_client.setex(key, int(body.ttl), body.value)  # type: ignore[attr-defined]
        else:
            redis_client.set(key, body.value)  # type: ignore[attr-defined]
        ttl = int(redis_client.ttl(key))  # type: ignore[attr-defined]
        return {"ok": True, "key": key, "ttl": ttl}
    except Exception as e:
        raise HTTPException(500, f"Redis error: {e}")


@app.get('/redis/kv/{key}')
def redis_kv_get(key: str, request: Request):
    _check_rate(request)
    if not redis_client:
        return {"ok": False, "configured": False}
    try:
        v = redis_client.get(key)  # type: ignore[attr-defined]
        ttl = int(redis_client.ttl(key))  # type: ignore[attr-defined]
        if v is not None and not isinstance(v, str):
            try:
                v = v.decode('utf-8')
            except Exception:
                v = str(v)
        return {"ok": True, "key": key, "value": v, "ttl": ttl}
    except Exception as e:
        raise HTTPException(500, f"Redis error: {e}")


@app.delete('/redis/kv/{key}')
def redis_kv_delete(key: str, request: Request):
    _check_auth(request)
    _check_rate(request)
    if not redis_client:
        raise HTTPException(503, 'Redis not configured')
    try:
        n = int(redis_client.delete(key))  # type: ignore[attr-defined]
        return {"ok": True, "key": key, "deleted": n}
    except Exception as e:
        raise HTTPException(500, f"Redis error: {e}")


@app.post('/upload')
async def upload_file(request: Request, file: UploadFile = File(...)):
    """Upload a media file to the server and return its saved path.
    Requires API key when `KNOT_API_KEY` is set.
    """
    _check_auth(request)
    _check_rate(request)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    # Derive safe filename: keep extension, randomize name
    orig = (file.filename or '').strip()
    _, ext = os.path.splitext(orig)
    ext = (ext or '')[:10]
    name = uuid.uuid4().hex + ext
    dest = os.path.join(UPLOADS_DIR, name)
    # Stream to disk
    size = 0
    with open(dest, 'wb') as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            size += len(chunk)
    # Basic MIME detection from extension
    import mimetypes
    mime, _ = mimetypes.guess_type(orig or name)
    return {"ok": True, "filename": name, "path": dest, "size": size, "mime": mime or "application/octet-stream"}


def _resolve_upload_path(filename: str) -> str:
    # Ensure no path traversal and the file exists under UPLOADS_DIR
    bn = os.path.basename(filename)
    if bn != filename or (os.path.sep in filename) or (os.path.altsep and os.path.altsep in filename):
        raise HTTPException(400, 'Invalid filename')
    path = os.path.join(UPLOADS_DIR, bn)
    if not os.path.isfile(path):
        raise HTTPException(404, 'Not found')
    return path


@app.get('/uploads/{filename}')
def get_upload(filename: str, request: Request):
    # Optional: disabled unless KNOT_SERVE_UPLOADS is truthy
    if not SERVE_UPLOADS:
        raise HTTPException(404, 'Not found')
    _check_rate(request)
    import mimetypes
    path = _resolve_upload_path(filename)
    mt, _ = mimetypes.guess_type(path)
    return FileResponse(path, media_type=mt or 'application/octet-stream')


class CacheFlushReq(BaseModel):
    prefix: Optional[str] = None


@app.post('/cache/flush')
def api_cache_flush(request: Request, body: Optional[CacheFlushReq] = None, prefix: Optional[str] = None):
    _check_auth(request)
    _check_rate(request)
    mem_before = len(_cache_store)
    _cache_store.clear()
    deleted = 0
    used_pattern = None
    pf = prefix or (body.prefix if body else None) or KNOT_CACHE_PREFIX
    if redis_client is not None and pf:
        pat = pf if any(ch in pf for ch in ['*', '?', '[']) else (pf + ':*')
        used_pattern = pat
        try:
            batch: list[str] = []
            for key in redis_client.scan_iter(match=pat):  # type: ignore[attr-defined]
                batch.append(key)  # type: ignore[arg-type]
                if len(batch) >= 200:
                    deleted += int(redis_client.delete(*batch))  # type: ignore[attr-defined]
                    batch.clear()
            if batch:
                deleted += int(redis_client.delete(*batch))  # type: ignore[attr-defined]
        except Exception as e:
            return {"ok": True, "memory_cleared": mem_before, "redis_deleted": deleted, "pattern": used_pattern, "redis_error": str(e)}
    return {"ok": True, "memory_cleared": mem_before, "redis_deleted": deleted, "pattern": used_pattern}


@app.post('/interactions/{action}')
def api_interaction(action: str, req: Interaction, request: Request):
    _check_auth(request)
    _check_rate(request)
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
    cat = post.get('Category') or {}
    v_delta = 1 if action == 'like' else 2 if action == 'comment' else 3 if action == 'share' else int(max(1, amount))
    c_delta = v_delta
    viewer, creator = _bump_user_after_action(viewer, creator, cat, v_delta, c_delta)
    post = _apply_action_to_post(post, action, amount)
    _save_json(v_path, viewer)
    _save_json(c_path, creator)
    _save_json(p_path, post)
    return {'ok': True}


@app.get('/rank')
def api_rank(request: Request, user: str, k: int = 20):
    _check_rate(request)
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
def api_search(request: Request, q: str, k: int = 10, backend: str = 'bow'):
    _check_rate(request)
    import hashlib, json
    # Try cache first (avoid building index if hit)
    hq = hashlib.sha1((q or '').encode('utf-8')).hexdigest()
    ckey = f"search:{backend}:{k}:{hq}"
    cached = _cache_get(ckey)
    if cached:
        try:
            data = json.loads(cached)
            return {'results': data}
        except Exception:
            pass
    # Cache miss: perform search
    idx = build_index(POSTS_DIR, backend=backend)
    res = idx.search(q, k=k)
    out = [{'postID': pid, 'score': sc} for pid, sc in res]
    try:
        _cache_set(ckey, json.dumps(out))
    except Exception:
        pass
    return {'results': out}


@app.get('/analytics/categories')
def api_category_stats(request: Request):
    _check_rate(request)
    stats = category_stats(POSTS_DIR)
    return stats


@app.get('/categories/tree')
def api_categories_tree(request: Request):
    _check_rate(request)
    tree_path = os.path.join(MESH_DIR, 'master_tree.json')
    if not os.path.isfile(tree_path):
        # Try to build on-demand using integrated builder
        try:
            from Mesh.tools.build_mastercategories import build_tree_and_write  # type: ignore
            build_tree_and_write(out_path=MASTER_PATH, tree_out=tree_path, mesos=3, micros=3)
        except Exception as e:
            raise HTTPException(404, f'Category tree not found and build failed: {e}')
    try:
        import json
        data = json.load(open(tree_path, 'r', encoding='utf-8'))
        return data
    except Exception as e:
        raise HTTPException(500, f'Failed to read category tree: {e}')


@app.get('/health/mongo')
def api_health_mongo():
    if _mongo_health is None:
        return {"ok": False, "configured": False}
    res = _mongo_health()  # type: ignore
    if not bool(res.get("ok")):
        raise HTTPException(503, f"Mongo unhealthy: {res}")
    return res


@app.get('/classify/ann')
def api_classify_ann(request: Request, video_path: str, k: int = 10, frames: int = 8, model: str = 'ViT-B/32', stage2: bool = True, use_audio: bool = False, w_video: float = 0.7, w_speech: float = 0.2, w_audio: float = 0.1, agg: str = 'mean'):
    _check_rate(request)
    master = MASTER_PATH
    idx = ensure_index(master, out_dir=os.path.join(ROOT, 'indexes'), model_name=model, mode='video')
    E = idx['emb']  # type: ignore[index]
    labels = idx['labels']  # type: ignore[index]
    index = idx['index']  # type: ignore[index]
    frames_emb, pooled = embed_video(video_path, model_name=model, frames=int(frames), device='cpu')
    # Stage 1 video ANN
    top = ann_search(E, labels, pooled, k=int(k), index=index)
    # Optional audio fusion (YAMNet)
    audio_info = None
    if bool(use_audio) and w_audio > 0:
        try:
            from veil.fusion.yamnet_events import score_events_to_labels  # type: ignore
            # Compute CLIP-based label scores using YAMNet top events as evidence
            emap = score_events_to_labels(
                video_path,
                labels,
                model_name=model,
                topn_events=15,
                label_emb=None,
            )
            import numpy as _np
            Sv = (pooled @ E.T)[0]
            Sa = _np.array([emap[lbl] for lbl in labels], dtype=_np.float32)
            def _mm(x):
                if not hasattr(x, 'size') or not x.size:
                    return x
                mn, mx = float(x.min(initial=0.0)), float(x.max(initial=0.0))
                return (x - mn) / (mx - mn + 1e-9)
            fused = w_video * _mm(Sv) + w_audio * _mm(Sa)
            order = _np.argsort(fused)[::-1][: int(k)]
            top = [(labels[i], float(fused[i]), int(i)) for i in order]
            audio_info = {'used': True, 'backend': 'yamnet'}
        except Exception:
            audio_info = {'used': False, 'backend': 'none'}
    if stage2 and top:
        top_idx = [t[2] for t in top]
        rer = rerank_with_frames(top_idx, E, frames_emb, agg=str(agg))
        out = [{'label': labels[i], 'score': sc} for i, sc in rer[:k]]
    else:
        out = [{'label': lbl, 'score': sc} for lbl, sc, _ in top]
    return {'results': out, 'k': k, 'frames': frames, 'model': model, 'audio': audio_info}
