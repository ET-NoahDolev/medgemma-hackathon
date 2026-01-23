from __future__ import annotations

import pytest

from extraction_service.chunking import chunk_document
from extraction_service.react_graph import build_extraction_graph
from extraction_service.tools import ExtractionToolFactory


def test_chunk_document_detects_sections() -> None:
    text = (
        "Inclusion Criteria:\n"
        "Age >= 18 years.\n\n"
        "Additional inclusion details.\n\n"
        "Exclusion Criteria:\n"
        "Pregnant or breastfeeding.\n"
    )
    chunks = chunk_document(text, max_tokens=5, overlap_tokens=2)
    assert chunks, "Expected at least one chunk"
    assert chunks[0].section_type == "inclusion"


def test_tool_factory_records_finding() -> None:
    factory = ExtractionToolFactory()
    factory.set_current_chunk(chunk_index=0, chunk_text="Age >= 18 years.")
    tools = factory.create_tools()
    submit_finding = next(
        t for t in tools if getattr(t, "name", t.__name__) == "submit_finding"
    )
    submit_finding(
        {
            "text": "Age >= 18 years",
            "criterion_type": "inclusion",
            "snippet": "Age >= 18",
            "triplet": {
                "entity": "age",
                "relation": "greater_than_or_equal",
                "value": "18",
            },
            "confidence": 0.9,
        }
    )
    results = factory.get_chunk_findings(0)
    assert len(results) == 1
    assert results[0]["has_criteria"] is True


@pytest.mark.anyio
async def test_react_graph_records_no_criteria() -> None:
    async def dummy_agent(_prompt_vars: dict) -> None:
        return None

    factory = ExtractionToolFactory()
    graph = build_extraction_graph(
        agent_loader=lambda: dummy_agent, tool_factory=factory
    )
    chunks = chunk_document(
        "No eligibility info here.", max_tokens=50, overlap_tokens=0
    )
    state = {
        "messages": [],
        "chunks": chunks,
        "chunk_index": 0,
        "total_chunks": len(chunks),
        "findings": [],
        "reasoning_steps": [],
    }
    final_state = await graph.ainvoke(state)
    assert final_state["findings"], "Expected a no-criteria finding to be recorded"
    assert final_state["findings"][0]["has_criteria"] is False
