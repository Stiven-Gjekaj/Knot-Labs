"""Helpers for deterministic ID generation in samples."""
from __future__ import annotations


def make_user_id(idx: int) -> str:
    """Return user ID like ``user_0001`` for index 1."""
    return f"user_{idx:04d}"


def make_post_id(idx: int) -> str:
    """Return post ID like ``post_0001`` for index 1."""
    return f"post_{idx:04d}"

