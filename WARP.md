# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Core Commands

### Environment Setup
```bash
# Windows PowerShell (recommended)
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

# Or using Make
make setup

# Manual setup
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Starting the API Server
```bash
# Windows (recommended - uses venv automatically)
scripts\start-api.bat

# PowerShell
powershell -ExecutionPolicy Bypass -File scripts\start-api.ps1

# Direct command (from repo root)
.venv\Scripts\python.exe -m uvicorn --env-file .env api.main:app --reload

# Using Make
make run
```

### Running Tests
```bash
# Run all tests
.venv\Scripts\python.exe -m pytest -q

# Run specific test file
.venv\Scripts\python.exe -m pytest tests/test_api_auth_rate.py -v

# Run tests with coverage
.venv\Scripts\python.exe -m pytest --cov=api --cov=Mesh --cov=Veil --cov=Drift --cov=Scribe
```

### Linting and Formatting
```bash
# Format with Black
.venv\Scripts\python.exe -m black . --line-length 100

# Lint with Ruff
.venv\Scripts\python.exe -m ruff check .

# Type checking with MyPy
.venv\Scripts\python.exe -m mypy api Mesh Veil Drift Scribe
```

### Building Category Labels
```bash
# Build flat categories (1000 unique)
.venv\Scripts\python.exe -m Mesh.tools.build_mastercategories --count 1000

# Build tree from Wikipedia (200 total micros)
.venv\Scripts\python.exe -m Mesh.tools.build_mastercategories --use-tree --count 200

# Build with fixed counts per level
.venv\Scripts\python.exe -m Mesh.tools.build_mastercategories --use-tree --mesos 3 --micros 3
```

### Label Embeddings for Fast ANN
```bash
# Precompute embeddings (recommended before first use)
python -m tools.embed_labels --master Mesh/mastercategories.txt --out indexes

# With specific model
python -m tools.embed_labels --master Mesh/mastercategories.txt --out indexes --model ViT-B/32 --mode video
```

### Running Demos
```bash
# CLI demo
.venv\Scripts\python.exe demo.py

# GUI demo (Tkinter)
.venv\Scripts\python.exe gui_demo.py

