# Knot-Labs 🌐

## ✨ Highlights

- 🧠 **Veil** — zero-shot media classifier for audio + video with prompt-style labels.
- 📂 **Mesh** — local JSON store handling users, posts, and lightweight analytics.
- 🔁 **Drift** — transparent feed ranking.
- 🔍 **Scribe** — full-text search across posts.
- 🧰 Everything runs on Python with a single `requirements.txt`.

## 🚀 Quick Start

1. Ensure Python 3.10+ is installed (3.13 recommended).
2. Choose your setup script:
   - 🪟 PowerShell: `powershell -ExecutionPolicy Bypass -File scripts\setup.ps1`
   - 🐧 Bash / WSL: `bash scripts/setup.sh`
   - 🔧 Make: `make setup`
   - 🧪 Manual: `python -m venv .venv && .venv\Scripts\python.exe -m pip install -r requirements.txt && pip install -e .`
3. Launch the CLI demo: `python demo.py`
4. Fire up the GUI: `python gui_demo.py`
5. Start the API (auto-reloads): `.venv\Scripts\python.exe -m uvicorn --env-file .env api.main:app --reload`
6. Open `/ui` to create users and posts — the new dropdowns let you pin gender and country or leave them on auto-select.

## 🎯 Try The Media Classifier

- Build master labels: `.venv\Scripts\python.exe -m Mesh.tools.build_mastercategories --count 1000`
- (Optional) Enable ANN speed-ups: `python -m tools.embed_labels --master Mesh/mastercategories.txt --out indexes`
- Classify a video: `python -m veil.run --mode video --video /abs/path.mp4 --master_labels_file Mesh/mastercategories.txt`

## 📡 API Endpoints (Favorites)

- `POST /users`
- `POST /posts`
- `GET /rank?user=<id-or-username>&k=20`
- `GET /search?q=...&k=10&backend=bow|st`
- `GET /analytics/categories`
- `GET /ui`

Need authentication, caching, or embeddings? Check the [developer manual](MANUAL.md).
