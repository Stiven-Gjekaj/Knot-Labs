from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]):
    subprocess.run(["python", str(ROOT / "demo.py")] + cmd, check=True)


def test_examples(tmp_path):
    # ensure sample file exists
    sample = ROOT / "samples"
    sample.mkdir(exist_ok=True)
    (sample / "test.png").write_bytes(b"test")

    run(["labs", "tester1"])
    run(["post", "postA", str(sample / "test.png")])
    run(["like", "postA"])
    run(["comment", "postA"])
    run(["feed", "5"])
    run(["gen_samples", "10"])
    run(["search", "basketball", "highlights"])
    run(["info", "post", "postA"])
    run(["info", "user", "tester1"])