# CLI with specific actions
.venv\Scripts\python.exe cli_demo.py classify-ann --video /path/to/video.mp4 --k 10
```

## Architecture Overview

### Component Structure

The codebase implements a modular social media stack with four main components:

1. **Veil** (`Veil/src/veil/`) - Zero-shot media classifier
   - `video_clip.py`, `image_clip.py` - CLIP-based visual classification
   - `audio_whisper.py` - Speech-to-text processing
   - `fusion/yamnet_events.py` - Audio event detection
   - `fusion/label_loader.py` - Label management and prompt engineering
   - `run.py` - Main fusion pipeline orchestrating all modalities

2. **Mesh** (`Mesh/`) - Data layer and storage
   - `schemas.py` - Pydantic models for Users, Posts, Categories
   - `sqlite_store.py` - Local SQLite persistence
   - `mongo_store.py` - MongoDB integration (optional)
   - `category.py` - Category system (macro/meso/micro hierarchy)
   - `analytics.py` - Category-based analytics
   - `tools/` - Data generation and management utilities

3. **Drift** (`Drift/`) - Feed ranking algorithm
   - `drift_ranker.py` - Core ranking logic with signal weights
   - `models.py` - Ranking request/response models
   - `app.py` - Standalone ranking service
   - Uses signals: likes, comments, shares, gifts, recency, category affinity

4. **Scribe** (`Scribe/`) - Search functionality
   - `search.py` - Dual backend: BoW TF-IDF or Sentence-Transformers
   - Indexes post descriptions + category tokens

### API Layer (`api/`)

FastAPI server orchestrating all components:
- `main.py` - Core endpoints and middleware
- `jobs.py` - Background job queue (classification tasks)
- `label_index.py` - Label embedding management for ANN search

Key endpoints:
- User/Post CRUD: `POST /users`, `POST /posts`
- Ranking: `GET /rank?user=<id>&k=20`
- Search: `GET /search?q=...&backend=bow|st`
- Classification: `GET /classify/ann?video_path=...`
- Analytics: `GET /analytics/categories`

### Data Flow

1. **Media Upload** → `POST /upload` → saved to `Mesh/Uploads/`
2. **Post Creation** → `POST /posts` → triggers Veil classification if media_path provided
3. **Classification** → Veil fusion (CLIP + Whisper + YAMNet) → Category object (macro/meso/micro)
4. **Storage** → JSON files + optional SQLite/MongoDB persistence
5. **Ranking** → Drift scores candidates using engagement signals + category affinity
6. **Search** → Scribe indexes descriptions + categories for retrieval

### Category System

Hierarchical label structure stored in `Mesh/mastercategories.txt`:
- **Macro**: Top-level categories (e.g., "Gaming", "Music", "Sports")
- **Meso**: Mid-level subcategories 
- **Micro**: Fine-grained specific topics

Tree builder fetches from Wikipedia with fallback to offline seeds.
Posts carry structured Category objects for multi-level classification.

## Environment Configuration

Key environment variables (set in `.env`):
- `KNOT_API_KEY` - API authentication (if set, requires X-API-Key header)
- `REDIS_URL` - Redis connection for caching/rate limiting
- `MONGO_URI` - MongoDB connection for persistence
- `KNOT_SERVE_UPLOADS` - Enable file serving at /uploads/{filename}
- `KNOT_CORS_ORIGINS` - CORS allowed origins (comma-separated)
- `KNOT_CACHE_ENABLED` - Enable result caching (default: 1)
- `KNOT_CACHE_TTL` - Cache TTL in seconds (default: 60)

## Development Workflow

### Quick Development Cycle
1. Activate venv: `.venv\Scripts\activate` (auto-activates with PowerShell profile)
2. Start API with hot reload: `scripts\start-api.bat`
3. Test changes: Access http://localhost:8000/ui or use API directly
4. Run specific tests: `pytest tests/test_<module>.py::test_<function> -v`

### Adding New Features
1. Implement in appropriate module (Veil/Mesh/Drift/Scribe)
2. Add API endpoint in `api/main.py` if needed
3. Write tests in `tests/`
4. Update category labels if adding new classification domains

### Performance Optimization
- FAISS integration for ANN search (install `faiss-cpu` for acceleration)
- Precompute label embeddings before deployment
- Redis caching for search/rank results
- Background job queue for heavy classification tasks

## Common Issues and Solutions

### Module Import Errors
- Always run from repo root
- Use module form: `python -m <module>` instead of direct script execution
- Ensure editable install: `pip install -e .`

### Classification Performance
- Precompute embeddings: `python -m tools.embed_labels --master Mesh/mastercategories.txt --out indexes`
- Install FAISS for faster ANN: `pip install faiss-cpu` (Linux/macOS)
- Reduce frame sampling for faster processing: `--frames 8`

### API Rate Limiting
- Default in-memory backend, switch to Redis for production
- Configure via `KNOT_RATE_BACKEND=redis` with `REDIS_URL`

## Testing Strategy

### Unit Tests
- Core logic: `test_drift_ranker.py`, `test_scribe_search.py`
- Data layer: `test_sqlite_store.py`, `test_export_import.py`
- Classification: `test_veil_*` files
- API: `test_api_auth_rate.py`, `test_admin_and_uploads.py`

### Integration Points
- Veil + Mesh: Classification results stored as Category objects
- Mesh + Drift: User preferences and post metadata for ranking
- Mesh + Scribe: Post content indexing for search

### Manual Testing
- GUI: `python gui_demo.py` for interactive testing
- Web UI: http://localhost:8000/ui for API interaction
- CLI: `python cli_demo.py` for command-line testing

## Key Implementation Details

### Veil Fusion Pipeline
1. Sample frames from video (configurable count)
2. Extract CLIP embeddings per frame
3. Match against label embeddings (ANN or direct)
4. Optional audio fusion with Whisper (speech) + YAMNet (events)
5. Weighted combination: video (0.5) + speech (0.3) + audio events (0.2)
6. Return structured categories (macro/meso/micro limits)

### Drift Ranking Algorithm
- Base scores from engagement signals (likes, comments, shares, gifts)
- Category affinity bonus for user preferences
- Creator overexposure penalty for diversity
- Recency decay with configurable half-life
- Run limits to ensure variety (max same category/creator in sequence)

### Scribe Search Backends
- **BoW (default)**: Fast TF-IDF scoring over tokenized text
- **Sentence-Transformers**: Dense embeddings for semantic search
- Both index description + category tokens for hybrid retrieval