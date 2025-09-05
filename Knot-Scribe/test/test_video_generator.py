import json
import json
import subprocess
import sys


def test_random_video_generation(tmp_path):
    lines = [
        "a video about alpha | a photo of alpha",
        "a video about beta | a photo of beta",
        "a video about gamma | a photo of gamma",
        "a video about delta | a photo of delta",
    ]
    master = tmp_path / "mastercategories.txt"
    master.write_text("\n".join(lines), encoding="utf-8")
    cmd = [
        sys.executable,
        "scripts/generate_random_videos.py",
        "--master",
        str(master),
    ]
    out = subprocess.check_output(cmd, text=True)
    data = json.loads(out.splitlines()[0])
    assert len(data["categories"]) == 3
    assert set(data["categories"]).issubset({"alpha", "beta", "gamma", "delta"})
    assert isinstance(data["creator"], str)
