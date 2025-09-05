from veil import Veil
import subprocess
import sys
from pathlib import Path


def test_classify_returns_three():
    v = Veil()
    tags = v.classify("funny_video.mp4")
    assert len(tags) == 3


def test_classify_keyword_logic():
    v = Veil()
    tags = v.classify("soccer_highlights.mp4")
    assert "sports" in tags


def test_cli_emits_three_categories(tmp_path):
    """Running the lightweight CLI should output three categories."""
    dummy = tmp_path / "video.mp4"
    dummy.touch()
    root = Path(__file__).resolve().parent.parent
    script = root / "Knot-Veil" / "veil.py"
    out = subprocess.check_output([sys.executable, str(script), str(dummy)]).decode().strip().split()
    assert len(out) == 3
