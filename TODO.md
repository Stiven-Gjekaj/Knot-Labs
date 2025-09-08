# Knot-Labs TODOs (Next Iterations)

Backlog (next)

- Macro/meso browser polish: search/filter; expand/collapse all.
- CLAP bootstrap enhancements: optionally provide a default checkpoint URL for quick start and more explicit errors.

Recently Completed

- Integrated hierarchical category builder into `Mesh/tools/build_mastercategories.py` (tree mode available via `--use-tree`).
- Added Categories Tree browser to the Web UI (loads `/categories/tree` and renders macros → mesos → micros).

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

- Admin tools: validate/resolve duplicates; rebuild labels target N; moderation panel.

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

- Admin actions (rebuild categories, simulators); continue visual polish.

12. UI polish passes

- Completed: responsive two-column layout; Compact Mode; toast notifications + Reset UI; Dark/Light theme toggle; Copy curl buttons.
