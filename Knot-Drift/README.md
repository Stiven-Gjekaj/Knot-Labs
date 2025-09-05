# Knot!Drift

Part of Knot!Labs.
Ranks candidate videos for a user using simple scores.

## Setup

```bash
pip install -r requirements.txt
```

## Testing Samples

1. **Generate new sample data:**
   - Run:
     ```bash
     python knot-drift/generate_sample_data.py
     ```

2. **Explore/edit generated data:**
   - Users: `knot-drift/data/users.json`
   - Videos: `knot-drift/data/videos.json`
   - Creators (summary): `knot-drift/data/creators.json`

3. **Run the demo:**
   - Execute:
     ```bash
     python knot-drift/demo.py
     ```

The demo reads from `data/users.json` and `data/videos.json`.

## Adding More Score Variables

To add more variables to the scoring system:
1. Add the new field to the `VideoCandidate` class in `models.py`.
2. Update `generate_sample_data.py` to generate the new field for each candidate.
3. Update the scoring logic in `drift_ranker.py` to use the new field (add a line in `compute_score`).
4. Regenerate your sample data and rerun the demo.
