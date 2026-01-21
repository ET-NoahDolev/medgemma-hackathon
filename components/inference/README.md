# inference

Shared MedGemma model-loading and LangGraph agent factories used by multiple services
in this repo.

This package intentionally centralizes:
- MedGemma model loading + quantization configuration
- LangGraph ReAct agent creation
- Jinja2 prompt rendering

