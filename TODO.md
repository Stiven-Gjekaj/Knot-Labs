# Knot-Labs TODOs (Next Iterations)

1) API layer (FastAPI)
- Expose endpoints for creating users/posts, recording interactions, running Veil classification, and ranking via Drift. Enables programmatic E2E flows and future UI integration.

2) Background jobs + queue
- Add a lightweight job runner (e.g., threading + queue) to process Veil classification and score updates asynchronously. Keep demo/GUI responsive and allow batching.

3) Config + ENV
- Centralize paths (Users/Posts/Master file) and model options (CLIP, Whisper size, YAMNet enable) in a single config file and environment variables.

4) Data validation (Pydantic schemas for Mesh)
- Define Mesh User/Post models and validate on load/save. Provide migration helpers to evolve schemas safely.

5) Category analytics
- Track per-category engagement aggregates (global + per-user) and surface top categories/trends over time. Add a simple report command.

6) Improved ranking signals
- Incorporate category affinity, recency decay, dwell time proxies, creator freshness, and diversity penalties directly into Drift, with tunable weights.

7) Veil caching + warmups
- Cache label embeddings and media fingerprints to avoid reprocessing the same post. Optional pre-warm of CLIP/Whisper to reduce first-call latency.

8) Scribe integration
- Plug Scribe embedding/search (e.g., sentence-transformers) to support semantic retrieval of posts and feed reranking with hybrid (BM25 + dense) signals.

9) Packaging + CI
- Add pyproject/ruff/black config, pinned lockfile, pre-commit hooks, and a minimal CI pipeline that runs tests and lints on push.

10) GUI enhancements
- Display thumbnails, progress bars for analysis, sortable tables for rankings, and inline actions (like/comment/share) with live updates.

