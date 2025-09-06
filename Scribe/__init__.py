"""Scribe: lightweight text search over Mesh posts.

Provides simple in-memory indexing with a fast bag-of-words backend by default,
and an optional Sentence-Transformers backend when available.
"""

from .search import (
    build_index,
    search_posts,
    load_posts,
)

__all__ = [
    "build_index",
    "search_posts",
    "load_posts",
]

