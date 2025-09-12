# Developer Manual

Technical documentation for Knot-Labs developers and contributors.

## Table of Contents

- [Architecture](#architecture)
- [Development Setup](#development-setup)
- [Component Details](#component-details)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Architecture

### System Overview

Knot-Labs consists of four core components:

```
┌─────────────────────────────────────────────┐
│                   API Layer                  │
│              (FastAPI + Uvicorn)             │
├─────────────────────────────────────────────┤
│     Veil          │        Drift            │
│ (Classification)  │   (Feed Ranking)        │
├─────────────────────────────────────────────┤
│     Mesh          │        Scribe           │
│  (Data Store)     │      (Search)           │
├─────────────────────────────────────────────┤
│            Storage Layer                     │
│    (JSON / MongoDB / SQLite / Redis)        │
└─────────────────────────────────────────────┘
```

### Component Structure

#### Veil - Media Classification

- **Location**: `Veil/src/veil/`
- **Purpose**: Multi-modal media understanding
- **Key Files**:
  - `run.py` - Main fusion runner
  - `video_clip.py` - Video classification
  - `image_clip.py` - Image classification
  - `audio_whisper.py` - Speech transcription
  - `fusion/yamnet_events.py` - Audio event detection

#### Mesh - Data Management

- **Location**: `Mesh/`
- **Purpose**: User and post storage with analytics
- **Key Files**:
  - `category.py` - Category system implementation
  - `analytics.py` - Usage analytics
  - `drift_adapter.py` - Drift integration
  - `mongo_store.py` - MongoDB persistence
  - `sqlite_store.py` - SQLite backend
  - `tools/` - Data generation utilities

#### Drift - Feed Ranking

- **Location**: `Drift/`
- **Purpose**: Personalized content ranking
- **Key Files**:
  - `drift_ranker.py` - Core ranking algorithm
  - `models.py` - Data models
  - `app.py` - Standalone Drift app

#### Scribe - Search System

- **Location**: `Scribe/`
- **Purpose**: Full-text search with multiple backends
- **Key Files**:
  - `search.py` - Search implementation
  - `cli.py` - Command-line interface

## Development Setup

### Prerequisites

- Python 3.10+ (tested on 3.13)
- Git
- 4GB+ RAM
- Optional: CUDA-capable GPU for acceleration
- Optional: FFmpeg for video processing

### Environment Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/Knot-Labs.git
   cd Knot-Labs
   ```

2. **Create virtual environment**

   ```bash
   python -m venv .venv
   ```

3. **Activate environment**

   Windows (PowerShell):

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   Windows (CMD):

   ```cmd
   .venv\Scripts\activate.bat
   ```

   Unix/MacOS:

   ```bash
   source .venv/bin/activate
   ```

4. **Install dependencies**

   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

5. **Optional: Install FAISS for ANN acceleration**

   ```bash
   # CPU version (recommended)
   pip install faiss-cpu

   # GPU version (Linux only)
   pip install faiss-gpu
   ```

### Development Tools

#### PowerShell Scripts

- `scripts/setup.ps1` - Complete setup automation
- `scripts/start-api.ps1` - Start API server
- `scripts/tasks.ps1` - Common development tasks
- `scripts/add-venv-auto-activate.ps1` - Auto-activate venv on directory entry

#### Make Targets

```bash
make help      # Show available targets
make setup     # Create venv and install deps
make run       # Start API server
make test      # Run tests
make clean     # Remove venv
make check     # Verify FAISS and FFmpeg
```

## Component Details

### Category System

Categories use a three-tier hierarchy:

```python
{
  "Category": {
    "macro": ["animals", "nature"],      # 2 max
    "meso": ["pets", "mammals"],         # 4 max
    "micro": ["cats", "kittens", "tabby"] # 8 max
  }
}
```

#### Building Categories

```bash
# Build from Wikipedia (online)
python -m Mesh.tools.build_mastercategories --use-tree --count 200

# Build with fixed counts
python -m Mesh.tools.build_mastercategories --use-tree --mesos 3 --micros 3

# Build flat list (offline)
python -m Mesh.tools.build_mastercategories --count 1000
```

Output files:

- `Mesh/mastercategories.txt` - Veil-compatible prompts
- `Mesh/master_tree.json` - Hierarchical structure

### Veil Classification Pipeline

1. **Video Processing**

   - Frame extraction (configurable count)
   - CLIP embedding generation
   - Frame aggregation (mean/max/softmax)

2. **Audio Processing**

   - Speech transcription (Whisper)
   - Audio event detection (YAMNet)
   - Text embedding of transcripts

3. **Fusion**
   - Weighted combination of modalities
   - Default weights: video=0.5, speech=0.3, audio=0.2
   - Returns top-K categories

#### CLI Usage

```bash
# Basic classification
python -m veil.run --mode video --video /path/to/video.mp4

# With ANN acceleration
python -m veil.run --mode video --video /path/to/video.mp4 \
  --use_ann true --ann_k 64 --ann_agg mean

# Custom weights
python -m veil.run --mode video --video /path/to/video.mp4 \
  --w_video 0.6 --w_speech 0.2 --w_audio 0.2
```

### Drift Ranking Algorithm

#### Scoring Weights (configurable in `drift_ranker.py`)

```python
WEIGHTS = {
    "likes": 1.0,
    "comments": 1.75,
    "shares": 3.0,
    "gift_count": 4.0,
    "pay_per_view_count": 0.25,
    "star": 15.0,
    "suggested": 4.0,
    "promotion_penalty": -15.0,
    "flag_penalty": -1000.0,
    "non_video_penalty": -20.0,
    "category_affinity": 30.0,
    "creator_overexposure": -12.0,
    "engagement_weight": 18.0,
    "recency_half_life_days": 2.0,
    "recency_weight": 0.5,
}
```

#### Variety Constraints

- Per-creator cap: 2 posts maximum
- Category runs: max 3 same category in sequence
- Creator runs: max 2 same creator in sequence

### Adding New Ranking Signals

1. Add field to `VideoCandidate` in `Drift/models.py`:

   ```python
   class VideoCandidate(BaseModel):
       # existing fields...
       new_signal: float = 0.0
   ```

2. Update generator in `Mesh/tools/gen_videos.py`:

   ```python
   post["new_signal"] = random.random() * 100
   ```

3. Add weight to `WEIGHTS` in `Drift/drift_ranker.py`:

   ```python
   WEIGHTS = {
       # existing weights...
       "new_signal": 2.5,
   }
   ```

4. Implement in `compute_score()`:
   ```python
   score += video.new_signal * WEIGHTS["new_signal"]
   ```

## API Reference

### Core Endpoints

#### Users

- `POST /users` - Create user
- `GET /users/{id}` - Get user details

#### Posts

- `POST /posts` - Create post (auto-classifies if media provided)
- `GET /posts` - List posts
- `GET /posts/{id}` - Get post details

#### Interactions

- `POST /interactions/like` - Like a post
- `POST /interactions/comment` - Add comment
- `POST /interactions/share` - Share post
- `POST /interactions/gift` - Send gift

#### Feed & Discovery

- `GET /rank` - Get personalized feed
  - Query params: `user`, `k` (count)
- `GET /search` - Search posts
  - Query params: `q` (query), `k`, `backend` (bow|st)
- `GET /analytics/categories` - Category statistics

#### Classification

- `GET /classify/ann` - Fast ANN classification
  - Query params: `video_path`, `k`, `frames`, `model`, `use_audio`
- `POST /upload` - Upload media for classification

#### Health & Admin

- `GET /health/redis` - Redis connectivity
- `GET /health/mongo` - MongoDB connectivity
- `GET /metrics` - Prometheus metrics
- `POST /cache/flush` - Clear caches (requires auth)

### Authentication

Set `KNOT_API_KEY` environment variable to enable authentication:

```bash
export KNOT_API_KEY="your-secret-key"
```

Protected endpoints require `X-API-Key` header:

```bash
curl -X POST http://localhost:8000/users \
  -H "X-API-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"username": "alice"}'
```

### Rate Limiting

Default: 60 requests per minute per client

Configure backend:

```bash
# In-memory (default)
export KNOT_RATE_BACKEND=memory

# Redis-backed
export KNOT_RATE_BACKEND=redis
export REDIS_URL=redis://localhost:6379/0
```

## Testing

### Running Tests

```bash
# All tests
pytest

# Specific module
pytest tests/test_drift_ranker.py -v

# With coverage
pytest --cov=. --cov-report=html

# Parallel execution
pytest -n auto
```

### Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_api_auth_rate.py    # API security
├── test_drift_ranker.py     # Feed ranking
├── test_veil_*.py          # Classification tests
├── test_scribe_search.py    # Search functionality
└── test_build_mastercategories*.py  # Category generation
```

### Writing Tests

Example test structure:

```python
import pytest
from Drift.drift_ranker import compute_score
from Drift.models import User, VideoCandidate

def test_score_calculation():
    user = User(
        id="u1",
        username="alice",
        preferred_categories=["tech"]
    )
    video = VideoCandidate(
        id="v1",
        creator_id="c1",
        category="tech",
        likes=100
    )
    score = compute_score(user, video)
    assert score > 0
```

## Deployment

### Environment Variables

Create `.env` file:

```env
# Core
KNOT_API_KEY=your-secret-key

# Redis (optional)
REDIS_URL=redis://localhost:6379/0
KNOT_CACHE_ENABLED=1
KNOT_CACHE_TTL=300
KNOT_CACHE_PREFIX=knot:cache
KNOT_RATE_BACKEND=redis

# MongoDB (optional)
MONGO_URI=mongodb://localhost:27017/
MONGO_DB=knot

# CORS (for cross-origin access)
KNOT_CORS_ORIGINS=https://yourdomain.com,http://localhost:3000

# Uploads
KNOT_SERVE_UPLOADS=1
```

### Production Deployment

#### Using Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Using systemd (Linux)

```ini
[Unit]
Description=Knot-Labs API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/knot-labs
Environment="PATH=/opt/knot-labs/.venv/bin"
ExecStart=/opt/knot-labs/.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

#### Performance Tuning

1. **Enable Redis caching**

   ```bash
   export REDIS_URL=redis://localhost:6379/0
   export KNOT_CACHE_ENABLED=1
   ```

2. **Use production server**

   ```bash
   uvicorn api.main:app --workers 4 --host 0.0.0.0 --port 8000
   ```

3. **Precompute label embeddings**

   ```bash
   python -m tools.embed_labels --master Mesh/mastercategories.txt --out indexes
   ```

4. **Install FAISS**
   ```bash
   pip install faiss-cpu
   ```

## Troubleshooting

### Common Issues

#### ModuleNotFoundError

**Problem**: `ModuleNotFoundError: No module named 'api'`

**Solution**: Run from repository root using module syntax:

```bash
python -m tools.embed_labels  # Correct
# NOT: python tools/embed_labels.py
```

#### Uvicorn Wrong Binary

**Problem**: `uvicorn: error: unrecognized arguments: --env-file`

**Solution**: Use venv's uvicorn:

```bash
.venv\Scripts\python.exe -m uvicorn --env-file .env api.main:app
```

#### No Frames from Video

**Problem**: `RuntimeError: No frames sampled from video`

**Solution**:

1. Verify FFmpeg is installed: `ffmpeg -version`
2. Check video path is correct
3. Try more frames: `--frames 16`

#### PowerShell Execution Policy

**Problem**: Scripts blocked by execution policy

**Solution**:

```powershell
# One-time
powershell -ExecutionPolicy Bypass -File scripts\start-api.ps1

# Or set permanently
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

#### Wikipedia Categories Not Loading

**Problem**: Tree builder can't fetch from Wikipedia

**Solution**:

1. Check internet connection
2. Set proxy if needed: `export HTTP_PROXY=http://proxy:8080`
3. Falls back to offline seeds automatically

#### FAISS Installation

**Windows**:

```bash
# Use Conda (recommended)
conda install -c pytorch faiss-cpu

# Or WSL
wsl
pip install faiss-cpu
```

**Linux/Mac**:

```bash
pip install faiss-cpu
```

#### Missing Tkinter (Linux)

```bash
# Debian/Ubuntu
sudo apt-get install python3-tk

# Fedora
sudo dnf install python3-tkinter
```

### Performance Issues

#### Slow Classification

1. **Enable FAISS**: `pip install faiss-cpu`
2. **Precompute embeddings**: `python -m tools.embed_labels`
3. **Reduce frames**: `--frames 4` instead of default 8
4. **Use GPU**: Install CUDA and `faiss-gpu`

#### High Memory Usage

1. **Limit batch size** in classification
2. **Enable Redis** for caching
3. **Reduce `--ann_k` parameter**
4. **Use smaller models**: `--model RN50` instead of `ViT-B/32`

#### Slow API Responses

1. **Enable caching**: `KNOT_CACHE_ENABLED=1`
2. **Use Redis**: `REDIS_URL=redis://localhost:6379`
3. **Add workers**: `uvicorn --workers 4`
4. **Profile endpoints**: `python -m cProfile -o profile.stats`

### Debugging

#### Enable Debug Logging

```python
# In api/main.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

#### Test Individual Components

```bash
# Test Veil
python -c "from Veil.src.veil.run import main; print('Veil OK')"

# Test Mesh
python -c "from Mesh.tools.gen_user import make_user; print(make_user())"

# Test Drift
python -c "from Drift.drift_ranker import WEIGHTS; print(WEIGHTS)"

# Test Scribe
python -c "from Scribe.search import build_index; print('Scribe OK')"
```

## Contributing

### Development Workflow

1. **Fork the repository**
2. **Create feature branch**: `git checkout -b feature/amazing-feature`
3. **Make changes**
4. **Run tests**: `pytest`
5. **Format code**: `black . && ruff check --fix`
6. **Commit**: `git commit -m "Add amazing feature"`
7. **Push**: `git push origin feature/amazing-feature`
8. **Open Pull Request**

### Code Style

- **Formatter**: Black (line length 100)
- **Linter**: Ruff
- **Type hints**: Use where possible
- **Docstrings**: Google style

Configuration in `pyproject.toml`:

```toml
[tool.black]
line-length = 100
target-version = ["py310"]

[tool.ruff]
line-length = 100
select = ["E","F","I","UP","B"]
target-version = "py310"
```

### Testing Guidelines

- Write tests for new features
- Maintain >80% coverage
- Use fixtures for shared setup
- Mock external dependencies
- Test edge cases

### Documentation

- Update MANUAL.md for technical changes
- Update README.md for user-facing features
- Update WARP.md for architectural changes
- Add docstrings to new functions/classes
- Include examples in docstrings

### Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Run full test suite
4. Tag release: `git tag v0.2.0`
5. Push tags: `git push --tags`

## Advanced Topics

### Custom Storage Backend

Implement the storage interface:

```python
class CustomStore:
    def save_user(self, user_data: dict) -> str:
        # Implementation
        pass

    def load_user(self, user_id: str) -> dict:
        # Implementation
        pass

    def save_post(self, post_data: dict) -> str:
        # Implementation
        pass

    def load_posts(self) -> list:
        # Implementation
        pass
```

### Custom Search Backend

```python
from Scribe.search import SearchBackend

class CustomSearch(SearchBackend):
    def build_index(self, posts: list) -> None:
        # Implementation
        pass

    def search(self, query: str, k: int = 10) -> list:
        # Implementation
        pass
```

### Plugin System

Create plugins in `plugins/` directory:

```python
# plugins/my_plugin.py
from fastapi import APIRouter

router = APIRouter(prefix="/my-plugin")

@router.get("/hello")
def hello():
    return {"message": "Hello from plugin"}

# In api/main.py
from plugins.my_plugin import router
app.include_router(router)
```

## Resources

- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **CLIP Paper**: https://arxiv.org/abs/2103.00020
- **Whisper**: https://github.com/openai/whisper
- **YAMNet**: https://github.com/tensorflow/models/tree/master/research/audioset
- **FAISS**: https://github.com/facebookresearch/faiss

## Support

- **Issues**: GitHub Issues for bug reports
- **Discussions**: GitHub Discussions for questions
- **Email**: support@knot-labs.example.com
- **Documentation**: This manual, README.md, and WARP.md
