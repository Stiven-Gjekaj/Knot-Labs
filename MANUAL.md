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

### Category Buckets (macro/meso/micro/nano)

- Category objects consist of four lists: `macro`, `meso`, `micro`, and `nano`.
- Defaults when deriving from a list of labels (Mesh/category.py: make_category_from_micro):
  - macro: first 2 unique labels
  - meso: next 4
  - micro: next 8
  - nano: all remaining
- To cap sizes explicitly, use `make_category_with_limits(macro_n=2, meso_n=4, micro_n=8, nano_n=12)`.
  - Set `nano_n=None` to keep all remaining as nano.
  - The app applies 2/4/8/12 (26 total) when updating a post’s Category from Veil predictions.

### Label Embeddings (ANN)

- Recommended pipeline: `python -m tools.embed_labels --master Mesh/mastercategories.txt --out indexes`.
- Direct script variant: `python tools/embed_labels.py --master Mesh/mastercategories.txt --out indexes`.
- Generates `indexes/labels_clip_<mode>_<model>.npz`.
- Options: `--mode video|image`, `--model ViT-B/32|RN50|...`.
- Reused by both the API and CLI for ANN classification; auto-build on first use if missing.

#### Runtime Caching Behavior

- Cache files live under `indexes/` as `labels_clip_<mode>_<model>.npz`.
- Veil loads and uses these embeddings directly for both video and image modes.
- If the NPZ is missing, Veil will normally build it on first use. You can
  control this with environment variables:
  - `VEIL_CACHED_ONLY=true` (or `KNOT_LABELS_CACHED_ONLY=true`): do not build when missing; return an empty index and skip ANN/cached labels.
  - `VEIL_CROSSMODE_FALLBACK=true` (default): if the requested mode’s NPZ is missing, reuse the other mode’s NPZ when dimensions align.
  - `VEIL_FAST_BOOT=true`: skip multi-template label embedding builds and rely on a single-template path for faster cold starts.

Examples:

- Precompute both caches for best speed and quality:
  - Video: `python -m tools.embed_labels --master Mesh/mastercategories.txt --out indexes --model ViT-B/32 --mode video`
  - Image: `python -m tools.embed_labels --master Mesh/mastercategories.txt --out indexes --model ViT-B/32 --mode image`
- Force cached-only for latency-sensitive environments: set `VEIL_CACHED_ONLY=true` in the process environment.

Related timeout knob (demo/API):

- `KNOT_VEIL_TIMEOUT_SEC`: max seconds the demo/API waits for `veil.run` before returning `{"error":"timeout"}`.

### Veil Runtime & Timeouts (API)

- The API enqueues a `classify_post` job which runs `python -m veil.run`.
- Cold starts can exceed default timeouts due to model downloads and label embedding builds.
- If a job ends with `{ "status": "error", "error": "{\"error\": \"timeout\"}" }`:
  - Pre-warm caches:
    - Video: `python -m tools.embed_labels --master Mesh/mastercategories.txt --out indexes --model ViT-B/32 --mode video`
    - Image: `python -m tools.embed_labels --master Mesh/mastercategories.txt --out indexes --model ViT-B/32 --mode image`
  - Increase timeout before starting Uvicorn: `KNOT_VEIL_TIMEOUT_SEC=600`
  - Optional safeguards to avoid heavy builds on the API host:
    - `VEIL_CACHED_ONLY=true` to skip building NPZ files if missing.
    - `VEIL_FAST_BOOT=true` to skip multi-template label embedding builds.
    - `VEIL_CROSSMODE_FALLBACK=true` (default) to reuse the other mode’s NPZ when lengths match.

### Veil Configuration (Env)

- Defaults (demo/API launchers):
  - Frames: `KNOT_VEIL_FRAMES=4`
  - Whisper on: `KNOT_VEIL_USE_WHISPER=true`
  - Weights: video `0.5`, speech `0.3`, audio `0.2` (passed via CLI flags)
  - Top‑K: `26` (macro/meso/micro/nano = 2/4/8/12)
- Additional knobs:
  - `KNOT_SPEECH_MAX_SEC` (e.g., `45`) caps Whisper transcription time.
  - `KNOT_AUDIO_MAX_SEC` (e.g., `20`) caps YAMNet audio duration.
  - `KNOT_VEIL_TIMEOUT_SEC` bounds the subprocess wall time.
- CLI overrides take precedence (`--frames`, `--use_whisper`, `--w_*`, `--topk`).

## 🧪 Running The Stack





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
- Add tests when extending components.
- File issues for large refactors or API changes before landing PRs.

Happy building! 🔧
