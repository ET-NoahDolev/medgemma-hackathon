"""LangGraph-based ReAct extraction graph for chunked documents."""

from __future__ import annotations

import logging
from typing import Any, Callable

from langgraph.graph import END, StateGraph
from pydantic import BaseModel

from extraction_service.state import DocumentProcessingState

logger = logging.getLogger(__name__)


class ChunkAgentResult(BaseModel):
    """Lightweight structured response from the ReAct agent."""

    status: str = "ok"
    summary: str | None = None


def build_extraction_graph(
    *,
    agent_loader: Callable[[], Callable[[dict[str, Any]], Any]],
    tool_factory: Any,
) -> Any:
    """Build a chunk-processing graph that uses a ReAct agent per chunk.

    Args:
        agent_loader: Callable returning an async agent invocation function.
        tool_factory: Tool factory that accumulates ChunkFinding results.
    """

    async def process_chunk(state: DocumentProcessingState) -> dict[str, Any]:
        agent = agent_loader()
        chunk = state["chunks"][state["chunk_index"]]
        tool_factory.set_current_chunk(
            chunk_index=state["chunk_index"],
            chunk_text=chunk.text,
            section_type=chunk.section_type,
            page_hint=chunk.page_hint,
        )

        try:
            await agent(
                {
                    "chunk_text": chunk.text,
                    "chunk_index": state["chunk_index"],
                    "total_chunks": state["total_chunks"],
                    "section_type": chunk.section_type or "unknown",
                    "page_hint": chunk.page_hint,
                }
            )
        except Exception as exc:
            logger.error("Chunk agent failed: %s", exc, exc_info=True)
            raise

        new_findings = tool_factory.get_chunk_findings(state["chunk_index"])
        if not new_findings:
            tool_factory.record_no_criteria(state["chunk_index"])
            new_findings = tool_factory.get_chunk_findings(state["chunk_index"])

        return {"findings": new_findings}

    def advance_chunk(state: DocumentProcessingState) -> dict[str, Any]:
        return {"chunk_index": state["chunk_index"] + 1}

    def route_after_chunk(state: DocumentProcessingState) -> str:
        if state["chunk_index"] + 1 >= state["total_chunks"]:
            return END
        return "advance_chunk"

    graph = StateGraph(DocumentProcessingState)
    graph.add_node("process_chunk", process_chunk)
    graph.add_node("advance_chunk", advance_chunk)
    graph.add_edge("advance_chunk", "process_chunk")
    graph.add_conditional_edges("process_chunk", route_after_chunk)
    graph.set_entry_point("process_chunk")
    return graph.compile()
