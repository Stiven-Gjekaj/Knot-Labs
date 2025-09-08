# Knot-Labs

Knot-Labs is a compact, multi-component sandbox for prototyping a social media stack. It includes:

- Veil: zero-shot media classifier (video + audio) using prompt-style labels.
- Mesh: local JSON store for users and posts (+simple analytics).
- Drift: transparent, explainable feed ranking over candidate posts.
- Scribe: lightweight full-text search over posts.

Everything is Python. One requirements file: `requirements.txt`.

## Quick Start

- Install (Python 3.10+)
  - `pip install -r requirements.txt`

- Build labels (writes `Mesh/mastercategories.txt`)
  - Flat builder: `python Mesh/tools/build_mastercategories.py --count 1000`
  - Tree builder (macros -> mesos -> micros): `python Mesh/tools/build_mastercategories_tree.py --mesos 3 --micros 3`
    - Integrated alternative: `python Mesh/tools/build_mastercategories.py --use-tree --mesos 3 --micros 3`
    - Uses a fixed macro list (Gaming, Music, Sports, ... 25 total)
    - Pulls mesos/micros from the web when online (Wikipedia); falls back to offline seeds
    - Also writes `Mesh/master_tree.json` with the full hierarchy
  - GUI: `python gui_demo.py`
    - GUI has Generate Users/Posts buttons. If no users exist, Generate Posts will auto-create one.

- Run demo (CLI)
  - `python demo.py`

- Run GUI (Tkinter)
  - `python gui_demo.py`
  - Ships with Python on most platforms. If missing: install your OS tk package (e.g., `sudo apt-get install python3-tk`).

- Start API (FastAPI)
  - `uvicorn api.main:app --reload`
  - Or load env vars from the provided `.env` file:
    - `uvicorn --env-file .env api.main:app --reload`
  - Endpoints:
    - `POST /users`
    - `POST /posts` (optionally classifies with Veil when `media_path` provided)
    - `POST /interactions/{like|comment|share|gift}`
    - `GET /rank?user=<id-or-username>&k=20`
    - `GET /search?q=...&k=10&backend=bow|st`
    - `GET /analytics/categories`
    - `GET /metrics` (Prometheus)
    - `GET /health/redis` (Redis ping)
    - `GET /health/mongo` (Mongo ping)
    - `POST /cache/flush` (admin; clears memory cache and Redis by prefix)
    - `POST /upload` (save media under `Mesh/Uploads`)
    - `GET /uploads/{filename}` (optional; serve uploaded file when enabled)
    - `GET /ping` (simple connectivity check)
    - `GET /classify/ann?video_path=/abs/path.mp4&k=10&frames=8&model=ViT-B/32&stage2=true&use_audio=false&w_video=1.0&w_audio=0.0` (fast ANN label matching with optional audio fusion)
    - `GET /ui` (simple web UI)
  - Optional auth: set `KNOT_API_KEY` to require `X-API-Key` on write endpoints. All endpoints have basic in-memory rate limiting.

  - Optional Redis + cache:
    - Set `REDIS_URL` (e.g. `redis://localhost:6379/0`) to enable Redis client.
    - Rate limiting backend: `KNOT_RATE_BACKEND=redis` (defaults to in-memory).
    - Caching: `KNOT_CACHE_ENABLED=1` (default), `KNOT_CACHE_TTL=60`, `KNOT_CACHE_PREFIX=knot:cache`.
    - Admin cache flush: `POST /cache/flush` (requires `X-API-Key` when `KNOT_API_KEY` is set). Query/body `prefix` is supported.
    - Demo KV API: `PUT|GET|DELETE /redis/kv/{key}` for simple key/value checks (requires Redis).
  - Optional MongoDB (write-through persistence):
    - Set `MONGO_URI` (e.g., `mongodb+srv://user:pass@host/db?retryWrites=true&w=majority`) and optionally `MONGO_DB` (default `knot`).
    - Users and posts created via API write through to Mongo (`users`, `posts` collections) in addition to JSON and optional SQLite.
    - Health: `GET /health/mongo`.
  - Uploads + preview:
    - Upload media via `POST /upload` (multipart field `file`). Response includes `filename`, server `path`, size, and `mime`.
    - Optional serving: set `KNOT_SERVE_UPLOADS=1` to enable `GET /uploads/{filename}` for browser preview.
    - The web UI at `/ui` supports uploads and shows inline preview (video/audio/image) and a link fallback.
    - The UI includes “Test API” and “Test CORS” buttons to validate connectivity/CORS quickly.
    - The UI also provides a “Redis KV” panel to set/get/delete keys via the demo endpoints.

  - Fast label ANN (optional):
    - Precompute label embeddings once: `python tools/embed_labels.py --master Mesh/mastercategories.txt --out indexes`
    - Then call: `GET /classify/ann?video_path=/abs/path.mp4&k=10` to get top labels using CLIP + ANN.
    - If `faiss` is installed, uses ANN; otherwise falls back to a fast vector dot product.
    - Stage 2 re-rank recomputes scores over per-frame embeddings for the top-K for higher accuracy.
    - Optional audio fusion with CLAP when available: set `use_audio=true&w_audio>0`.
    - CLI equivalents:
      - `python cli_demo.py embed-labels --master Mesh/mastercategories.txt --out indexes`
      - `python cli_demo.py classify-ann --video /abs/path.mp4 --k 10 --frames 8 --model ViT-B/32 --agg mean`
    - UI controls: Classify panel includes Use Audio and weight inputs; results render in a table.

  - CLAP bootstrap (optional):
    - Download checkpoint: `python tools/bootstrap_clap.py --url https://.../clap_ckpt.pt --out models/clap_ckpt.pt`
    - Set env: `CLAP_CKPT_PATH=models/clap_ckpt.pt` (or `CLAP_CKPT_URL=https://...`)

