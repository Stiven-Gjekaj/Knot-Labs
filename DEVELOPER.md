# Knot-Labs Developer Documentation

**Welcome to Knot-Labs.** This document is a comprehensive guide written for developers. It covers everything from high-level architecture to nitty-gritty implementation details, common gotchas, and where to find things.

---

## 📑 Table of Contents

### Getting Started

- [What is Knot-Labs?](#what-is-knot-labs)
- [Quick Setup](#quick-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)

### Core Architecture

- [System Overview](#system-overview)
- [Data Flow](#data-flow)
- [Component Communication](#component-communication)

### Components Deep Dive

- [Mesh - Data Storage](#mesh---data-storage)
- [Veil - Media Classification](#veil---media-classification)
- [Drift - Feed Ranking](#drift---feed-ranking)
- [Scribe - Search Engine](#scribe---search-engine)
- [Echo - Face Recognition](#echo---face-recognition)
- [API - Web Service](#api---web-service)

### Key Concepts

- [Category System](#category-system)
- [Job Queue](#job-queue)
- [Index Management](#index-management)
- [Mesh Adapters](#mesh-adapters)

### Development Guide

- [Running Tests](#running-tests)
- [Adding New Features](#adding-new-features)
- [Common Patterns](#common-patterns)
- [Code Examples](#code-examples)

### Troubleshooting

- [Common Issues](#common-issues)
- [Performance Tips](#performance-tips)
- [Debugging Guide](#debugging-guide)

### Reference

- [Environment Variables](#environment-variables)
- [API Endpoints](#api-endpoints)
- [File Locations](#file-locations)

---

## What is Knot-Labs?

Knot-Labs is a **social media sandbox** - a complete, working social media platform built for experimentation and learning. It's modular, meaning each component can work independently or as part of the whole system.

**The Big Picture:**
Think of it like a real social media app (TikTok, Instagram, etc.) but smaller and fully transparent. Users create posts (videos/images), the system classifies content, ranks it for personalized feeds, allows searching, and even has face recognition for profile pictures.

**Tech Stack:**

- Python 3.10+ (3.13 recommended)
- FastAPI for the web service
- JSON files for data storage (with optional SQLite/MongoDB)
- CLIP, Whisper, YAMNet for AI classification
- FAISS for similarity search
- Sentence Transformers for semantic search

---

## Quick Setup

### Prerequisites

- Python 3.10 or higher (3.13 is best)
- FFmpeg installed (for video processing)
- Git

### Installation

```bash
# Clone the repo
git clone <your-repo-url>
cd Knot-Labs

# Create virtual environment
python -m venv .venv

# Activate it (Windows)
.venv\Scripts\activate

# Or on Linux/Mac
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install in editable mode (important for development!)
pip install -e .
```

### First Run

```bash
# Start the API server
python -m uvicorn --env-file .env api.main:app --reload

# Open your browser
# http://localhost:8000/ui
```

That's it! You should see the web UI.

---

## Project Structure

```
Knot-Labs/
├── api/                    # FastAPI web service
│   ├── main.py            # Main API endpoints
│   ├── jobs.py            # Background job queue
│   ├── label_index.py     # CLIP label indexing
│   └── static/            # Web UI (HTML/CSS/JS)
│
├── Mesh/                  # Data storage layer
│   ├── Users/             # User JSON files
│   ├── Posts/             # Post JSON files
│   ├── Echo/              # Face recognition data
│   │   ├── known/         # Reference face images
│   │   └── queries/       # Query images
│   ├── Uploads/           # Uploaded media files
│   ├── category.py        # Category system logic
│   ├── drift_adapter.py   # Converts Mesh data to Drift models
│   ├── analytics.py       # Basic analytics
│   └── tools/             # Data generation/management scripts
│
├── veil/                  # Media classification engine
│   └── src/veil/          # Core classification code
│
├── Drift/                 # Feed ranking algorithm
│   ├── drift_ranker.py    # Ranking logic
│   └── models.py          # Data models
│
├── Scribe/                # Search engine
│   └── search.py          # Bag-of-words & semantic search
│
├── Echo/                  # Face recognition
│   └── scripts/           # CLI tools for face indexing/querying
│
├── indexes/               # All FAISS/embedding indexes
│   ├── labels_clip_*.npz  # Veil label embeddings
│   ├── echo_faiss_*.bin   # Face recognition indexes
│   └── echo_faiss_*.json  # Face metadata
│
├── tests/                 # All test files
├── tools/                 # Utility scripts
└── scripts/               # Setup and start scripts
```

**Important Principle:** Always run Python modules from the repo root using the `-m` flag:

```bash
python -m veil.run           # ✓ Correct
python veil/run.py           # ✗ Will break imports
```

---

## Development Workflow

### Typical Development Day

1. **Pull latest changes**

   ```bash
   git pull origin main
   ```

2. **Activate venv**

   ```bash
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Linux/Mac
   ```

3. **Make your changes**

   - Edit code
   - Write tests

4. **Run tests**

   ```bash
   pytest tests/test_your_feature.py
   ```

5. **Test manually**

   ```bash
   python -m uvicorn api.main:app --reload
   # Visit http://localhost:8000/ui
   ```

6. **Commit and push**
   ```bash
   git add .
   git commit -m "Add feature X"
   git push
   ```

---

## System Overview

### The 10,000 Foot View

Knot-Labs is built around a **content lifecycle**:

1. **User creates content** → Stored in Mesh
2. **Content gets classified** → Veil analyzes it
3. **Categories assigned** → Stored back in Mesh
4. **Users interact** → Likes, comments, shares
5. **Feed gets ranked** → Drift personalizes it
6. **Content is searchable** → Scribe finds it

```
┌─────────┐    ┌──────┐    ┌──────────┐    ┌───────┐
│  User   │───▶│ Mesh │───▶│   Veil   │───▶│ Mesh  │
│ Creates │    │Stores│    │Classifies│    │Updates│
└─────────┘    └──────┘    └──────────┘    └───────┘
                                                 │
                                                 ▼
┌─────────┐    ┌──────┐    ┌──────────┐    ┌───────┐
│  User   │◀───│Drift │◀───│   Mesh   │    │       │
│  Views  │    │Ranks │    │  Loads   │    │       │
└─────────┘    └──────┘    └──────────┘    └───────┘
```

### Components at a Glance

| Component  | What it does      | Input                    | Output          |
| ---------- | ----------------- | ------------------------ | --------------- |
| **Mesh**   | Stores all data   | User actions             | JSON files      |
| **Veil**   | Classifies media  | Video/image file         | Category labels |
| **Drift**  | Ranks content     | User preferences + Posts | Sorted list     |
| **Scribe** | Searches posts    | Text query               | Matching posts  |
| **Echo**   | Recognizes faces  | Photo                    | Similar faces   |
| **API**    | Serves everything | HTTP requests            | JSON responses  |

---

## Data Flow

### Post Creation Flow

This is the most complex flow in the system. Let me break it down step by step:

**1. User uploads media via web UI**

```
POST /upload
  ↓
Upload file to Mesh/Uploads/
  ↓
Return file path
```

**2. User creates post with media**

```
POST /posts
{
  "creator": "user123",
  "description": "Cool video",
  "media_path": "/path/to/uploaded/video.mp4"
}
```

**3. API stores post in Mesh**

```python
# api/main.py
post = make_post(creator_id, categories=[], country=req.country)
post['description'] = req.description
path = save_post(post, POSTS_DIR)  # Saves to Mesh/Posts/{postID}.json
```

**4. API enqueues background classification job**

```python
# api/main.py
job = {
    'id': uuid.uuid4().hex,
    'type': 'classify_post',
    'post_path': path,
    'media_path': req.media_path,
}
job_id = job_queue.submit(job)
```

**5. Background worker processes job**

```python
# api/main.py → _handle_job()
res = _run_veil_and_get_categories(media_path, topk=26)
# Returns list of category labels

# Convert labels to Category object
post['Category'] = make_category_from_micro(cats)
# Category = {macro: [2 labels], meso: [4], micro: [8], nano: [12+]}

# Save updated post
_save_json(post_path, post)
```

**6. User can poll job status**

```
GET /jobs/{job_id}
  ↓
Returns: {"status": "running|done|error", "result": {...}}
```

### Feed Ranking Flow

**1. User requests their feed**

```
GET /rank?user=alice&k=20
```

**2. API loads user from Mesh**

```python
# api/main.py
user_json = load_from_file('Mesh/Users/alice.json')
```

**3. Convert to Drift model**

```python
# Mesh/drift_adapter.py
drift_user = mesh_user_to_drift_user(user_json)
# Extracts: preferred_categories, seen_creators, engagement scores
```

**4. Load all posts**

```python
# Mesh/drift_adapter.py
candidates = mesh_posts_to_drift_candidates('Mesh/Posts/')
# Filters out inactive/deleted/flagged posts
```

**5. Rank posts**

```python
# Drift/drift_ranker.py
ranked = rank_videos(drift_user, candidates)
# Scores each post based on:
# - Category match
# - Creator familiarity
# - Engagement signals
# - Recency
# - Diversity constraints
```

**6. Return top K**

```python
return ranked[:20]  # Top 20 posts
```

---

## Mesh - Data Storage

Mesh is the **heart** of Knot-Labs. Everything lives here.

### Philosophy

Mesh uses **JSON files** because:

- Easy to inspect (just open the file!)
- No database setup required
- Git-friendly (you can version control data)
- Perfect for a sandbox/learning environment

But it also supports SQLite and MongoDB for "real" deployments.

### Directory Structure

```
Mesh/
├── Users/              # One JSON file per user
│   ├── user_001.json
│   ├── user_002.json
│   └── ...
│
├── Posts/              # One JSON file per post
│   ├── post_001.json
│   ├── post_002.json
│   └── ...
│
├── Echo/               # Face recognition data
│   ├── known/          # Reference faces (subfolders = labels)
│   │   ├── alice/
│   │   └── bob/
│   └── queries/        # Query images
│
├── Uploads/            # Uploaded media files
│   └── {uuid}.mp4
│
└── mastercategories.txt  # List of all category labels (generated)
```

### User Schema

**File:** `Mesh/Users/{userID}.json`

```json
{
  "userID": "user_abc123",
  "username": "alice",
  "gender": "female",
  "country": "US",
  "CategoryScores": {
    "Technology": 150,
    "Gaming": 89,
    "Music": 45
  },
  "ViewerScore": {
    "creator_xyz": 12,
    "creator_abc": 5
  },
  "RecentCreators": ["creator_xyz", "creator_abc"],
  "SeenPosts": ["post_001", "post_002"]
}
```

**Field Breakdown:**

- `userID`: Unique identifier (string)
- `username`: Display name (optional, can be null)
- `gender`: "male", "female", "other", or null
- `country`: ISO country code or null
- `CategoryScores`: Map of category → score (higher = more interested)
  - Updated when user interacts with posts
  - Used by Drift for ranking
- `ViewerScore`: Map of creator_id → engagement count
  - Tracks how much user engages with each creator
  - Influences Drift to show more from creators you like
- `RecentCreators`: List of recently seen creator IDs
  - Used to avoid over-exposure (show variety)
- `SeenPosts`: List of post IDs already watched
  - Prevents showing same post twice

### Post Schema

**File:** `Mesh/Posts/{postID}.json`

```json
{
  "postID": "post_xyz789",
  "creator": "user_abc123",
  "description": "My cool video",
  "createdAt": 1696000000.0,
  "likes": 42,
  "comments": 7,
  "shares": 3,
  "views": 150,
  "Category": {
    "macro": ["Technology", "Entertainment"],
    "meso": ["AI", "Gaming", "Music", "Movies"],
    "micro": [
      "Machine Learning",
      "FPS",
      "Rock",
      "Sci-Fi",
      "Python",
      "Streaming",
      "Concerts",
      "Animation"
    ],
    "nano": ["Deep Learning", "Neural Networks", "CS:GO", "..."]
  },
  "isActive": true,
  "isDeleted": false,
  "isFlagged": false,
  "isPromotion": false
}
```

**Field Breakdown:**

- `postID`: Unique identifier
- `creator`: User ID who created the post
- `description`: Text description (optional)
- `createdAt`: Unix timestamp
- Engagement metrics: `likes`, `comments`, `shares`, `views`
- `Category`: **THE BIG ONE** - see [Category System](#category-system)
- Status flags:
  - `isActive`: false = don't show in feeds
  - `isDeleted`: true = soft delete
  - `isFlagged`: true = moderation flag
  - `isPromotion`: true = sponsored content (ranks lower)

### Key Files

**`Mesh/category.py`** - Category manipulation functions

```python
# Create category from list of labels
make_category_from_micro(labels: List[str]) -> Dict
# Returns: {"macro": [...], "meso": [...], "micro": [...], "nano": [...]}

# With custom limits
make_category_with_limits(labels, macro_n=2, meso_n=4, micro_n=8, nano_n=12)

# Get category from post (handles legacy formats)
ensure_category(post: Dict) -> Dict

# Flatten category for search indexing
category_texts(category: Dict) -> List[str]
```

**`Mesh/drift_adapter.py`** - Converts Mesh data to Drift models

This is **critical** for understanding how Mesh and Drift talk to each other.

```python
# Convert Mesh user JSON to Drift User object
mesh_user_to_drift_user(mesh_user: Dict) -> DriftUser

# Load all posts and convert to Drift candidates
mesh_posts_to_drift_candidates(posts_dir: str) -> List[DriftVideo]
```

**Why adapters?** Because Mesh and Drift have different schemas. Mesh is storage-focused, Drift is algorithm-focused. The adapter translates between them.

### Tools

**Generate master categories** (list of all possible labels):

```bash
python -m Mesh.tools.build_mastercategories --count 1000
# Creates Mesh/mastercategories.txt with 1000 categories
```

**Tree-based (Wikipedia hierarchy)**:

```bash
python -m Mesh.tools.build_mastercategories --use-tree --mesos 3 --micros 3
# Creates structured tree: Mesh/master_tree.json
```

---

## Veil - Media Classification

Veil is the **AI brain** that watches videos and figures out what they're about.

### What Veil Does

Input: A video file (or image)
Output: A list of category labels

**Example:**

```
Input: gaming_video.mp4
Output: ["Gaming", "FPS", "Shooter", "Esports", "CS:GO", "Action", "Multiplayer", ...]
```

### How It Works (The Magic)

Veil uses **multimodal fusion** - it analyzes three things:

1. **Visual (CLIP)**: What's in the video frames?
2. **Speech (Whisper)**: What are people saying?
3. **Audio (YAMNet)**: What sounds are present?

Then it **fuses** the results with weighted averaging:

- Video: 50% weight
- Speech: 30% weight
- Audio: 20% weight

```python
# Simplified pseudocode
video_labels = analyze_frames_with_clip(video)      # 50%
speech_labels = transcribe_with_whisper(video)      # 30%
audio_labels = classify_audio_with_yamnet(video)    # 20%

final_labels = weighted_merge(video_labels, speech_labels, audio_labels)
```

### Running Veil

**Basic usage:**

```bash
python -m veil.run \
  --mode video \
  --video /path/to/video.mp4 \
  --master_labels_file Mesh/mastercategories.txt \
  --frames 4
```

**With ANN (faster, requires precomputed embeddings):**

```bash
python -m veil.run \
  --mode video \
  --video /path/to/video.mp4 \
  --master_labels_file Mesh/mastercategories.txt \
  --use_ann true \
  --ann_k 64 \
  --ann_agg mean
```

### Configuration

**Environment Variables:**

```bash
# Number of frames to sample from video
KNOT_VEIL_FRAMES=4

# Enable/disable speech transcription
KNOT_VEIL_USE_WHISPER=true

# Max audio duration for Whisper (seconds)
KNOT_SPEECH_MAX_SEC=45

# Max audio duration for YAMNet (seconds)
KNOT_AUDIO_MAX_SEC=20

# Classification timeout (seconds)
KNOT_VEIL_TIMEOUT_SEC=600

# Fusion weights (must sum to ~1.0)
# Set via CLI: --w_video 0.5 --w_speech 0.3 --w_audio 0.2
```

**Fast Boot Mode:**

```bash
# Skip expensive multi-template embedding builds
VEIL_FAST_BOOT=true

# Only use precomputed embeddings (fail if missing)
VEIL_CACHED_ONLY=true
```

### Label Embeddings (ANN Speed-Up)

Veil can precompute label embeddings for fast similarity search.

**Why?** CLIP is slow when comparing against 1000+ labels. Precomputing embeddings and using FAISS is **much** faster.

**Precompute embeddings:**

```bash
# Video mode
python -m tools.embed_labels \
  --master Mesh/mastercategories.txt \
  --out indexes \
  --mode video \
  --model ViT-B/32

# Image mode
python -m tools.embed_labels \
  --master Mesh/mastercategories.txt \
  --out indexes \
  --mode image \
  --model ViT-B/32
```

**Result:** Creates `indexes/labels_clip_{mode}_{model}.npz`

**Then use ANN:**

```bash
python -m veil.run --use_ann true --ann_k 64 ...
```

### Cold Start Problem

**Problem:** First run is SLOW because:

1. Models download from Hugging Face (~GB of data)
2. Label embeddings build on-the-fly
3. Everything gets cached

**Solution:**

1. Precompute embeddings (see above)
2. Increase timeout: `KNOT_VEIL_TIMEOUT_SEC=600`
3. Use fast boot: `VEIL_FAST_BOOT=true`

---

## Drift - Feed Ranking

Drift is the **algorithm** that decides what posts you see and in what order.

### Philosophy

Drift is **transparent and explainable**. Unlike black-box recommendation systems, you can see exactly why each post gets its score.

### How Ranking Works

**Core Idea:** Each post gets a score based on multiple signals, then posts are sorted by score.

**Scoring Formula (simplified):**

```
score =
  + (likes * 1.0)
  + (comments * 1.75)
  + (shares * 3.0)
  + (gifts * 4.0)
  + (category_match ? 30.0 : 0)
  + (creator_engagement * 18.0)
  + (recency_boost)
  - (creator_overexposure * 12.0)
  - (flagged ? 1000.0 : 0)
```

**Weights** are configurable in `Drift/drift_ranker.py`:

```python
WEIGHTS = {
    "likes": 1.0,
    "comments": 1.75,
    "shares": 3.0,
    "gift_count": 4.0,
    "ppv": 0.25,
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

### Diversity Constraints

Drift doesn't just sort by score - it enforces **diversity rules** to prevent monotony:

1. **Per-creator limit**: Max 2 posts per creator in feed
2. **Category run limit**: Max 3 consecutive posts from same category
3. **Creator run limit**: Max 2 consecutive posts from same creator

**Example:**

```
If top scores are:
1. creator_A, Gaming (100 pts)
2. creator_A, Gaming (95 pts)
3. creator_A, Gaming (90 pts)
4. creator_B, Music (85 pts)

Actual feed:
1. creator_A, Gaming (100 pts)
2. creator_A, Gaming (95 pts)  ← 2nd from creator_A, OK
3. creator_B, Music (85 pts)   ← Skip creator_A (hit limit), take creator_B
```

This is handled by `_apply_limits()` in `Drift/drift_ranker.py`.

### Code Walkthrough

**`Drift/models.py`** - Data structures

```python
class User(BaseModel):
    id: str
    preferred_categories: List[str]      # Top categories user likes
    seen_creators: List[str]             # All creators seen
    recent_creators: List[str]           # Recently seen (for variety)
    watched_videos: List[str]            # Posts already watched
    creator_engagement: Dict[str, int]   # creator_id → engagement count

class VideoCandidate(BaseModel):
    id: str
    creator_id: str
    category: str  # Single category for simplicity (uses macro[0])
    likes: int
    comments: int
    shares: int
    # ... more fields
```

**`Drift/drift_ranker.py`** - Main logic

```python
def rank_videos(user: User, videos: List[VideoCandidate]) -> List[RankedVideo]:
    # 1. Score all videos
    scored = [(v, compute_score(user, v)) for v in videos]

    # 2. Sort by score (descending)
    scored.sort(key=lambda x: x[1], reverse=True)

    # 3. Apply diversity constraints
    return _apply_limits(scored)

def compute_score(user: User, video: VideoCandidate) -> float:
    score = 0.0

    # Engagement signals
    score += video.likes * WEIGHTS["likes"]
    score += video.comments * WEIGHTS["comments"]
    # ... etc

    # Category affinity
    if video.category in user.preferred_categories:
        score += WEIGHTS["category_affinity"]

    # Creator familiarity
    if video.creator_id in user.seen_creators:
        # New creators get a bonus
        score += random.random() * 2.5
    else:
        score += random.random() * 5.0

    # Overexposure penalty
    repeat_count = user.recent_creators.count(video.creator_id)
    score += repeat_count * WEIGHTS["creator_overexposure"]

    # Already watched? Score = 0
    if video.id in user.watched_videos:
        score = 0

    # Creator engagement boost
    eng = user.creator_engagement.get(video.creator_id, 0)
    if eng > 0:
        score += math.sqrt(eng) * WEIGHTS["engagement_weight"]

    # Recency boost (newer = better)
    age_days = (time.time() - video.created_at) / 86400.0
    decay = 0.5 ** (age_days / WEIGHTS["recency_half_life_days"])
    score = score * (1 - WEIGHTS["recency_weight"]) + score * decay * WEIGHTS["recency_weight"]

    return score
```

### Usage

**Via API:**

```bash
curl http://localhost:8000/rank?user=alice&k=20
```

**Programmatically:**

```python
from Mesh.drift_adapter import mesh_user_to_drift_user, mesh_posts_to_drift_candidates
from Drift.drift_ranker import rank_videos

# Load user
user_json = load_json('Mesh/Users/alice.json')
drift_user = mesh_user_to_drift_user(user_json)

# Load posts
candidates = mesh_posts_to_drift_candidates('Mesh/Posts/')

# Rank
ranked = rank_videos(drift_user, candidates)

# Top 20
top_20 = ranked[:20]
```

### Tuning the Algorithm

Want to change how ranking works? Edit `WEIGHTS` in `Drift/drift_ranker.py`.

**Examples:**

- Make likes matter more: `"likes": 2.0`
- Reduce overexposure penalty: `"creator_overexposure": -6.0`
- Boost new creators: Increase random bonus in `compute_score()`
- Change recency decay: `"recency_half_life_days": 1.0` (faster decay)

---

## Scribe - Search Engine

Scribe lets users search posts by text.

### Two Backends

**1. Bag-of-Words (BoW)**

- Fast, lightweight
- TF-IDF scoring
- Good for exact keyword matches

**2. Sentence Transformers (ST)**

- Semantic search
- Understands meaning, not just keywords
- Slower, but more accurate

### How It Works

**Indexing:**

```python
from Scribe.search import build_index

# Build index from posts
index = build_index('Mesh/Posts/', backend='bow')  # or 'st'
```

**Searching:**

```python
# Search
results = index.search('funny cat videos', k=10)
# Returns: [(post_id, score), ...]
```

### Behind the Scenes

**`Scribe/search.py`**

```python
class BowEmbedder:
    def fit_transform(self, texts: List[str]):
        # 1. Tokenize all texts
        # 2. Build vocabulary
        # 3. Compute TF-IDF weights
        # 4. Return normalized vectors

    def transform_one(self, text: str):
        # Convert query to vector using same vocab

class SentenceTransformerEmbedder:
    def __init__(self, model_name="sentence-transformers/all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    def fit_transform(self, texts: List[str]):
        return self.model.encode(texts, normalize_embeddings=True)

class Index:
    def __init__(self, embedder, ids, texts, vecs):
        self.embedder = embedder
        self.ids = ids
        self.vecs = vecs

    def search(self, query: str, k: int = 10):
        # 1. Embed query
        q_vec = self.embedder.transform_one(query)

        # 2. Compute cosine similarity with all docs
        scores = [dot_product(q_vec, v) for v in self.vecs]

        # 3. Sort and return top K
        ranked = sorted(zip(self.ids, scores), key=lambda x: x[1], reverse=True)
        return ranked[:k]
```

### Index Text Sources

Posts are indexed from multiple fields:

- `description`
- `Category` (flattened using `category_texts()`)

```python
def _extract_text(post: Dict) -> str:
    parts = []

    # Description
    desc = post.get('description')
    if desc:
        parts.append(str(desc))

    # Categories
    cat = ensure_category(post)
    cat_words = category_texts(cat)
    parts.extend(cat_words)

    return ' '.join(parts)
```

### Usage

**Via API:**

```bash
curl "http://localhost:8000/search?q=gaming&k=10&backend=bow"
```

**Backend selection:**

- `backend=bow` - Fast, keyword-based
- `backend=st` - Slow, semantic

**Caching:** Search results are cached in Redis (if enabled) to speed up repeated queries.

---

## Echo - Face Recognition

Echo finds faces in photos and matches them against a database.

### What Echo Does

1. **Index building**: Scans `Mesh/Echo/known/` for reference faces
2. **Face detection**: Uses `face_recognition` library (dlib under the hood)
3. **Embedding**: Converts faces to 128-d vectors
4. **FAISS indexing**: Stores vectors for fast search
5. **Querying**: Finds similar faces from a query photo

### Directory Structure

```
Mesh/Echo/
├── known/              # Reference faces (organized by person)
│   ├── alice/
│   │   ├── photo1.jpg
│   │   └── photo2.jpg
│   └── bob/
│       └── photo1.jpg
└── queries/            # Query photos (any structure)

indexes/
├── echo_faiss_index.bin   # FAISS index
└── echo_faiss_meta.json   # Metadata (labels, paths, metric)
```

### Building the Index

```bash
python -m Echo.scripts.build_index \
  --known Mesh/Echo/known \
  --model hog \
  --metric l2
```

**Options:**

- `--model hog` (CPU) or `cnn` (GPU)
- `--metric l2` or `cosine`
- `--out-index indexes/echo_faiss_index.bin`
- `--out-meta indexes/echo_faiss_meta.json`

**What happens:**

1. Recursively finds images in `Mesh/Echo/known/`
2. Detects faces in each image
3. Computes 128-d embeddings
4. Builds FAISS index (flat search, no quantization)
5. Saves metadata JSON

**Metadata format:**

```json
{
  "created_utc": 1696000000.0,
  "metric": "l2",
  "dim": 128,
  "count": 42,
  "items": [
    {
      "label": "alice",
      "path": "alice/photo1.jpg"
    },
    ...
  ]
}
```

### Querying

```bash
python -m Echo.scripts.query \
  /path/to/query.jpg \
  --k 5 \
  --threshold 0.6
```

**Output** (Rich table):

```
┌─────────┬──────┬───────────┬───────┬─────────────────┐
│ Query # │ Rank │ Score     │ Label │ Path            │
├─────────┼──────┼───────────┼───────┼─────────────────┤
│ 1       │ #1   │ ✅ 0.4521 │ alice │ alice/photo1.jpg│
│ 1       │ #2   │ ✅ 0.5234 │ alice │ alice/photo2.jpg│
│ 1       │ #3   │ — 0.7123  │ bob   │ bob/photo1.jpg  │
└─────────┴──────┴───────────┴───────┴─────────────────┘
```

### Live Webcam Search

```bash
python -m Echo.scripts.live_search --cam 0 --k 3
```

Opens webcam, detects faces in real-time, shows matches. Press 'q' to quit.

### Web UI Integration

Echo is integrated into `/ui`:

1. User uploads photo
2. Photo saved to `Mesh/Uploads/`
3. API calls Echo query endpoint
4. Results displayed in table

**API Endpoints:**

- `GET /echo/search?image_path=...&k=5&threshold=0.6`
- `POST /echo/build` (rebuilds index)

### Fake Embeddings (Testing)

Echo supports **fake embeddings** for testing without dlib/face_recognition:

```bash
FAKE_EMB=1 python -m Echo.scripts.build_index --known Mesh/Echo/known
FAKE_EMB=1 pytest tests/test_echo_*.py
```

Fake embeddings are deterministic (same file = same vector), allowing tests without ML dependencies.

---

## API - Web Service

The API is the **glue** that connects everything.

### FastAPI Structure

**`api/main.py`** - Main file (~887 lines)

Key sections:

1. **Imports and setup** (lines 1-50)
2. **Helper functions** (lines 51-200)
3. **Middleware** (timing, CORS)
4. **Auth and rate limiting** (lines 140-236)
5. **Caching** (lines 238-277)
6. **Data models** (lines 279-297)
7. **Startup/shutdown** (lines 299-328)
8. **Job handler** (lines 330-373)
9. **Endpoints** (lines 375-887)

### Endpoints Reference

**User Management:**

- `POST /users` - Create user
- `GET /users/{identifier}` - Get user by ID or username

**Posts:**

- `POST /posts` - Create post (auto-enqueues classification)
- `GET /posts/{postID}` - Get post (not implemented yet)

**Interactions:**

- `POST /interactions/{action}` - like, comment, share, gift
  - Updates both viewer and creator CategoryScores

**Feed & Search:**

- `GET /rank?user={id}&k=20` - Ranked feed for user
- `GET /search?q={query}&k=10&backend=bow|st` - Search posts

**Echo:**

- `GET /echo/search?image_path={path}&k=5&threshold=0.6` - Face search
- `POST /echo/build` - Rebuild face index

**Veil:**

- `GET /classify/ann?video_path={path}&k=10&frames=8` - Fast ANN classification

**Jobs:**

- `GET /jobs/{job_id}` - Job status
- `POST /jobs/{job_id}/cancel` - Cancel job
- `GET /jobs/debug` - Queue stats

**Admin:**

- `POST /upload` - Upload file
- `GET /uploads/{filename}` - Download file (disabled by default)
- `POST /cache/flush` - Flush cache
- `GET /analytics/categories` - Category stats
- `GET /categories/tree` - Category tree (hierarchical)
- `GET /metrics` - Prometheus metrics
- `GET /health/redis` - Redis health check
- `GET /health/mongo` - MongoDB health check

**UI:**

- `GET /ui` - Web interface
- `GET /` - Redirects to `/ui`

### Authentication

**Optional API key:**

```bash
export KNOT_API_KEY=your-secret-key
```

Write endpoints (POST/PUT/DELETE) require `X-API-Key` header:

```bash
curl -X POST http://localhost:8000/users \
  -H "X-API-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"username": "alice"}'
```

Read endpoints (GET) don't require auth.

### Rate Limiting

**In-memory (default):**

- 60 requests per minute per client
- Per-endpoint tracking
- Uses client IP or API key

**Redis-backed:**

```bash
export REDIS_URL=redis://localhost:6379/0
export KNOT_RATE_BACKEND=redis
```

Fixed-window rate limiting with automatic expiration.

### Caching

**In-memory (default):**

- 60-second TTL
- Key-value store
- Auto-cleanup

**Redis-backed:**

```bash
export REDIS_URL=redis://localhost:6379/0
export KNOT_CACHE_ENABLED=1
export KNOT_CACHE_TTL=60
export KNOT_CACHE_PREFIX=knot:cache
```

**Cached endpoints:**

- `/search` - Avoids rebuilding index
- (More can be added)

### Web UI

**Location:** `api/static/index.html`

**Features:**

- User creation/login
- Post creation with media upload
- File preview (video/audio/image)
- Interaction buttons (like/comment/share/gift)
- Feed ranking
- Search
- Echo face search (NEW!)
- Cache flushing
- Job polling

**Tech:** Vanilla JS, no frameworks. Simple and readable.

---

## Category System

Categories are the **backbone** of personalization in Knot-Labs.

### The Four Levels

Think of categories as a **hierarchy**:

```
Macro (broad)
  └─ Meso (medium)
      └─ Micro (specific)
          └─ Nano (very specific)
```

**Example:**

```json
{
  "macro": ["Technology", "Entertainment"],
  "meso": ["Programming", "Gaming", "Music", "Movies"],
  "micro": [
    "Python",
    "Machine Learning",
    "FPS",
    "Shooter",
    "Rock",
    "Metal",
    "Action",
    "Sci-Fi"
  ],
  "nano": [
    "Deep Learning",
    "Neural Networks",
    "TensorFlow",
    "CS:GO",
    "Call of Duty",
    "Heavy Metal",
    "Metallica",
    "Star Wars",
    "Blade Runner",
    "Cyberpunk"
  ]
}
```

### Default Sizes

When converting a flat list of labels to a Category object:

- **Macro**: First 2 unique labels
- **Meso**: Next 4 labels
- **Micro**: Next 8 labels
- **Nano**: Remaining labels (usually 12+)

**Total:** 26 labels (2 + 4 + 8 + 12)

### Why Hierarchical?

**Ranking:** Drift can match at different levels:

- Strong match: Same nano category
- Medium match: Same micro or meso
- Weak match: Same macro

**Analytics:** Easy to see trends at different granularities.

**Search:** More keywords for Scribe to index.

### Creating Categories

**From flat list:**

```python
from Mesh.category import make_category_from_micro

labels = ["Gaming", "FPS", "Shooter", "CS:GO", "Esports", ...]
category = make_category_from_micro(labels)
```

**With custom limits:**

```python
from Mesh.category import make_category_with_limits

category = make_category_with_limits(
    labels,
    macro_n=3,    # 3 macro labels
    meso_n=5,     # 5 meso labels
    micro_n=10,   # 10 micro labels
    nano_n=None   # All remaining as nano
)
```

**From post (handles legacy):**

```python
from Mesh.category import ensure_category

post = load_json('Mesh/Posts/post_123.json')
category = ensure_category(post)
# Works even if post has old 'Categories' field or malformed data
```

### Flattening for Search

```python
from Mesh.category import category_texts

category = {
    "macro": ["Technology"],
    "meso": ["AI", "ML"],
    "micro": ["Deep Learning"],
    "nano": ["Neural Networks"]
}

flat = category_texts(category)
# Returns: ["Technology", "AI", "ML", "Deep Learning", "Neural Networks"]
```

### Updating User Preferences

When user interacts with post, their `CategoryScores` update:

```python
# api/main.py → _bump_user_after_action()

def _bump_user_after_action(viewer, creator, category, v_delta, c_delta):
    # Viewer gets points in post's categories
    for lvl in ['macro', 'meso', 'micro', 'nano']:
        for cat in category.get(lvl, []):
            viewer['CategoryScores'][cat] = viewer['CategoryScores'].get(cat, 0) + v_delta

    # Creator gets engagement points
    creator['CategoryScores'][cat] = creator['CategoryScores'].get(cat, 0) + c_delta

    return viewer, creator
```

Delta values:

- Like: +1
- Comment: +2
- Share: +3
- Gift: +amount

---

## Job Queue

Long-running tasks (like Veil classification) run in a **background queue**.

### Why a Queue?

**Problem:** Classifying a video takes 10-60 seconds. We can't block the HTTP request.

**Solution:**

1. Enqueue job
2. Return job ID immediately
3. Client polls `/jobs/{id}` for status
4. Job runs in background thread

### Architecture

**`api/jobs.py`** - Simple in-memory queue

```python
class JobQueue:
    def __init__(self):
        self.q = queue.Queue()              # Job queue
        self.results = {}                    # Job results by ID
        self._worker = None                  # Background thread
        self._cancelled = set()              # Cancelled job IDs
        self._current = None                 # Currently running job ID

    def start(self, handler):
        # Start background worker thread
        # Continuously pulls jobs from queue
        # Calls handler(job) for each job

    def submit(self, job: Dict) -> str:
        # Add job to queue, return job ID

    def status(self, job_id: str) -> Dict:
        # Get job status (queued/running/done/error/cancelled)

    def cancel(self, job_id: str) -> bool:
        # Mark job as cancelled
        # If queued: skipped when dequeued
        # If running: handler must cooperate

    def is_cancelled(self, job_id: str) -> bool:
        # Check if job is cancelled (for cooperative cancellation)
```

### Job Flow

**1. Submit job**

```python
# api/main.py
job = {
    'id': uuid.uuid4().hex,
    'type': 'classify_post',
    'post_path': '/path/to/post.json',
    'media_path': '/path/to/video.mp4',
}
job_id = job_queue.submit(job)
```

**2. Background worker picks it up**

```python
# api/jobs.py → JobQueue.start()
def run():
    while not stopped:
        job = queue.get(timeout=0.25)

        # Check if cancelled
        if job['id'] in cancelled:
            results[job['id']] = {'status': 'cancelled'}
            continue

        # Mark as running
        results[job['id']] = {'status': 'running'}

        # Execute
        try:
            result = handler(job)
            results[job['id']] = {'status': 'done', 'result': result}
        except Exception as e:
            results[job['id']] = {'status': 'error', 'error': str(e)}
```

**3. Handler processes job**

```python
# api/main.py → _handle_job()
def _handle_job(job: Dict) -> Any:
    if job['type'] == 'classify_post':
        # Check cancellation periodically
        def is_cancelled():
            return job_queue.is_cancelled(job['id'])

        # Run Veil
        res = _run_veil_and_get_categories(
            media_path,
            topk=26,
            cancel_check=is_cancelled  # Cooperative cancellation
        )

        if res.get('error') == 'cancelled':
            return {'status': 'cancelled'}

        # Update post with categories
        post['Category'] = make_category_from_micro(res)
        save_json(post_path, post)

        return {'post': post['postID'], 'categories': res}
```

**4. Client polls status**

```python
# Client-side JS
async function pollJob(jobId) {
    while (true) {
        const res = await fetch(`/jobs/${jobId}`);
        const status = await res.json();

        if (status.status === 'done') {
            console.log('Job done!', status.result);
            break;
        } else if (status.status === 'error') {
            console.error('Job failed:', status.error);
            break;
        } else if (status.status === 'cancelled') {
            console.log('Job cancelled');
            break;
        }

        await sleep(2000);  // Poll every 2 seconds
    }
}
```

### Cancellation

**Best-effort cancellation:**

```python
# Cancel via API
POST /jobs/{job_id}/cancel

# Handler checks periodically
def long_running_task(cancel_check):
    for i in range(1000):
        if cancel_check():
            return {'error': 'cancelled'}
        # Do work...
```

**Limitations:**

- If job is queued: cancelled before starting
- If job is running: depends on handler cooperation
- Can't cancel external processes (e.g., subprocess)

### Result TTL

Results are kept for 1 hour (configurable):

```bash
export JOB_RESULT_TTL=3600  # seconds
```

Old results are auto-cleaned during queue processing.

---

## Index Management

All indexes live in `indexes/`:

```
indexes/
├── labels_clip_video_ViT-B-32.npz      # Veil video embeddings
├── labels_clip_image_ViT-B-32.npz      # Veil image embeddings
├── echo_faiss_index.bin                # Echo FAISS index
└── echo_faiss_meta.json                # Echo metadata
```

### Why Centralized?

**Before:** Each component had its own index folder
**After:** All indexes in one place

**Benefits:**

- Easy to find
- Easy to backup
- Easy to .gitignore
- Consistent naming

### Naming Convention

**Veil:** `labels_clip_{mode}_{model}.npz`

- `mode`: video or image
- `model`: CLIP model name (/ replaced with -)

**Echo:** `echo_faiss_{type}.{ext}`

- `index.bin` - FAISS index
- `meta.json` - Metadata

### Building Indexes

**Veil:**

```bash
python -m tools.embed_labels \
  --master Mesh/mastercategories.txt \
  --out indexes \
  --mode video \
  --model ViT-B/32
```

**Echo:**

```bash
python -m Echo.scripts.build_index \
  --known Mesh/Echo/known \
  --out-index indexes/echo_faiss_index.bin \
  --out-meta indexes/echo_faiss_meta.json
```

### Loading Indexes

**Veil:**

```python
# api/label_index.py
def ensure_index(master_labels_file, out_dir, model_name, mode):
    # 1. Load master labels
    # 2. Check if NPZ exists
    # 3. If not, build it
    # 4. Load NPZ
    # 5. Create FAISS index
    # 6. Return {emb, labels, index}
```

**Echo:**

```python
# Echo/scripts/query.py
def load_index(index_path: Path) -> faiss.Index:
    return faiss.read_index(str(index_path))

def load_meta(meta_path: Path) -> dict:
    return json.loads(meta_path.read_text())
```

---

## Mesh Adapters

Adapters **translate** between Mesh (storage) and other components.

### The Problem

**Mesh** stores data in JSON with one schema.
**Drift** expects Python objects with a different schema.

**Without adapters:** You'd have to update Drift code every time Mesh schema changes (or vice versa).

**With adapters:** Change the adapter, both components stay clean.

### User Adapter

**`Mesh/drift_adapter.py`**

```python
def mesh_user_to_drift_user(mesh_user: Dict) -> DriftUser:
    # Extract top 10 preferred categories
    preferred = sorted(
        mesh_user.get("CategoryScores", {}).items(),
        key=lambda kv: kv[1],
        reverse=True
    )
    preferred_categories = [k for k, _ in preferred[:10]]

    # Combine seen creators from multiple sources
    seen_creators = list({
        *mesh_user.get("RecentCreators", []),
        *list(mesh_user.get("ViewerScore", {}).keys())
    })

    # Convert to Drift model
    return DriftUser(
        id=mesh_user.get("userID"),
        preferred_categories=preferred_categories,
        seen_creators=seen_creators,
        recent_creators=mesh_user.get("RecentCreators", []),
        watched_videos=mesh_user.get("SeenPosts", []),
        creator_engagement=mesh_user.get("ViewerScore", {}),
    )
```

**What it does:**

1. Extracts top 10 categories by score
2. Merges seen creators from multiple fields
3. Creates Drift User object

### Post Adapter

```python
def mesh_post_to_drift_video(post: Dict) -> Optional[DriftVideo]:
    # Skip inactive/deleted/flagged posts
    if not (post.get("isActive", True)
            and not post.get("isDeleted", False)
            and not post.get("isFlagged", False)):
        return None

    # Extract category (use first macro)
    cat_obj = ensure_category(post)
    category = cat_obj.get("macro", ["uncategorized"])[0]

    # Convert to Drift model
    return DriftVideo(
        id=post.get("postID"),
        creator_id=post.get("creator"),
        category=category,
        likes=post.get("likes", 0),
        comments=post.get("comments", 0),
        shares=post.get("shares", 0),
        # ... more fields
    )

def mesh_posts_to_drift_candidates(posts_dir: str) -> List[DriftVideo]:
    # Load all posts from directory
    posts = []
    for filename in os.listdir(posts_dir):
        if not filename.endswith('.json'):
            continue

        path = os.path.join(posts_dir, filename)
        post = json.load(open(path))

        # Convert to Drift model
        video = mesh_post_to_drift_video(post)
        if video:
            posts.append(video)

    return posts
```

**What it does:**

1. Loads all post JSONs
2. Filters out inactive/deleted/flagged
3. Converts to Drift VideoCandidate objects
4. Returns list

### Usage

```python
# Load user
user_json = json.load(open('Mesh/Users/alice.json'))
drift_user = mesh_user_to_drift_user(user_json)

# Load posts
candidates = mesh_posts_to_drift_candidates('Mesh/Posts/')

# Rank
from Drift.drift_ranker import rank_videos
ranked = rank_videos(drift_user, candidates)
```

---

## Running Tests

Tests use **pytest**.

### Test Structure

```
tests/
├── conftest.py                  # Shared fixtures
├── test_veil_*.py              # Veil tests
├── test_drift_*.py             # Drift tests
├── test_echo_*.py              # Echo tests
├── test_scribe_*.py            # Scribe tests
├── test_api_*.py               # API tests
└── test_*.py                   # Misc tests
```

### Running Tests

**All tests:**

```bash
pytest
```

**Single file:**

```bash
pytest tests/test_veil_run_smoke.py
```

**Single test function:**

```bash
pytest tests/test_veil_run_smoke.py::test_basic_video_classification
```

**With output:**

```bash
pytest -v -s
```

**Echo tests (with fake embeddings):**

```bash
FAKE_EMB=1 pytest tests/test_echo_*.py
```

### Writing Tests

**Example:**

```python
# tests/test_my_feature.py

def test_category_creation():
    from Mesh.category import make_category_from_micro

    labels = ["Tech", "AI", "ML", "Python"]
    category = make_category_from_micro(labels)

    assert len(category["macro"]) == 2
    assert category["macro"][0] == "Tech"
    assert category["macro"][1] == "AI"

def test_user_adapter():
    from Mesh.drift_adapter import mesh_user_to_drift_user

    mesh_user = {
        "userID": "test_user",
        "CategoryScores": {"Tech": 100, "Gaming": 50},
        "RecentCreators": ["creator_1"],
        "SeenPosts": ["post_1"],
        "ViewerScore": {"creator_1": 5},
    }

    drift_user = mesh_user_to_drift_user(mesh_user)

    assert drift_user.id == "test_user"
    assert "Tech" in drift_user.preferred_categories
    assert "creator_1" in drift_user.seen_creators
```

### Test Fixtures

**`tests/conftest.py`**

```python
import pytest
import tempfile
import shutil

@pytest.fixture
def tmp_dir():
    """Create temporary directory for test."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)

@pytest.fixture
def sample_user():
    """Sample user JSON."""
    return {
        "userID": "test_user",
        "username": "alice",
        "CategoryScores": {"Tech": 100},
        "SeenPosts": [],
    }
```

**Usage:**

```python
def test_with_tmp_dir(tmp_dir):
    # tmp_dir is a temporary directory
    # Automatically cleaned up after test
    path = os.path.join(tmp_dir, 'test.json')
    # ...

def test_with_sample_user(sample_user):
    # sample_user is a dict
    assert sample_user["username"] == "alice"
```

---

## Adding New Features

### Adding a New Ranking Signal

**Goal:** Make Drift consider post view count in ranking.

**Step 1:** Add field to Drift model

**`Drift/models.py`**

```python
class VideoCandidate(BaseModel):
    # ... existing fields
    views: int = 0  # NEW
```

**Step 2:** Add weight

**`Drift/drift_ranker.py`**

```python
WEIGHTS = {
    # ... existing weights
    "views": 0.5,  # NEW
}
```

**Step 3:** Use in scoring

**`Drift/drift_ranker.py`**

```python
def compute_score(user: User, video: VideoCandidate) -> float:
    score = 0.0
    # ... existing signals
    score += video.views * WEIGHTS["views"]  # NEW
    return score
```

**Step 4:** Update adapter

**`Mesh/drift_adapter.py`**

```python
def mesh_post_to_drift_video(post: Dict) -> Optional[DriftVideo]:
    return DriftVideo(
        # ... existing fields
        views=post.get("views", 0),  # NEW
    )
```

**Step 5:** Test

```bash
pytest tests/test_drift_ranker.py
```

Done! Posts with more views now rank higher.

---

### Adding a New Search Backend

**Goal:** Add Elasticsearch backend to Scribe.

**Step 1:** Install dependency

```bash
pip install elasticsearch
```

**Step 2:** Create embedder

**`Scribe/search.py`**

```python
class ElasticsearchEmbedder:
    def __init__(self, host='localhost:9200'):
        from elasticsearch import Elasticsearch
        self.es = Elasticsearch([host])
        self.index_name = 'posts'

    def fit_transform(self, texts: List[str]):
        # Index all texts
        for i, text in enumerate(texts):
            self.es.index(
                index=self.index_name,
                id=i,
                body={'text': text}
            )
        return []  # Not used

    def search(self, query: str, k: int):
        # Use ES query
        res = self.es.search(
            index=self.index_name,
            body={
                'query': {'match': {'text': query}},
                'size': k
            }
        )
        return [(hit['_id'], hit['_score']) for hit in res['hits']['hits']]
```

**Step 3:** Update build_index

**`Scribe/search.py`**

```python
def build_index(posts_dir: str, backend: str = 'bow'):
    # ... existing code
    if backend == 'es':  # NEW
        embedder = ElasticsearchEmbedder()
    elif backend == 'bow':
        embedder = BowEmbedder()
    # ... rest
```

**Step 4:** Update API

**`api/main.py`**

```python
@app.get('/search')
def api_search(request: Request, q: str, k: int = 10, backend: str = 'bow'):
    # backend can now be 'bow', 'st', or 'es'
    # ... rest stays same
```

**Step 5:** Test

```bash
curl "http://localhost:8000/search?q=test&backend=es"
```

---

## Common Patterns

### Loading Mesh Data

**Load user by ID:**

```python
import json
import os

def load_user(user_id: str) -> dict:
    path = f'Mesh/Users/{user_id}.json'
    if not os.path.exists(path):
        return None
    return json.load(open(path, 'r', encoding='utf-8'))
```

**Load user by username:**

```python
def find_user_by_username(username: str) -> dict:
    users_dir = 'Mesh/Users/'
    for filename in os.listdir(users_dir):
        if not filename.endswith('.json'):
            continue

        path = os.path.join(users_dir, filename)
        user = json.load(open(path))

        if user.get('username') == username:
            return user

    return None
```

**Load all posts:**

```python
def load_all_posts() -> List[dict]:
    posts = []
    posts_dir = 'Mesh/Posts/'

    for filename in os.listdir(posts_dir):
        if not filename.endswith('.json'):
            continue

        path = os.path.join(posts_dir, filename)
        try:
            posts.append(json.load(open(path)))
        except Exception:
            pass  # Skip corrupted files

    return posts
```

### Saving Mesh Data

**Save user:**

```python
from Mesh.tools.gen_user import save_user

user = {
    "userID": "user_123",
    "username": "alice",
    # ... more fields
}
save_user(user, 'Mesh/Users/')
```

**Save post:**

```python
from Mesh.tools.gen_videos import save_post

post = {
    "postID": "post_456",
    "creator": "user_123",
    # ... more fields
}
save_post(post, 'Mesh/Posts/')
```

### Category Manipulation

**Create from labels:**

```python
from Mesh.category import make_category_from_micro

labels = ["Tech", "AI", "ML", "Python", "Data Science"]
category = make_category_from_micro(labels)
```

**Get from post:**

```python
from Mesh.category import ensure_category

post = load_json('Mesh/Posts/post_123.json')
category = ensure_category(post)
# Handles legacy formats, missing fields, etc.
```

**Flatten for search:**

```python
from Mesh.category import category_texts

category = post['Category']
keywords = category_texts(category)
# Use in search index
```

### Module Execution

**Always use `-m` flag:**

```bash
# ✓ Correct
python -m veil.run
python -m Echo.scripts.build_index
python -m Mesh.tools.build_mastercategories

# ✗ Wrong (breaks imports)
python veil/run.py
python Echo/scripts/build_index.py
```

---

## Code Examples

### End-to-End: Create User and Post

```python
import json
import uuid
from Mesh.tools.gen_user import make_user, save_user
from Mesh.tools.gen_videos import make_post, save_post
from Mesh.category import make_category_from_micro

# 1. Create user
user = make_user(username="alice", gender="female", country="US")
save_user(user, 'Mesh/Users/')
print(f"Created user: {user['userID']}")

# 2. Create post
categories = ["Gaming", "FPS", "Shooter", "CS:GO", "Esports"]
post = make_post(creator_id=user['userID'], categories=categories)
post['description'] = "Epic gaming montage!"
save_post(post, 'Mesh/Posts/')
print(f"Created post: {post['postID']}")

# 3. Simulate interaction (like)
user['CategoryScores'] = user.get('CategoryScores', {})
for cat in categories:
    user['CategoryScores'][cat] = user['CategoryScores'].get(cat, 0) + 1

user['SeenPosts'] = user.get('SeenPosts', [])
user['SeenPosts'].append(post['postID'])

# Save updated user
save_user(user, 'Mesh/Users/')

# 4. Update post engagement
post['likes'] = post.get('likes', 0) + 1
post['views'] = post.get('views', 0) + 1
save_post(post, 'Mesh/Posts/')

print("Interaction recorded!")
```

### End-to-End: Rank Feed

```python
from Mesh.drift_adapter import mesh_user_to_drift_user, mesh_posts_to_drift_candidates
from Drift.drift_ranker import rank_videos

# Load user
user_json = json.load(open('Mesh/Users/alice.json'))
drift_user = mesh_user_to_drift_user(user_json)

# Load posts
candidates = mesh_posts_to_drift_candidates('Mesh/Posts/')

# Rank
ranked = rank_videos(drift_user, candidates)

# Show top 5
print("Top 5 posts for alice:")
for i, video in enumerate(ranked[:5], 1):
    print(f"{i}. {video.id} (score: {video.score}, category: {video.category})")
```

### End-to-End: Search Posts

```python
from Scribe.search import build_index

# Build index
index = build_index('Mesh/Posts/', backend='bow')

# Search
results = index.search('gaming fps shooter', k=10)

# Show results
print("Search results:")
for post_id, score in results:
    print(f"- {post_id} (score: {score:.3f})")
```

### End-to-End: Classify Video

```python
import subprocess
import json

# Run Veil
result = subprocess.run([
    'python', '-m', 'veil.run',
    '--mode', 'video',
    '--video', '/path/to/video.mp4',
    '--master_labels_file', 'Mesh/mastercategories.txt',
    '--frames', '4',
    '--topk', '26'
], capture_output=True, text=True)

# Parse output (Veil prints JSON)
output = result.stdout
labels = json.loads(output)

print("Top labels:", labels[:10])

# Create category
from Mesh.category import make_category_from_micro
category = make_category_from_micro(labels)

# Update post
post = json.load(open('Mesh/Posts/post_123.json'))
post['Category'] = category
json.dump(post, open('Mesh/Posts/post_123.json', 'w'), indent=2)
```

---

## Common Issues

### 1. Import Errors

**Problem:**

```bash
$ python veil/run.py
ModuleNotFoundError: No module named 'veil.src'
```

**Cause:** Running script directly instead of as module.

**Fix:**

```bash
python -m veil.run  # ✓ Correct
```

**Why:** Python's module system expects packages to be run from project root with `-m` flag.

---

### 2. Veil Timeouts

**Problem:** Classification job times out with `{"error": "timeout"}`

**Cause:** First run downloads models (CLIP, Whisper, YAMNet) which takes time.

**Fix:**

```bash
# Option 1: Precompute embeddings
python -m tools.embed_labels --master Mesh/mastercategories.txt --out indexes --mode video

# Option 2: Increase timeout
export KNOT_VEIL_TIMEOUT_SEC=600
python -m uvicorn api.main:app

# Option 3: Fast boot mode
export VEIL_FAST_BOOT=true
python -m uvicorn api.main:app
```

---

### 3. FFmpeg Missing

**Problem:**

```
FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'
```

**Cause:** FFmpeg not installed or not in PATH.

**Fix:**

```bash
# Windows (with Chocolatey)
choco install ffmpeg

# Mac
brew install ffmpeg

# Linux
sudo apt-get install ffmpeg

# Verify
ffmpeg -version
```

---

### 4. Echo/Dlib Installation Fails

**Problem:**

```
ERROR: Could not build wheels for dlib
```

**Cause:** Dlib requires C++ compiler.

**Fix (Windows):**

1. Install Visual Studio Build Tools
2. Or use prebuilt wheels: https://github.com/ageitgey/face_recognition_models

**Fix (Mac/Linux):**

```bash
# Install dependencies
sudo apt-get install cmake
sudo apt-get install build-essential

# Then reinstall
pip install dlib face_recognition
```

**Alternative:** Use fake embeddings for testing:

```bash
FAKE_EMB=1 python -m Echo.scripts.build_index --known Mesh/Echo/known
```

---

### 5. Empty Index

**Problem:** Echo index builds but has 0 faces.

**Cause:** No images in `Mesh/Echo/known/` or no faces detected.

**Fix:**

1. Check directory: `ls Mesh/Echo/known/`
2. Add images organized by person:
   ```
   Mesh/Echo/known/
   ├── alice/
   │   └── photo.jpg
   └── bob/
       └── photo.jpg
   ```
3. Rebuild: `python -m Echo.scripts.build_index`

---

### 6. Port Already in Use

**Problem:**

```
ERROR: [Errno 98] Address already in use
```

**Cause:** Another process using port 8000.

**Fix:**

```bash
# Find process
lsof -i :8000  # Mac/Linux
netstat -ano | findstr :8000  # Windows

# Kill it
kill -9 <PID>  # Mac/Linux
taskkill /PID <PID> /F  # Windows

# Or use different port
uvicorn api.main:app --port 8001
```

---

### 7. Redis Connection Failed

**Problem:**

```
redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379
```

**Cause:** Redis not running or wrong URL.

**Fix:**

```bash
# Check if Redis is running
redis-cli ping

# Start Redis
redis-server

# Or disable Redis features
unset REDIS_URL
unset KNOT_RATE_BACKEND
```

---

### 8. Category Scores Not Updating

**Problem:** User interacts with posts but `CategoryScores` don't change.

**Cause:** Interaction endpoint not called or post has no categories.

**Fix:**

1. Check post has `Category` field:

   ```python
   post = json.load(open('Mesh/Posts/post_123.json'))
   print(post.get('Category'))  # Should not be None
   ```

2. Verify interaction endpoint:

   ```bash
   curl -X POST http://localhost:8000/interactions/like \
     -H "Content-Type: application/json" \
     -d '{
       "viewer": "alice",
       "creator": "bob",
       "post": "post_123"
     }'
   ```

3. Check user file updated:
   ```python
   user = json.load(open('Mesh/Users/alice.json'))
   print(user.get('CategoryScores'))  # Should have scores
   ```

---

## Performance Tips

### 1. Precompute Embeddings

**Slow:** Build embeddings on first classification
**Fast:** Precompute once, reuse forever

```bash
python -m tools.embed_labels --master Mesh/mastercategories.txt --out indexes --mode video
python -m tools.embed_labels --master Mesh/mastercategories.txt --out indexes --mode image
```

**Speedup:** 10-60 seconds → 2-5 seconds per classification

---

### 2. Use Redis Caching

**Slow:** Rebuild search index on every query
**Fast:** Cache results in Redis

```bash
export REDIS_URL=redis://localhost:6379/0
export KNOT_CACHE_ENABLED=1
export KNOT_CACHE_TTL=60
```

**Speedup:** 100-500ms → 5-10ms (for cache hits)

---

### 3. Limit Veil Frames

**Slow:** Sample 16 frames per video
**Fast:** Sample 4 frames

```bash
export KNOT_VEIL_FRAMES=4
```

**Speedup:** 30 seconds → 10 seconds
**Trade-off:** Slightly less accurate

---

### 4. Disable Whisper

**Slow:** Transcribe audio with Whisper
**Fast:** Skip speech analysis

```bash
export KNOT_VEIL_USE_WHISPER=false
```

**Speedup:** 20 seconds → 10 seconds
**Trade-off:** No speech-based labels

---

### 5. Use BoW Instead of Transformers

**Slow:** Sentence-Transformers semantic search
**Fast:** Bag-of-words TF-IDF

```bash
curl "http://localhost:8000/search?q=gaming&backend=bow"
```

**Speedup:** 200ms → 20ms
**Trade-off:** Less semantic, more keyword-based

---

## Debugging Guide

### Enable Verbose Logging

**Veil:**

```bash
python -m veil.run --verbose ...
```

**Echo:**

```bash
python -m Echo.scripts.build_index --verbose ...
```

**API:**

```python
# api/main.py (edit logging level)
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

### Inspect Job Queue

**Endpoint:**

```bash
curl http://localhost:8000/jobs/debug
```

**Response:**

```json
{
  "queued_estimate": 2,
  "running": "job_abc123",
  "results_total": 45,
  "cancelled_total": 3
}
```

---

### Check Indexes

**Veil embeddings:**

```bash
ls -lh indexes/labels_clip_*.npz
```

**Echo index:**

```bash
ls -lh indexes/echo_faiss_*
```

**Load and inspect:**

```python
import numpy as np

# Veil
data = np.load('indexes/labels_clip_video_ViT-B-32.npz')
print(data['labels'])  # Label list
print(data['embeddings'].shape)  # (N, 512)

# Echo
import json
meta = json.load(open('indexes/echo_faiss_meta.json'))
print(meta['count'])  # Number of faces
print(meta['items'][:5])  # First 5 faces
```

---

### Profile Veil Performance

```python
import time

start = time.time()
# Run classification
print(f"Total: {time.time() - start:.2f}s")
```

**Add timing to veil.run:**

```python
# veil/src/veil/run.py
import time

# Around frame extraction
t0 = time.time()
frames = extract_frames(video, n=frames)
print(f"Frame extraction: {time.time() - t0:.2f}s")

# Around CLIP
t0 = time.time()
video_emb = clip_encode(frames)
print(f"CLIP encoding: {time.time() - t0:.2f}s")
```

---

## Environment Variables

### Veil

| Variable                  | Default | Description                              |
| ------------------------- | ------- | ---------------------------------------- |
| `KNOT_VEIL_FRAMES`        | 4       | Number of frames to sample               |
| `KNOT_VEIL_USE_WHISPER`   | true    | Enable speech transcription              |
| `KNOT_VEIL_TIMEOUT_SEC`   | 600     | Classification timeout                   |
| `KNOT_SPEECH_MAX_SEC`     | 45      | Max audio for Whisper                    |
| `KNOT_AUDIO_MAX_SEC`      | 20      | Max audio for YAMNet                     |
| `VEIL_CACHED_ONLY`        | false   | Only use precomputed embeddings          |
| `VEIL_FAST_BOOT`          | false   | Skip multi-template embeddings           |
| `VEIL_CROSSMODE_FALLBACK` | true    | Reuse other mode's embeddings if missing |

### API

| Variable             | Default    | Description                            |
| -------------------- | ---------- | -------------------------------------- |
| `KNOT_API_KEY`       | (none)     | Optional API key for auth              |
| `KNOT_SERVE_UPLOADS` | 0          | Enable GET /uploads/{file}             |
| `KNOT_CACHE_ENABLED` | 1          | Enable response caching                |
| `KNOT_CACHE_TTL`     | 60         | Cache TTL in seconds                   |
| `KNOT_CACHE_PREFIX`  | knot:cache | Redis cache key prefix                 |
| `KNOT_RATE_BACKEND`  | memory     | Rate limit backend (memory/redis)      |
| `KNOT_CORS_ORIGINS`  | (none)     | CORS allowed origins (comma-separated) |

### Redis

| Variable              | Default | Description                                    |
| --------------------- | ------- | ---------------------------------------------- |
| `REDIS_URL`           | (none)  | Redis connection URL                           |
| `REDIS_SSL_CERT_REQS` | (none)  | SSL cert requirements (none/optional/required) |

### Echo

| Variable   | Default | Description                   |
| ---------- | ------- | ----------------------------- |
| `FAKE_EMB` | 0       | Use fake embeddings (testing) |

### Jobs

| Variable               | Default | Description                |
| ---------------------- | ------- | -------------------------- |
| `JOB_RESULT_TTL`       | 3600    | Job result TTL in seconds  |
| `KNOT_JOBS_POLL_LIMIT` | 180     | Rate limit for job polling |

---

## API Endpoints

### Quick Reference

**Users:**

- `POST /users` - Create user
- `GET /users/{id}` - Get user

**Posts:**

- `POST /posts` - Create post

**Interactions:**

- `POST /interactions/like`
- `POST /interactions/comment`
- `POST /interactions/share`
- `POST /interactions/gift`

**Feed & Search:**

- `GET /rank?user={id}&k=20`
- `GET /search?q={query}&k=10&backend=bow`

**Echo:**

- `GET /echo/search?image_path={path}&k=5`
- `POST /echo/build`

**Veil:**

- `GET /classify/ann?video_path={path}&k=10`

**Jobs:**

- `GET /jobs/{id}`
- `POST /jobs/{id}/cancel`

**Admin:**

- `POST /upload`
- `POST /cache/flush`
- `GET /analytics/categories`
- `GET /health/redis`

**UI:**

- `GET /ui`

---

## File Locations

### Data

| Path                        | Contents                |
| --------------------------- | ----------------------- |
| `Mesh/Users/*.json`         | User profiles           |
| `Mesh/Posts/*.json`         | Posts                   |
| `Mesh/Echo/known/`          | Reference face images   |
| `Mesh/Echo/queries/`        | Query images            |
| `Mesh/Uploads/`             | Uploaded media          |
| `Mesh/mastercategories.txt` | Master label list       |
| `Mesh/master_tree.json`     | Hierarchical categories |

### Indexes

| Path                           | Contents              |
| ------------------------------ | --------------------- |
| `indexes/labels_clip_*.npz`    | Veil label embeddings |
| `indexes/echo_faiss_index.bin` | Echo FAISS index      |
| `indexes/echo_faiss_meta.json` | Echo metadata         |

### Code

| Path                    | Contents              |
| ----------------------- | --------------------- |
| `api/main.py`           | API server            |
| `api/jobs.py`           | Job queue             |
| `Mesh/category.py`      | Category functions    |
| `Mesh/drift_adapter.py` | Mesh→Drift adapters   |
| `Drift/drift_ranker.py` | Ranking algorithm     |
| `Scribe/search.py`      | Search engine         |
| `Echo/scripts/`         | Face recognition CLI  |
| `veil/src/veil/`        | Classification engine |

---

## Final Notes

**This is a sandbox.** Knot-Labs is built for experimentation. It's not production-ready, and that's okay. The goal is to understand how it work under the hood.

**Code quality varies.** Some parts are polished, some are prototypes. That's the nature of a sandbox project.

**Ask questions.** If something doesn't make sense, it's probably not documented well enough. Open an issue, ask the team, or just read the code.

**Have fun.** Building things is fun. Breaking things is fun. Understanding how complex systems work is incredibly fun.

**One last thing:** Programming is like an ex - it keeps coming back with new problems you thought you'd fixed and insists everything is your fault. At least with code, you can debug the relationship. 😅

**Good luck!** 🚀

---

**Document Version:** 1.0
**Last Updated:** 2025-09-30
**Maintained By:** Stiven Gjekaj
