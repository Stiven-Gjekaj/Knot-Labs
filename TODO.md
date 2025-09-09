# Knot-Labs TODOs (Next Iterations)

Backlog (next)

- Macro/meso browser polish: search/filter; expand/collapse all.
- YAMNet tuning: expose top-N event count and label-mapping weight controls in UI/API.

- bump any UI copy in api/static/index.html to display audio options like the docs page
- keep audio weight defaults consistent across CLI/GUI/docs, standardize them (e.g., 0.7 video / 0.3 audio)
- change category system for posts to be 2 macro, 4 meso, 8 micro.

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