Notes
- ANN acceleration uses FAISS if available (optional dependency). Install `faiss-cpu` for your platform to enable.

- Tests
  - `pytest -q`

## Category System

Posts carry a structured Category object (multi-level, multi-valued):

- Default bucketing (compatibility across code/tests):
  - macro: top-level labels (list[str], up to 3)
  - meso: mid-level labels (list[str], up to 8)
  - micro: fine-grained labels (list[str], up to 15)

Veil demo path: The demo classification path constrains buckets tighter (macro=2, meso=4, micro=6) when writing Category, which improves focus and speeds follow‑on ranking. The generic helpers still produce 3/8/15 unless you opt into the limited helper.

Example:

```
{
  "postID": "p1",
  "Category": {"macro": ["animals","wildlife","nature"], "meso": ["pets","mammals"], "micro": ["cats","kittens", "tabby"]}
}
```

- Backward compatible: legacy `Categories: ["cats", ...]` auto-converts (first→macro, second→meso).
- Search indexes description plus category tokens (macro, meso, micro). Analytics aggregate on macro.

## Labels: mastercategories.txt

- Canonical file: `Mesh/mastercategories.txt`.
- Format per line (Veil-compatible prompts):
  - `a video about <category> | a photo of <category>`
- Builder: `Mesh/tools/build_mastercategories.py`
  - Deterministic (seed=42) curate/dedup from multiple domains.
  - `--count N` builds up to N unique categories (≤ available unique after dedup).
  - Programmatic API for GUI: `build_and_write(out_path=None, target_count=N)`.

## Components

- Veil: loads labels from the master file; classifies media and returns label scores. See `Veil/src/veil`.
- Mesh: JSON-backed Users/Posts (see `Mesh/tools/*`, `Mesh/category.py`, `Mesh/analytics.py`).
- Drift: ranks candidates; mapping via `Mesh/drift_adapter.py`.
- Scribe: builds an index from post descriptions + category tokens; backends: BoW TF-IDF (default) or Sentence-Transformers.

## Category Tree (Macros → Mesos → Micros)

The hierarchical builder `Mesh/tools/build_mastercategories_tree.py` uses a fixed macro list:

Gaming, Music, Sports, Movies & TV, Anime & Comics, Technology & Gadgets, Science & Education, Art & Design, Fashion & Beauty, Food & Cooking, Travel & Places, Cars & Vehicles, Health & Fitness, Lifestyle & Routines, History & Culture, Politics & News, Finance & Business, Nature & Animals, DIY & How-To, Comedy & Memes, Motivation & Self-Help, Mystery & Horror, Podcasts & Talk, Relationships & Community, Spirituality & Philosophy.

- For each macro it pulls several mesos (subcategories) from the web (Wikipedia) when online; otherwise a compact offline fallback is used.
- For each meso it collects several micros (leaf topics), deduplicates simple adjective variants, and avoids repeating macro/meso terms.
- Writes micros as prompts in `Mesh/mastercategories.txt` (Veil prompt format) and writes the full tree to `Mesh/master_tree.json`.

## Feed Ranking (Drift)

The feed is scored and ordered by `Drift/drift_ranker.py`.

- Signals and default weights (see `WEIGHTS`):
  - likes: 1.0, comments: 1.75, shares: 3.0, gift_count: 4.0, pay-per-view: 0.25, star: 15.0
  - suggested flag: +4.0, promotion penalty: −15.0, flagged penalty: −1000.0, non-video penalty: −20.0
  - category affinity: +30.0 if user prefers that category
  - creator overexposure: −12.0 per repeat in `user.recent_creators`
  - engagement_weight: +18.0 × sqrt(engagement with creator)
  - recency: exponential decay with half-life = 2 days, blended with weight = 0.5
