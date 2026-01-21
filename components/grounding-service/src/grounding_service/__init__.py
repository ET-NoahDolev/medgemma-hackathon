"""grounding-service package."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from grounding_service import agent, mcp_server, schemas, umls_client

__all__ = ["agent", "mcp_server", "schemas", "umls_client"]


def __getattr__(name: str):
    """Lazy module exports to avoid importing optional heavy deps at import time."""
    if name in __all__:
        return importlib.import_module(f"{__name__}.{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
