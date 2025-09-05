"""ID generation utilities."""
from __future__ import annotations

import uuid


def new_id(prefix: str = "") -> str:
    """Return a short unique id with optional prefix."""
    return f"{prefix}{uuid.uuid4().hex[:8]}"
