# Knot-Labs TODOs (Next Iterations)

Completed in this iteration

- Improved ranking signals (Drift): added recency decay and configurable weights; category affinity/freshness/diversity handled via weights and run-limits.
- GUI enhancements: generators (users/posts), gender and country selectors, and an indeterminate progress bar for Veil analysis.
- SQLite persistence (initial): lightweight SQLite store for users and posts with write-through on create/update.
- Auth & API keys: FastAPI now checks `X-API-Key` when `KNOT_API_KEY` is set.
- Rate limiting & quotas: simple in-memory per-identity, per-endpoint limiter over a 60s window.

Next Updates:

1. Observability & metrics

- Structured logging, request/handler timing, Prometheus metrics for API and job queue; basic dashboard.

2. Lint/format/type + CI upgrades

- Add pyproject, ruff/black config, mypy; expand CI to run linting and type checks in addition to tests.

3. Multi-modal Scribe

- Fuse text embeddings with Veil outputs (visual/audio) and support hybrid search (BM25/TF-IDF + dense) with tunable weights.

4. Personalization pipeline

- Offline jobs to compute per-user/category embeddings and creator affinity; persist vectors and use in ranking/search.

5. Export/Import tooling

- NDJSON export of Mesh entities and import with deduplication; admin scripts and docs.

Newly Added Next Updates:

6. SQLite read-path + DAO adoption

- Migrate API and CLI reads to use SQLite via a DAO while keeping JSON as optional export.

7. Drift weights config surface

- Load weights from env or config file and expose an admin endpoint to tweak at runtime.

8. Admin GUI: browse and moderate

- Add a GUI panel to browse users/posts, flag/unflag posts, and view top categories.

9. Job queue status page

- Persist job statuses and add a small web dashboard route to inspect progress/history.

10. Tests for GUI generators and limits

- Add unit tests covering GUI generator actions and API key + rate limiting behaviors.
