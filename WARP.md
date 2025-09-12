# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Core Development Commands

### Setup and Installation
```bash
# PowerShell (Windows)
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

# Or using Make
make setup

# Manual setup
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Running the API Server
```bash
# PowerShell
powershell -ExecutionPolicy Bypass -File scripts\start-api.ps1

# Windows CMD
scripts\start-api.bat

# Or directly with uvicorn
.venv\Scripts\python.exe -m uvicorn --env-file .env api.main:app --reload
```

### Building Category Labels
```bash
# Build hierarchical categories from Wikipedia (recommended)
.venv\Scripts\python.exe -m Mesh.tools.build_mastercategories --use-tree --count 200

# Build with fixed counts per level
.venv\Scripts\python.exe -m Mesh.tools.build_mastercategories --use-tree --mesos 3 --micros 3

# Precompute label embeddings for fast ANN classification
python -m tools.embed_labels --master Mesh/mastercategories.txt --out indexes
```

### Running Tests
```bash
# Run all tests
pytest -q

# Run specific test module
pytest tests/test_drift_ranker.py -v

# Run with coverage
pytest --cov=. --cov-report=html
```

### GUI and Demo Commands
```bash
# Run GUI demo (Tkinter)
python gui_demo.py

# Run CLI demo
python demo.py

# Run classification CLI
python cli_demo.py classify-ann --video /path/to/video.mp4 --k 10
```

## Architecture Overview

### Component Structure

**Knot-Labs** is a modular social media backend prototype with four main components:

1. **Veil** (`Veil/src/veil/`) - Media Classification System
   - Multi-modal classifier using CLIP (video/image), Whisper (speech), and YAMNet (audio)
   - Entry point: `veil.run` module for unified fusion
   - Key classes: `classify_video_clip()`, `classify_image_clip()`
   - Supports ANN (Approximate Nearest Neighbor) search via FAISS when available

2. **Mesh** (`Mesh/`) - Data Storage Layer
   - JSON-backed storage for users and posts with optional MongoDB/SQLite persistence
   - Category system with hierarchical structure (macro → meso → micro)
   - Analytics and category management via `Mesh/analytics.py` and `Mesh/category.py`
   - Tools for data generation in `Mesh/tools/`

3. **Drift** (`Drift/`) - Feed Ranking Engine
   - Sophisticated ranking algorithm with configurable weights in `drift_ranker.py`
   - Considers engagement signals, recency, user preferences, and content diversity
   - Enforces variety constraints (creator limits, category runs)
   - Integration via `Mesh/drift_adapter.py`

4. **Scribe** (`Scribe/`) - Search System
   - Full-text search over posts using TF-IDF or Sentence-Transformers
   - Indexes post descriptions and category tokens
   - Backend-agnostic search interface

### API Architecture (`api/main.py`)

The FastAPI application provides RESTful endpoints with:
- Optional authentication via `KNOT_API_KEY`
- Rate limiting (memory or Redis-backed)
- Caching layer with configurable TTL
- Prometheus metrics (`/metrics`)
- CORS support for cross-origin requests
- Static UI serving at `/ui`

Key endpoints:
- User/Post CRUD operations
- `/rank` - Feed ranking with Drift
- `/search` - Text search with Scribe
- `/classify/ann` - Fast media classification with Veil
- `/analytics/categories` - Category statistics
- `/cache/flush` - Admin cache management

### Data Flow

1. **Content Creation**: Users/posts created via API or GUI → stored in JSON (Mesh/) → optionally persisted to MongoDB
2. **Classification**: Media files → Veil multi-modal analysis → structured Category object (macro/meso/micro levels)
3. **Ranking**: User profile + candidate posts → Drift scoring → variety-constrained feed
4. **Search**: Query → Scribe indexing → ranked results with optional caching

### Category System

Categories follow a three-tier hierarchy:
- **Macro**: Top-level categories (2 max per post)
- **Meso**: Mid-level subcategories (4 max per post)
- **Micro**: Fine-grained topics (8 max per post)

The master category file (`Mesh/mastercategories.txt`) contains Veil-compatible prompts that can be built from Wikipedia or offline seeds.

### Storage Backends

- **Primary**: JSON files in `Mesh/Users/` and `Mesh/Posts/`
- **Optional MongoDB**: Write-through persistence via `MONGO_URI`
- **Optional SQLite**: Via `Mesh/sqlite_store.py`
- **Redis**: For caching and rate limiting via `REDIS_URL`

## Environment Configuration

Key environment variables (see `.env` file):
- `KNOT_API_KEY` - API authentication key
- `REDIS_URL` - Redis connection string
- `MONGO_URI` - MongoDB connection string
- `KNOT_CACHE_ENABLED` - Enable/disable caching (default: 1)
- `KNOT_CACHE_TTL` - Cache TTL in seconds (default: 60)
- `KNOT_SERVE_UPLOADS` - Enable file serving (default: 0)
- `KNOT_CORS_ORIGINS` - Comma-separated CORS origins

## Development Patterns

### Adding New Ranking Signals

To add new ranking factors to Drift:
1. Add field to `VideoCandidate` in `Drift/models.py`
2. Update `Mesh/tools/gen_videos.py` to generate the field
3. Add weight to `WEIGHTS` dict in `Drift/drift_ranker.py`
4. Implement scoring logic in `compute_score()`

### Extending Classification

To modify Veil classification:
1. Label generation: Edit `Mesh/tools/build_mastercategories.py`
2. Fusion weights: Adjust in `veil.run` arguments (`--w_video`, `--w_speech`, `--w_audio`)
3. ANN index: Rebuild with `tools/embed_labels.py` after label changes

### API Extension Pattern

New endpoints should follow the established pattern:
1. Add route handler in `api/main.py`
2. Use `_check_auth()` for protected endpoints
3. Use `_check_rate()` for rate limiting
4. Add metrics via `REQ_COUNT` and `REQ_LAT`
5. Support caching where appropriate

## Testing Strategy

- Unit tests in `tests/` cover all major components
- Test files follow `test_*.py` naming convention
- Key test areas:
  - `test_drift_ranker.py` - Feed ranking logic
  - `test_veil_*` - Classification components
  - `test_api_auth_rate.py` - API security
  - `test_build_mastercategories*.py` - Category generation

## Common Development Tasks

### Rebuilding After Category Changes
```bash
# Rebuild categories
.venv\Scripts\python.exe -m Mesh.tools.build_mastercategories --use-tree --count 200

