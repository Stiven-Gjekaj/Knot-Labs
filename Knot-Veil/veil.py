"""Veil module: simple tag classifier."""
import os
import random
from typing import List, Dict
import argparse


class Veil:
    """Assigns up to three realistic tags to an item based on filename keywords."""

    DEFAULT_CATEGORIES = [
        "music",
        "sports",
        "travel",
        "news",
        "fun",
        "education",
        "food",
        "gaming",
        "technology",
        "art",
        "science",
        "nature",
        "animals",
        "fashion",
        "health",
        "history",
        "finance",
        "comedy",
        "film",
        "automotive",
    ]

    KEYWORDS: Dict[str, List[str]] = {
        "music": ["music", "song", "guitar", "piano", "concert"],
        "sports": ["sport", "soccer", "football", "basketball", "tennis"],
        "travel": ["travel", "trip", "journey", "vacation", "tour"],
        "news": ["news", "update", "breaking"],
        "fun": ["fun", "game", "prank", "party"],
        "education": ["education", "tutorial", "lesson", "howto"],
        "food": ["food", "recipe", "cooking", "kitchen"],
        "gaming": ["gaming", "gameplay", "esports"],
        "technology": ["tech", "technology", "gadget"],
        "art": ["art", "painting", "drawing", "design"],
        "science": ["science", "experiment", "physics", "chemistry"],
        "nature": ["nature", "wildlife", "outdoor"],
        "animals": ["animal", "dog", "cat", "pet"],
        "fashion": ["fashion", "style", "clothes"],
        "health": ["health", "fitness", "workout"],
        "history": ["history", "historic", "ancient"],
        "finance": ["finance", "stock", "market", "economy"],
        "comedy": ["comedy", "standup", "funny"],
        "film": ["movie", "film", "cinema"],
        "automotive": ["car", "auto", "vehicle", "drive"],
    }

    def __init__(self, categories: List[str] | None = None) -> None:
        self.categories = categories or self.DEFAULT_CATEGORIES.copy()

    def classify(self, path: str) -> List[str]:
        """Return up to three tags using filename keywords with fallback randomness."""
        name = os.path.basename(path).lower()
        tags: List[str] = []
        for cat in self.categories:
            keywords = self.KEYWORDS.get(cat, [])
            if any(k in name for k in keywords):
                tags.append(cat)
        if not tags:
            tags.append(random.choice(self.categories))
        while len(tags) < 3:
            choice = random.choice(self.categories)
            if choice not in tags:
                tags.append(choice)
        return tags[:3]


def main() -> None:
    """Simple command line interface for the lightweight classifier.

    The heavy fusion runner lives in ``veil.classify_veil``.  For tests and
    demos we expose a minimal CLI that mirrors the behaviour of the ``Veil``
    class.  Usage is simply::

        python -m veil <path>

    It prints three whitespace separated categories.
    """

    parser = argparse.ArgumentParser(description="Classify a media file with Veil")
    parser.add_argument("path", help="Path to image or video file")
    args = parser.parse_args()

    v = Veil()
    tags = v.classify(args.path)
    print(" ".join(tags))


if __name__ == "__main__":  # pragma: no cover - exercised via CLI test
    main()
