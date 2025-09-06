# Knot-Labs

Knot-Labs is a unified, multi-component lab for prototyping a social media stack. It integrates four systems that now work together:

- Veil: zero-shot media classification for uploads
- Mesh: lightweight local engagement database and utilities
- Drift: simple feed ranking over candidates
- Scribe: search engine AI

All per-project generators/validators and per-project READMEs have been removed in favor of a single, consolidated workflow documented here. The only requirements file is the root `requirements.txt`.

## Quick Start

1. Install dependencies (Python 3.10+):

```bash
pip install -r requirements.txt
```

2. Build or refresh the master categories list (written to `Mesh/mastercategories.txt`):

```bash
python Mesh/tools/build_mastercategories.py
```

3. Run the integrated demo (CLI):

```bash
python demo.py
```
Veil’s examples directory and Scribe’s data directory were removed. Veil’s category build tool was moved to Mesh and standardized to output `Mesh/mastercategories.txt`.

## Components

- Veil: Zero-shot audio+video classifier for uploads. Encodes video frames and/or audio transcripts, performs label scoring, and can be used to annotate posts during upload.
- Mesh: Local JSON-backed store for users and posts with engagement tracking (views, likes, comments, shares, gifts) and simple query helpers. Hosts the canonical `mastercategories.txt` and the script to rebuild it.
- Drift: Feed ranking that scores candidate posts for a user using simple, explainable features.
- Scribe: Lightweight harness for category experiments and demos. Sample generators/validators were removed to centralize the workflow.

## Data: Master Categories

- Canonical file: `Mesh/mastercategories.txt`
- Rebuild with: `python Mesh/tools/build_mastercategories.py`

This file can be used by Veil for classification prompts and by other components for category-aware behavior.

## Notes on Cleanup

- Removed sample generators and validators across projects.
- Moved `Veil/tools/build_mastercategories.py` to `Mesh/tools/` and updated it to write to `Mesh/mastercategories.txt`.
- Removed per-project `requirements.txt`; only the root `requirements.txt` is used.
- Removed `Veil/examples/` and `Scribe/data/`.
- Consolidated documentation into this root README.

## License

This repository is released under the [MIT License](LICENSE).



4. Optional GUI demo (PySimpleGUI):

```bash
python gui_demo.py
```

5. Run tests (pytest):

```bash
pytest -q
```
