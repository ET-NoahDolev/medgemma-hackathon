"""Gemini-based PDF extraction for eligibility criteria."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel
from shared.mlflow_utils import set_trace_metadata


class CriterionSnippet(BaseModel):
    """A single eligibility criterion snippet."""

    text: str
    criterion_type: str
    confidence: float


class PDFExtractionResult(BaseModel):
    """Structured extraction output for a PDF document."""

    criteria: list[CriterionSnippet]


_PROMPTS_DIR = Path(__file__).parent / "prompts"
_JINJA_ENV = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)))


def _render_prompt() -> str:
    template = _JINJA_ENV.get_template("extract_from_pdf.j2")
    return template.render()


def _get_gemini_client() -> genai.Client:
    project_id = os.getenv("GCP_PROJECT_ID")
    if not project_id:
        raise ValueError("GCP_PROJECT_ID is required for PDF extraction.")
    region = os.getenv("GCP_REGION", "europe-west4")
    return genai.Client(vertexai=True, project=project_id, location=region)


def _model_name() -> str:
    return os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-pro")


def _validate_result(payload: dict[str, Any]) -> PDFExtractionResult:
    if hasattr(PDFExtractionResult, "model_validate"):
        return PDFExtractionResult.model_validate(payload)
    return PDFExtractionResult.parse_obj(payload)


async def extract_criteria_from_pdf(
    *,
    pdf_path: Path | None = None,
    pdf_bytes: bytes | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
) -> PDFExtractionResult:
    """Extract eligibility criteria from a PDF using Gemini.

    Args:
        pdf_path: Optional PDF file path.
        pdf_bytes: Optional PDF bytes (preferred).
        session_id: Optional session ID for trace grouping.
        user_id: Optional user ID for trace grouping.
        run_id: Optional run ID to group all traces from a single extraction run.
    """
    if pdf_bytes is None:
        if pdf_path is None:
            raise ValueError("pdf_path or pdf_bytes is required.")
        pdf_bytes = pdf_path.read_bytes()

    set_trace_metadata(user_id=user_id, session_id=session_id, run_id=run_id)

    client = _get_gemini_client()
    prompt = _render_prompt()
    response = await client.aio.models.generate_content(
        model=_model_name(),
        contents=types.Content(
            role="user",
            parts=[
                types.Part(text=prompt),
                types.Part(
                    inline_data=types.Blob(
                        mime_type="application/pdf",
                        data=pdf_bytes,
                    )
                ),
            ],
        ),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )
    raw = response.text or ""
    if not raw.strip():
        raise ValueError("Gemini returned empty extraction response.")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Gemini returned invalid JSON for extraction.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Gemini extraction payload is not an object.")
    return _validate_result(payload)
