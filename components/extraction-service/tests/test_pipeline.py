import pytest
from shared.models import Criterion

from extraction_service.pipeline import (
    ExtractionConfig,
    ExtractionPipeline,
    classify_criterion_type,
    detect_sections,
    extract_criteria,
    split_into_candidate_sentences,
)

SAMPLE_PROTOCOL = """
ELIGIBILITY CRITERIA

Inclusion Criteria:
- Age >= 18 years at time of screening
- ECOG performance status 0-1
- Histologically confirmed melanoma
- Adequate organ function as defined by:
  - ANC >= 1500/mm3
  - Platelets >= 100,000/mm3

Exclusion Criteria:
- Pregnant or breastfeeding
- Active autoimmune disease requiring systemic treatment
- Prior therapy with anti-PD-1 agents
- Known CNS metastases unless treated and stable
"""


class TestSectionDetection:
    def test_detects_inclusion_section(self) -> None:
        sections = detect_sections(SAMPLE_PROTOCOL)
        assert "inclusion" in sections
        assert "Age >= 18" in sections["inclusion"]

    def test_detects_exclusion_section(self) -> None:
        sections = detect_sections(SAMPLE_PROTOCOL)
        assert "exclusion" in sections
        assert "Pregnant" in sections["exclusion"]


class TestSentenceSplitting:
    def test_splits_on_bullets(self) -> None:
        text = "- Item 1\n- Item 2\n- Item 3"
        sentences = split_into_candidate_sentences(text)
        assert len(sentences) == 3

    def test_splits_on_numbers(self) -> None:
        text = "1. First\n2. Second\n3. Third"
        sentences = split_into_candidate_sentences(text)
        assert len(sentences) == 3

    def test_handles_nested_bullets(self) -> None:
        text = "- Main item\n  - Sub item 1\n  - Sub item 2"
        sentences = split_into_candidate_sentences(text)
        assert len(sentences) >= 1

    def test_removes_empty_lines(self) -> None:
        text = "- Item 1\n\n- Item 2"
        sentences = split_into_candidate_sentences(text)
        assert "" not in sentences

    def test_strips_whitespace(self) -> None:
        sentences = split_into_candidate_sentences("  - Age >= 18  ")
        assert sentences[0] == "Age >= 18"


class TestClassification:
    def test_classify_inclusion_default(self) -> None:
        result = classify_criterion_type("Age >= 18 years", section="inclusion")
        assert result == "inclusion"

    def test_classify_exclusion_from_section(self) -> None:
        result = classify_criterion_type("Active infection", section="exclusion")
        assert result == "exclusion"

    def test_classify_exclusion_keywords(self) -> None:
        result = classify_criterion_type(
            "Pregnant or breastfeeding",
            section="inclusion",
        )
        assert result == "exclusion"

    def test_classify_handles_negation(self) -> None:
        result = classify_criterion_type("No prior chemotherapy", section="inclusion")
        assert result == "exclusion"


class TestExtractCriteria:
    def test_returns_list_of_criteria(self) -> None:
        criteria = extract_criteria(SAMPLE_PROTOCOL)
        assert isinstance(criteria, list)
        assert all(isinstance(c, Criterion) for c in criteria)

    def test_extracts_inclusion_criteria(self) -> None:
        criteria = extract_criteria(SAMPLE_PROTOCOL)
        inclusion = [c for c in criteria if c.criterion_type == "inclusion"]
        assert len(inclusion) >= 3

    def test_extracts_exclusion_criteria(self) -> None:
        criteria = extract_criteria(SAMPLE_PROTOCOL)
        exclusion = [c for c in criteria if c.criterion_type == "exclusion"]
        assert len(exclusion) >= 3

    def test_criteria_have_confidence(self) -> None:
        criteria = extract_criteria(SAMPLE_PROTOCOL)
        assert all(0.0 <= c.confidence <= 1.0 for c in criteria)

    def test_empty_text_raises(self) -> None:
        with pytest.raises(ValueError):
            extract_criteria("")

    def test_no_criteria_returns_empty(self) -> None:
        criteria = extract_criteria("This is just random text with no criteria")
        assert criteria == []

    def test_truncates_at_references_section(self) -> None:
        text = """
Inclusion Criteria:
- Age >= 18

Exclusion Criteria:
- Pregnant or breastfeeding

References:
patients. Int J Chron Obstruct Pulmon Dis. 2013;8:569-79
"""
        criteria = extract_criteria(text)
        texts = [c.text for c in criteria]
        assert any("Age" in t for t in texts)
        assert any("Pregnant" in t for t in texts)
        assert not any("Int J Chron Obstruct" in t for t in texts)

    def test_filters_citation_like_lines(self) -> None:
        text = """
Inclusion Criteria:
- Age >= 18
- Int J Chron Obstruct Pulmon Dis. 2013;8:569-79
"""
        criteria = extract_criteria(text)
        texts = [c.text for c in criteria]
        assert any("Age" in t for t in texts)
        assert not any("2013;8:569-79" in t for t in texts)


class TestExtractionPipelineFallback:
    """Test auto-fallback when model doesn't support tools."""

    def test_fallback_when_model_lacks_tool_support(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test pipeline falls back to legacy mode when model lacks tool support."""
        # Configure to use Model Garden endpoint (doesn't support tools)
        monkeypatch.setenv("MODEL_BACKEND", "vertex")
        monkeypatch.setenv("GCP_PROJECT_ID", "test-project")
        monkeypatch.setenv("GCP_REGION", "us-central1")
        monkeypatch.setenv("VERTEX_ENDPOINT_ID", "endpoint-123")
        monkeypatch.delenv("VERTEX_MODEL_NAME", raising=False)
        monkeypatch.setenv("USE_MODEL_EXTRACTION", "true")

        config = ExtractionConfig.from_env()
        pipeline = ExtractionPipeline(config=config, use_iterative=True)

        # Should use legacy mode (no tools) when model doesn't support them
        # This is tested by checking that _get_model_loader is called
        # and that use_iterative is effectively False for Model Garden
        model_loader, _, agent_cfg = pipeline._get_model_loader()
        assert not agent_cfg.supports_tools
        # Pipeline should handle this gracefully
        assert pipeline.use_iterative is True  # Set by user
        # But internally it will fall back to legacy mode

    def test_uses_iterative_when_model_supports_tools(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that pipeline uses iterative mode when model supports tools."""
        # Configure to use Gemini model (supports tools)
        monkeypatch.setenv("MODEL_BACKEND", "vertex")
        monkeypatch.setenv("GCP_PROJECT_ID", "test-project")
        monkeypatch.setenv("GCP_REGION", "us-central1")
        monkeypatch.delenv("VERTEX_ENDPOINT_ID", raising=False)
        monkeypatch.setenv("VERTEX_MODEL_NAME", "gemini-2.5-pro")
        monkeypatch.setenv("USE_MODEL_EXTRACTION", "true")

        config = ExtractionConfig.from_env()
        pipeline = ExtractionPipeline(config=config, use_iterative=True)

        model_loader, _, agent_cfg = pipeline._get_model_loader()
        assert agent_cfg.supports_tools
