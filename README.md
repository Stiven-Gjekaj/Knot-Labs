# Knot-Labs

Knot-Labs brings together four experimental programs designed to regulate key parts of a social media platform: posting, engagement, feed, and search.

## Projects

| Directory | Purpose |
|-----------|---------|
| [Knot-Veil](Knot-Veil) | Zero-shot audio+video classifier that analyzes uploads to categorize content without task-specific training, helping moderate what gets posted. |
| [Knot-Mesh](Knot-Mesh) | Lightweight local database that stores users and posts as JSON and updates engagement scores based on platform activity. |
| [Knot-Drift](Knot-Drift) | Ranks candidate videos for a user using simple scores to assemble a personalized feed. |
| [Knot-Scribe](Knot-Scribe) | Environment for category experimentation with an interactive demo that generates categories, creates random videos, and searches them semantically. |

Each project includes its own README with setup instructions and demos.

## Getting started

Clone the repository and explore each module individually. Example:

```bash
cd Knot-Mesh
python demo.py  # run the engagement database demo
```

## License

This repository is released under the [MIT License](LICENSE).
