# Knot-Labs

Knot-Labs is a unified, multi-component lab for prototyping a social media stack. It integrates four systems that work together:

- Veil: zero-shot media classification for uploads
- Mesh: lightweight local engagement database and utilities
- Drift: simple feed ranking over candidates
- Scribe: simple text search over posts

The only requirements file is the root `requirements.txt`.

## Quick Start

- Install (Python 3.10+):
  - `pip install -r requirements.txt`

- Build master categories (writes `Mesh/mastercategories.txt`):
  - `python Mesh/tools/build_mastercategories.py`

- Generate some data:
  - Users: `python Mesh/tools/gen_videos.py 3 --users-dir Mesh/Users`
  - Posts: `python Mesh/tools/gen_videos.py 10 --posts-dir Mesh/Posts`

- Run demo (CLI):
  - `python demo.py`

- Optional GUI (Tkinter):
  - `python gui_demo.py`
  - Tkinter ships with Python on most platforms. If missing, install your OS package for Tk (e.g., `sudo apt-get install python3-tk`).
  - GUI now includes generators for users/posts plus selectors for gender and country.

- Scribe search (CLI):
  - `python -m Scribe.cli --posts-dir Mesh/Posts --backend bow "cats funny"`
  - Use backend `st` to switch to Sentence-Transformers if installed.

- Start API (FastAPI):
  - `uvicorn api.main:app --reload`
  - Endpoints:
    - `POST /users`
    - `POST /posts` (optionally enqueues Veil classification when `media_path` provided)
    - `POST /interactions/{like|comment|share|gift}`
    - `GET /rank?user=<id-or-username>&k=20`
    - `GET /search?q=...&k=10&backend=bow|st`
    - `GET /analytics/categories`
  - Optional auth: set `KNOT_API_KEY` env var to require `X-API-Key` header for write endpoints. Basic in-memory rate limiting is enabled for all endpoints.

- Run tests:
  - `pytest -q`
  - Includes Veil unit tests that avoid large downloads and exercise label loading, prompt parsing, fusion, and helper logic.

CI notes
- The workflow runs unit tests on Ubuntu.
- Update the badge URL above by replacing `OWNER` with your GitHub username or org if needed.

## Components

- Veil: Zero-shot audio+video classifier. Encodes video frames and/or audio transcripts, performs label scoring, and annotates posts on upload.
- Mesh: JSON-backed store (Users, Posts) with engagement tracking and utilities. Hosts the canonical `mastercategories.txt` and tools to rebuild it.
- Drift: Ranking over candidate posts using simple, explainable signals.
- Scribe: Text search over posts with TF‑IDF (default) or Sentence‑Transformers.

## Recent Updates
- GUI migrated to Tkinter; added generators and gender/country selectors.
- Added lightweight SQLite write-through store for users/posts (`Mesh/sqlite_store.py`).
- FastAPI now supports `X-API-Key` auth (when `KNOT_API_KEY` is set) and has simple rate limiting.
- Drift ranking weights tuned and are configurable in `Drift/drift_ranker.py` via `WEIGHTS`.

## Data: Master Categories

- Canonical file: `Mesh/mastercategories.txt`
- Rebuild with: `python Mesh/tools/build_mastercategories.py`

## Data Model

- Category field on posts: each post now stores a `Category` object, not a flat list.
  - Shape:
    - `macro`: top-level category name (string)
    - `meso`: mid-level category (string)
    - `micro`: fine-grained labels (array of strings)
  - Example:
    ```json
    {
      "postID": "p1",
      "Category": {
        "macro": "animals",
        "meso": "pets",
        "micro": ["cats", "kittens"]
      }
    }
    ```
- Backward compatibility: if older posts contain `Categories: ["cats", ...]`, the code converts them on the fly using the first item as `macro` and second as `meso`.
- Search indexes description plus category tokens (macro, meso, micro). Analytics aggregate on the macro level.

## Notes

- “Posts” are the primary content unit. Older “video” function/flag names are kept as wrappers for compatibility (e.g., `make_video` -> `make_post`).
- Per-project READMEs and requirements are consolidated into this root README and the root requirements file.

## Scripts & Tasks

- Makefile targets: `install`, `test`, `demo`, `gui`, `labels`, `cli`
- PowerShell: `scripts/tasks.ps1 -Task Install|Test|Demo|GUI|Labels|CLI`

## License

This repository is released under the [MIT License](LICENSE).
