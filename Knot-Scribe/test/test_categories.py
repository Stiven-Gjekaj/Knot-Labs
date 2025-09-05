import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.generate_categories import (  # noqa: E402
    ADJECTIVES,
    NOUNS,
    extract_categories,
    random_categories,
)


def test_extract_normalization():
    lines = [
        "a video about cars | a photo of cars",
        "A PHOTO OF   Cityscapes",
        "a video of   the forests",
        "a photo about cars",
    ]
    cats = extract_categories(lines)
    assert sorted(set(cats)) == ["cars", "cityscapes", "forests"]


def test_random_master_generation(tmp_path):
    master = tmp_path / "mastercategories.txt"
    cmd = [
        sys.executable,
        "scripts/generate_categories.py",
        "--file",
        str(master),
        "--count",
        "5",
    ]
    subprocess.check_call(cmd)
    lines = master.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 5
    assert all("a video about" in line and "|" in line for line in lines)


def test_random_categories_unique():
    cats = random_categories(20)
    assert len(cats) == 20
    assert len(set(cats)) == 20


def test_random_categories_too_many():
    max_pairs = len(ADJECTIVES) * len(NOUNS)
    with pytest.raises(ValueError):
        random_categories(max_pairs + 1)

