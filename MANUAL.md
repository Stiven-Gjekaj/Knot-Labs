# Knot-Labs Developer Manual 🛠

This manual captures everything you need to build, extend, and debug the Knot-Labs sandbox. Pair it with the user-facing [README](README.md) for a friendly tour.

## 🧩 Project Components

- **Veil** — multimodal zero-shot classifier powered by CLIP, Whisper, and YAMNet.
- **Mesh** — JSON-backed user/post store with analytics helpers and tooling.
- **Drift** — explainable feed ranking over candidate posts.
- **Scribe** — lightweight search (bag-of-words + semantic transformer backends).
- **API** — FastAPI service bundling the full stack (UVicorn runner in `api.main`).

## ⚙️ Environment Setup

- Target Python 3.10+ (tests verified on 3.13).
- Single dependency file: `requirements.txt`.
- Create a virtualenv manually: `python -m venv .venv`.
- Install deps: `.venv\Scripts\python.exe -m pip install -r requirements.txt`.
- Convenience scripts (pick one):
  - `powershell -ExecutionPolicy Bypass -File scripts\setup.ps1`
  - `bash scripts/setup.sh`
  - `make setup`

## 🗃️ Data & Label Pipelines

### Master Categories

- Flat builder: `.venv\Scripts\python.exe -m Mesh.tools.build_mastercategories --count 1000`.
- Tree builder (Wikipedia macros ➕ mesos ➕ micros):
  - `.venv\Scripts\python.exe -m Mesh.tools.build_mastercategories --use-tree --count 200`
  - Fixed counts: `.venv\Scripts\python.exe -m Mesh.tools.build_mastercategories --use-tree --mesos 3 --micros 3`
- Outputs: `Mesh/mastercategories.txt` (flat) and `Mesh/master_tree.json` (tree).
- Tree builder maps friendly macro names to Wikipedia topics (custom User-Agent, offline fallbacks).

### Label Embeddings (ANN)

- Recommended pipeline: `python -m tools.embed_labels --master Mesh/mastercategories.txt --out indexes`.
- Direct script variant: `python tools/embed_labels.py --master Mesh/mastercategories.txt --out indexes`.
- Generates `indexes/labels_clip_<mode>_<model>.npz`.
- Options: `--mode video|image`, `--model ViT-B/32|RN50|...`.
- Reused by both the API and CLI for ANN classification; auto-build on first use if missing.

## 🧪 Running The Stack

- **CLI demo:** `python demo.py` (interactive walk-through of the components).
- **GUI (Tkinter):** `python gui_demo.py`
  - Ships with Python; install `python3-tk` on Linux if missing.
  - GUI buttons auto-seed users when needed.
- **Media classifier:** `python -m veil.run --mode video --video /abs/path.mp4 --master_labels_file Mesh/mastercategories.txt`
  - Fusion pipeline uses CLIP + Whisper + YAMNet (ANN off by default).
  - Enable ANN: `--use_ann true --ann_k 64 --ann_agg mean` after embeddings exist.

## 🌐 API Service

- Start scripts:
  - Windows CMD: `scripts\start-api.bat`
  - PowerShell: `powershell -ExecutionPolicy Bypass -File scripts\start-api.ps1`
  - Bash/WSL: `bash scripts/start-api.sh`
- Explicit command: `.venv\Scripts\python.exe -m uvicorn --env-file .env api.main:app --reload`
- Selected endpoints:
  - `POST /users` — body accepts optional `username`, `gender`, `country`.
  - `POST /posts` — runs Veil when `media_path` is supplied and now accepts optional `description`, `media_path`, and `country`.
  - `POST /interactions/{like|comment|share|gift}`
  - `GET /rank?user=<id-or-username>&k=20`
  - `GET /search?q=...&k=10&backend=bow|st`
  - `GET /analytics/categories`
  - `GET /metrics` (Prometheus)
  - `GET /health/redis`, `GET /health/mongo`
  - `POST /cache/flush`
  - `POST /upload`, `GET /uploads/{filename}`
  - `GET /classify/ann?...` (fast ANN clip matching)
  - `GET /ui`
- Optional auth: set `KNOT_API_KEY`; require `X-API-Key` on write routes (the bundled web UI no longer prompts for it).
- Redis integration:
  - `REDIS_URL=redis://localhost:6379/0`
  - Rate limiting: `KNOT_RATE_BACKEND=redis`
  - Caching knobs: `KNOT_CACHE_ENABLED=1`, `KNOT_CACHE_TTL=60`, `KNOT_CACHE_PREFIX=knot:cache`

## 🔧 Developer Tips

- Install with editable mode when building packages: `pip install -e .`.
- Run commands from repo root to avoid package import errors.
- Use FAISS for ANN acceleration:
  - CPU: `pip install faiss-cpu` (or Conda `faiss-cpu`).
  - GPU (via Conda): `conda install -c pytorch -c nvidia faiss-gpu`.
- Verify FAISS: `python -c "import faiss, numpy as np; xb=np.random.rand(100,512).astype('float32'); index=faiss.IndexFlatIP(512); index.add(xb); print(index.ntotal)"`.

## 🧐 Troubleshooting Cheatsheet

- **Import errors**: run inside venv or reinstall with `pip install -e .`.
- **torchvision resize TypeError**: ensure Pillow is installed; latest code converts frames to PIL.
- **No video frames sampled**: validate OpenCV/FFmpeg (`ffmpeg -i <video>`); try `--frames 16`.
- **PowerShell script blocked**: use `-ExecutionPolicy Bypass` or set `RemoteSigned`.
- **Wikipedia category fetch fails**: check proxy, set `HTTP_PROXY/HTTPS_PROXY`, rerun with smaller `--count`.
- **Missing Tk on Linux**: install platform package (e.g., `sudo apt-get install python3-tk`).
- **TensorFlow oneDNN warning**: set `TF_ENABLE_ONEDNN_OPTS=0` to silence.
- **timm deprecation logs**: import via `timm.layers` or upgrade.
- **Proxy/SSL issues**:
  - Export `HTTP_PROXY`/`HTTPS_PROXY`.
  - Configure pip: `pip config set global.proxy http://user:pass@proxy:8080`.
  - Provide corporate CA via `PIP_CERT`, `REQUESTS_CA_BUNDLE`, or `pip config set global.cert`.
  - Git SSL: `git config --global http.sslCAInfo <path>` or `http.sslBackend schannel` on Windows.
- **CUDA not detected**:
  - Check: `.venv\Scripts\python.exe -c "import torch;print(torch.cuda.is_available());import tensorflow as tf;print(tf.config.list_physical_devices('GPU'))"`.
  - Align PyTorch/TensorFlow wheels with installed driver/CUDA version.
  - Force CPU: set `CUDA_VISIBLE_DEVICES=`.
- **FFmpeg missing**: install via package manager (Chocolatey, Homebrew, apt, dnf) and ensure `ffmpeg -version` works.

## 🤝 Contributing

- Follow Python code style with descriptive docstrings where helpful.
- Add tests when extending components (CLI demos double as smoke tests).
- File issues for large refactors or API changes before landing PRs.

Happy building! 🔧
