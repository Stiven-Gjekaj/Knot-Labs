# Knot-Labs TODOs (Next Iterations)

Backlog (next)

- Add audio fusion controls to the UI (use_audio, w_video/w_audio sliders) and persist choices.
- Macro/meso browser polish: search/filter; expand/collapse all.
- Optional CLAP checkpoint bootstrap script and env docs.

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
