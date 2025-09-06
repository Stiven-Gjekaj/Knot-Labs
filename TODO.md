# Knot-Labs TODOs (Next Iterations)

1) Improved ranking signals (Drift)
- Add recency decay, category affinity weights, dwell-time proxy, creator freshness, and diversity penalties; make weights configurable.

2) GUI enhancements
- Thumbnails, progress bars for Veil jobs, sortable ranking table, and inline actions from search results with live updates.

3) SQLite persistence for Mesh
- Introduce SQLite with schemas for users, posts, and engagements; add DAO layer, migrations, and JSON import/export tools.

4) Auth & API keys
- Add simple auth (JWT or API keys) to FastAPI; enforce scoped actions per user and protect write endpoints.

5) Rate limiting & quotas
- Per-IP and per-user throttles for posts/interactions/search; FastAPI dependency for limits and clear error responses.

6) Observability & metrics
- Structured logging, request/handler timing, Prometheus metrics for API and job queue; basic dashboard.

7) Lint/format/type + CI upgrades
- Add pyproject, ruff/black config, mypy; expand CI to run linting and type checks in addition to tests.

8) Multi‑modal Scribe
- Fuse text embeddings with Veil outputs (visual/audio) and support hybrid search (BM25/TF‑IDF + dense) with tunable weights.

9) Personalization pipeline
- Offline jobs to compute per-user/category embeddings and creator affinity; persist vectors and use in ranking/search.

10) Export/Import tooling
- NDJSON export of Mesh entities and import with deduplication; admin scripts and docs.
