# Knot-Labs TODOs (Next Iterations)

Completed in this iteration

- Improved ranking signals (Drift): added recency decay and configurable weights; category affinity/freshness/diversity handled via weights and run-limits.
- GUI enhancements: generators (users/posts), gender and country selectors, and an indeterminate progress bar for Veil analysis.
- SQLite persistence (initial): lightweight SQLite store for users and posts with write-through on create/update.
- Auth & API keys: FastAPI now checks `X-API-Key` when `KNOT_API_KEY` is set.
- Rate limiting & quotas: simple in-memory per-identity, per-endpoint limiter over a 60s window.

- Redis integration (optional): `REDIS_URL` support, Redis-backed rate limiting (`KNOT_RATE_BACKEND=redis`), request-safe initialization and clean shutdown.
- Caching: lightweight cache with Redis or in-memory fallback; `/search` results cached with TTL (`KNOT_CACHE_TTL`, default 60s).
- Health and admin: `/health/redis` ping endpoint; `/cache/flush` admin endpoint (API-key guarded) to clear memory cache and Redis by prefix.
- Web UI: simple static page served at `/ui` providing core GUI functions (create user, create post + analyze, interactions, rank, search, cache flush).
 - Uploads: `/upload` endpoint to save media to `Mesh/Uploads`; `/ui` now supports browser file upload and auto-fills the media path for analysis.
 - Preview uploads: optional `GET /uploads/{filename}` (enable with `KNOT_SERVE_UPLOADS=1`); UI shows a clickable preview link after upload.
 - Inline previews in Web UI: dedicated Preview section renders video/audio/image inline (with link fallback) after upload.
 - MIME detection: `/upload` returns a `mime` field (basic guess via extension); UI prefers MIME to select the preview element.
 - Root redirect and ping: `/` redirects to `/ui`; added `GET /ping` for connectivity tests.
 - CORS + Pages: `KNOT_CORS_ORIGINS` enables cross-origin calls (e.g., from GitHub Pages). UI supports configurable API base URL and provides “Test API” and “Test CORS” buttons.
 - Docs & config: added `.env` with sensible defaults (serve uploads; CORS for localhost + GitHub Pages). README updated with env usage and Pages setup.
  - Redis KV: added demo KV endpoints (`PUT|GET|DELETE /redis/kv/{key}`) and a Redis KV panel in the UI to set/get/delete keys.

Tests added:

- `tests/test_admin_and_uploads.py` covering `/health/redis`, static `/ui`, `/upload` + `/uploads/{filename}` preview, and `/cache/flush`.
- Observability & metrics: structured logging; Prometheus counters/histograms with `/metrics`; basic request timing middleware; job metrics.
- Lint/format/type config: added `pyproject.toml` with ruff/black/mypy defaults (CI wiring pending).
- Multi-modal Scribe: added `backend="hybrid"` combining BoW and Sentence-Transformers with a tunable weight.
- Personalization pipeline (initial): offline job `Mesh/tools/personalize.py` recomputes per-user `CategoryScores` from `SeenPosts`.
- Export/Import tooling: `Mesh/tools/export_import.py` for NDJSON export/import with simple dedup.

Next Updates:

1. CI wiring for lint/type

- Add GitHub Actions (or preferred CI) to run ruff/black/mypy.

2. Metrics dashboard

- Simple Grafana/Prometheus docker-compose to visualize request rates/latency and job throughput.

3. Veil caching + warmup

- Cache CLIP/ST models; add warmup job and configurable device (CPU/GPU) selection.

4. Hybrid search scoring knobs

- Expose `dense_weight` and category token weights via API/UI; add quick A/B hooks.

5. Category browser/admin

- GUI panel to browse categories, rebuild labels to N, and validate/resolve duplicates.

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

11. Expand Web UI

- Add file upload flow for media (server-side storage) and admin actions (rebuild categories, simulators). Add nicer styling.

12. UI polish passes

- Added responsive two-column layout for main panels on wide screens.
- Added a Compact Mode toggle (saved in localStorage) to tighten spacing.
- Added lightweight toast notifications for success/error actions and a Reset UI button to clear preferences.
- Added Dark Mode toggle (with light theme option) and one-click "Copy curl" buttons for major actions.
