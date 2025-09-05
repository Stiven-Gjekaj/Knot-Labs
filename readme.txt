Knot: A Local Social Media Backend Simulation
============================================

This repository bundles four subsystems – **Mesh** (JSON database), **Veil** (AI
categoriser), **Drift** (ranking) and **Scribe** (search) – into a single local stack.
Everything runs without external services and stores data under `./data/`.

Installation
------------
```
python -m venv .venv
source .venv/bin/activate  # On Windows use .venv\Scripts\activate
pip install -r requirement.txt
```

Running the Demo
----------------
Run the interactive CLI:
```
python demo.py
```
Or run single commands:
```
python demo.py labs "alice"
python demo.py post "p1" ./some/file.jpg
python demo.py like "p1"
```

Commands
--------
* `labs "userID"` – create/switch active user.
* `post "postID" <path>` – create a post from active user.
* `view|like|comment|share|gift "postID"` – add engagement.
* `gen_samples N` – create N synthetic users and posts.
* `feed [topK]` – show ranked feed (default top 10).
* `search "<query>"` – text search using Scribe.
* `info post "postID"` – show post JSON.
* `info user "userID"` – show user JSON.

Optional Dependencies
---------------------
Heavy ML libraries are optional. Veil falls back to a deterministic hash-based
heuristic if models such as CLIP, Whisper or YAMNet are not installed.

Data Layout
-----------
`./data/` contains JSON files for users, posts, indices and feeds.
`./data/mastercategories.txt` lists the master categories used by Veil and Scribe.

