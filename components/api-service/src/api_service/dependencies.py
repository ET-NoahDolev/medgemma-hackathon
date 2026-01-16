"""FastAPI dependencies for shared resources."""

from __future__ import annotations

from .storage import Storage, get_engine


def get_storage() -> Storage:
    """Provide a storage instance for request handlers."""
    return Storage(get_engine())
