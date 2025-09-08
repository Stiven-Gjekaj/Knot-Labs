"""Label loader for the 1000-category master list.

Each line of the master file is formatted as:
    a video about <category> | a photo of <category>

This module parses the file and exposes helpers to select labels by modality.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Dict


Mode = Literal["video", "photo"]


@dataclass(frozen=True)
class MasterLabels:
    video_labels: List[str]
    photo_labels: List[str]


def load_master_labels(path, expect_exact_count=None):
    """Parse a mastercategories.txt file into video/photo lists.

    Raises ValueError on malformed lines or if the count exceeds 1000.

    - path: filesystem path to the master file
      - expect_exact_count: if int, requires exactly that many entries; if True,
        requires exactly 1000 entries; if False, only enforces <= 1000.
    """
    video: List[str] = []
    photo: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        # keep non-empty, ignore comments
        lines = [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    for i, ln in enumerate(lines, 1):
        if ln.count("|") != 1:
            raise ValueError(f"Line {i} must contain exactly one '|': {ln}")
        left, right = [p.strip() for p in ln.split("|", 1)]
        if not left.startswith("a video about "):
            raise ValueError(f"Line {i} left must start with 'a video about ': {left}")
        if not right.startswith("a photo of "):
            raise ValueError(f"Line {i} right must start with 'a photo of ': {right}")
        video.append(left)
        photo.append(right)

    if isinstance(expect_exact_count, bool):
        if expect_exact_count:
            if len(lines) != 1000:
                raise ValueError(f"Expected 1000 entries, found {len(lines)}")
        else:
            if len(lines) > 1000:
                raise ValueError(f"Too many entries: {len(lines)} > 1000")
    elif isinstance(expect_exact_count, int):
        if len(lines) != expect_exact_count:
            raise ValueError(f"Expected {expect_exact_count} entries, found {len(lines)}")
    else:
        if len(lines) > 1000:
            raise ValueError(f"Too many entries: {len(lines)} > 1000")

    if len(set(video)) != len(video):
        raise ValueError("Duplicate left-side (video) entries")
    if len(set(photo)) != len(photo):
        raise ValueError("Duplicate right-side (photo) entries")

    return MasterLabels(video_labels=video, photo_labels=photo)


def select_labels(master: MasterLabels, mode: Mode) -> List[str]:
    """Return the label list for a given mode ('video' or 'photo')."""
    return master.video_labels if mode == "video" else master.photo_labels

