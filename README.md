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
  - CLI: `python Mesh/tools/build_mastercategories.py --count 1000`
  - GUI: `python gui_demo.py` → Generators → set “Labels N” → “Rebuild Categories”

- Generate data
  - Users: `python Mesh/tools/gen_user.py 3 --users-dir Mesh/Users`
  - Posts: `python Mesh/tools/gen_videos.py 10 --posts-dir Mesh/Posts`
    - GUI has “Generate Users/Posts” buttons. If no users exist, Generate Posts will auto-create one.

- Run demo (CLI)
  - `python demo.py`

- Run GUI (Tkinter)
  - `python gui_demo.py`
  - Ships with Python on most platforms. If missing: install your OS tk package (e.g., `sudo apt-get install python3-tk`).

- Start API (FastAPI)
  - `uvicorn api.main:app --reload`
  - Endpoints:
    - `POST /users`
    - `POST /posts` (optionally classifies with Veil when `media_path` provided)
    - `POST /interactions/{like|comment|share|gift}`
    - `GET /rank?user=<id-or-username>&k=20`
    - `GET /search?q=...&k=10&backend=bow|st`
    - `GET /analytics/categories`
  - Optional auth: set `KNOT_API_KEY` to require `X-API-Key` on write endpoints. All endpoints have basic in-memory rate limiting.

- Tests
  - `pytest -q`

## Category System

Posts carry a structured Category object (multi-level, multi-valued):

- macro: top-level labels (list[str], up to 3)
- meso: mid-level labels (list[str], up to 8)
- micro: fine-grained labels (list[str], up to 15)

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

## Quality-of-Life

- GUI adds a “Rebuild Categories” action and a Labels count input.
- Posts generator auto-creates one user if none exist.
- Make/PS shortcuts:
  - `make install|test|demo|gui|labels|cli`
  - `scripts/tasks.ps1 -Task Install|Test|Demo|GUI|Labels|CLI`

## Notes

- No special “t1” user is required. Create users via GUI, demo, or API as needed.
- Old “video” naming is preserved as aliases (e.g., `make_video` → `make_post`).

## License

MIT — see `LICENSE`.