# Recompute embeddings
python -m tools.embed_labels --master Mesh/mastercategories.txt --out indexes

# Restart API to load new categories
```

### Debugging Classification
```bash
# Test classification with detailed output
python -m veil.run --mode video --video /path/to/video.mp4 --master_labels_file Mesh/mastercategories.txt --topk 20

# With ANN enabled
python -m veil.run --mode video --video /path/to/video.mp4 --use_ann true --ann_k 64
```

### Database Operations
```bash
# Export/import data
python -m Mesh.tools.export_import export --output backup.json
python -m Mesh.tools.export_import import --input backup.json

# Validate categories
python -m Mesh.tools.validate_categories
```

## Performance Considerations

- **FAISS**: Install `faiss-cpu` for 10-100x faster ANN search
- **Label Embeddings**: Always precompute with `tools/embed_labels.py` to avoid startup delays
- **Caching**: Enable Redis caching for search/ranking results in production
- **Video Processing**: Adjust `--frames` parameter based on video length and available memory

## Troubleshooting

### Module Import Errors
- Always run Python commands from repository root
- Use module form: `python -m module.name` instead of direct script execution
- Ensure virtual environment is activated

### Classification Issues
- Verify `Mesh/mastercategories.txt` exists and is non-empty
- Check CUDA availability for GPU acceleration: `.venv\Scripts\python.exe -c "import torch;print(torch.cuda.is_available())"`
- For video issues, ensure FFmpeg is installed and on PATH

### API Issues
- Check uvicorn is using the venv version: `.venv\Scripts\python.exe -m uvicorn`
- Verify `.env` file exists with required variables
- For CORS issues, set `KNOT_CORS_ORIGINS` appropriately

### Performance Bottlenecks
- Enable Redis for production workloads
- Use FAISS for large-scale classification
- Consider MongoDB for persistence at scale
- Profile with `python -m cProfile` for specific bottlenecks