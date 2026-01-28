# inference

Shared MedGemma model-loading and LangGraph agent factories used by multiple services
in this repo.

This package intentionally centralizes:
- MedGemma model loading + quantization configuration
- LangGraph ReAct agent creation
- Jinja2 prompt rendering

## Architecture

The `agent_factory.py` module provides two main functions:

1. **`create_structured_extractor()`**: Creates functions that use `model.with_structured_output()` for direct Pydantic model extraction (used for filtering tasks)

2. **`create_react_agent()`**: Creates LangGraph ReAct agents that can execute tools iteratively, then extract structured output (used for complex tasks requiring tool calls)

Both functions use lazy singleton pattern for model loading and Jinja2 for prompt rendering.

See the [LangGraph Architecture diagram](../../docs/diagrams/langgraph-architecture.md) for detailed information about how these agents are used across the system.
