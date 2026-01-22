from __future__ import annotations

from functools import lru_cache
from typing import Callable, TypeVar

T = TypeVar("T")


def lazy_singleton(loader: Callable[[], T]) -> Callable[[], T]:
    """Cache the result of a loader function.

    Args:
        loader: Callable that constructs the object to cache.

    Returns:
        A callable that returns the cached instance.
    """
    return lru_cache(maxsize=1)(loader)
