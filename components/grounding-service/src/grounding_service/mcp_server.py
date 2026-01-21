"""FastMCP server exposing UMLS tools for external MCP protocol clients.

This server can be used by external MCP clients. The agent (agent.py) uses
LangChain tools that call UmlsClient directly, but both implementations
use the same underlying UmlsClient for consistency.
"""

import logging
import os
from typing import Any

from fastmcp import FastMCP  # type: ignore[import-not-found]

from grounding_service.umls_client import UmlsClient

logger = logging.getLogger(__name__)

mcp: FastMCP = FastMCP("UMLS Tools")


@mcp.tool()
def search_concepts(term: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search UMLS for clinical concepts matching a term.

    Args:
        term: Clinical term or phrase to search for.
        limit: Maximum number of results to return (default: 5).

    Returns:
        List of concept dictionaries with code, display, and cui fields.
    """
    api_key = os.getenv("UMLS_API_KEY")
    if not api_key:
        logger.warning("UMLS_API_KEY not set, returning empty results")
        return []

    try:
        with UmlsClient(api_key=api_key) as client:
            candidates = client.search_snomed(term, limit)
            return [
                {
                    "code": c.code,
                    "display": c.display,
                    "cui": c.code,  # For SNOMED, code is the CUI
                    "ontology": c.ontology,
                    "confidence": c.confidence,
                }
                for c in candidates
            ]
    except Exception as e:
        logger.error("Error searching UMLS concepts: %s", e)
        return []


@mcp.tool()
def get_semantic_type(cui: str) -> dict[str, Any]:
    """Get semantic type information for a UMLS concept.

    Args:
        cui: UMLS Concept Unique Identifier.

    Returns:
        Dictionary with semantic type information including TUI and name.
    """
    api_key = os.getenv("UMLS_API_KEY")
    if not api_key:
        logger.warning("UMLS_API_KEY not set, returning empty result")
        return {"cui": cui, "semantic_types": []}

    try:
        with UmlsClient(api_key=api_key) as client:
            tuis = client.get_semantic_types(cui)
            return {
                "cui": cui,
                "semantic_types": tuis,
            }
    except Exception as e:
        logger.error("Error getting semantic type for CUI %s: %s", cui, e)
        return {"cui": cui, "semantic_types": []}


@mcp.tool()
def get_concept_details(cui: str) -> dict[str, Any]:
    """Get detailed information about a UMLS concept.

    Args:
        cui: UMLS Concept Unique Identifier.

    Returns:
        Dictionary with concept details from UMLS API.
    """
    api_key = os.getenv("UMLS_API_KEY")
    if not api_key:
        logger.warning("UMLS_API_KEY not set, returning empty result")
        return {"cui": cui, "details": {}}

    try:
        with UmlsClient(api_key=api_key) as client:
            details = client.get_concept_details(cui)
            return {
                "cui": cui,
                "details": details,
            }
    except Exception as e:
        logger.error("Error getting concept details for CUI %s: %s", cui, e)
        return {"cui": cui, "details": {}}


if __name__ == "__main__":
    mcp.run()