- Run/variety constraints (`_apply_limits`):
  - per-creator overall cap: 2
  - max 3 of the same category in a row
  - max 2 from the same creator in a row
- Tuning:
  - Edit `Drift/drift_ranker.py:WEIGHTS` to change signal strengths and recency behavior.
  - Adjust run-limit parameters in `_apply_limits` if you call it directly; API uses defaults.
- API:
  - `GET /rank?user=<id-or-username>&k=20` returns a list of `{ id, creator, category, score }`.

## Quality-of-Life

- GUI adds a “Rebuild Categories” action and a Labels count input.
- Posts generator auto-creates one user if none exist.
- Make/PS shortcuts:
  - `make install|test|demo|gui|labels|cli`
  - `scripts/tasks.ps1 -Task Install|Test|Demo|GUI|Labels|CLI`

## GitHub Pages (Static UI)

- This repo includes a simple static UI that can be hosted via GitHub Pages.
- We publish `docs/index.html` for Pages; the same UI is also served by the API at `/ui`.
- The UI has a modern, dark red theme with improved typography, cards, and buttons for a cleaner UX.
- Responsive layout: panels flow into two columns on wide screens.
- Compact mode: toggle in the Auth section to reduce spacing (saved in localStorage).
- Dark mode: default dark red palette with a Dark Mode toggle (switch to light theme); saved in localStorage.
- Copy curl: one-click "Copy curl" buttons next to key actions to reproduce API calls from the terminal.
- Toast notifications: success/error toasts appear for key actions alongside the log.
- Reset UI: quick button to clear UI preferences (compact, API base/key inputs).
- Classify (ANN) panel: includes aggregation, audio fusion toggle, and weights.
- Category Browser: loads `Mesh/master_tree.json` via `/categories/tree` and displays macros → mesos → micros.
  - Web UI includes a "Load Categories" button to fetch/render the tree. If the tree file is missing, the API builds it on-demand.
- The UI is static and expects an API base URL:
  - Use the “API Base URL” field at the top of the page, e.g. `http://localhost:8000` or your deployed API host.
  - If left blank, it calls the same origin (works when served by the API at `/ui`).
- Optional: set `KNOT_SERVE_UPLOADS=1` on your API to preview uploaded files within the UI.

## GUI (Tkinter)

- Appearance: Dark/Light palettes with light red accents; applies across frames, buttons, inputs.
- Create User / Create Post + Analyze: same core actions as the web UI.
- Classify (ANN): K, Frames, Model dropdown, Aggregation (mean/max/softmax), optional audio fusion with video/audio weights; results logged.
- Category Browser: loads `Mesh/master_tree.json` and displays macros -> mesos -> micros in a tree view.
- Generators: Users/Posts helpers; auto-creates one user if none exist for post generation.

## Environment Variables

- `KNOT_API_KEY`: if set, API requires `X-API-Key` on protected routes (e.g., `POST /users`, `POST /posts`, `POST /upload`, `POST /cache/flush`).
- `REDIS_URL`: enable Redis client; example `redis://localhost:6379/0` or `redis://:password@host:6379/0`.
- `KNOT_RATE_BACKEND`: `memory` (default) or `redis` to use Redis-backed fixed-window rate limiting.
- `KNOT_CACHE_ENABLED`: `1` (default) to enable cache helper (search results); `0` to disable.
- `KNOT_CACHE_TTL`: TTL seconds for cached entries (default `60`).
- `KNOT_CACHE_PREFIX`: Redis/memory cache key prefix (default `knot:cache`).
- `KNOT_SERVE_UPLOADS`: `1` to enable `GET /uploads/{filename}`; disabled by default.
- `KNOT_CORS_ORIGINS`: comma-separated list of allowed origins for CORS (e.g., `https://<user>.github.io, http://localhost:5173`). If set, enables CORS for cross-origin requests (required when using the UI from GitHub Pages to call your API).
- `MONGO_URI`: if set, enables MongoDB client; API writes users/posts to Mongo.
- `MONGO_DB`: Mongo database name (default `knot`).

Tip: an example `.env` is included at the repo root. Start the API with:

`uvicorn --env-file .env api.main:app --reload`

## Notes

- No special “t1” user is required. Create users via GUI, demo, or API as needed.
- Old “video” naming is preserved as aliases (e.g., `make_video` → `make_post`).

## License

MIT — see `LICENSE`.

