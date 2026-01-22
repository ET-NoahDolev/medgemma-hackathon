from __future__ import annotations

from typing import Generator

import pytest


@pytest.fixture(autouse=True)
def disable_model_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    """Disable model extraction for all tests by default.

    This ensures tests run quickly using the baseline regex extractor
    without attempting to load ML models. Also resets the singleton
    pipeline between tests.
    """
    monkeypatch.setenv("USE_MODEL_EXTRACTION", "false")

    # Reset the singleton pipeline before each test
    import extraction_service.pipeline as pipeline_module

    pipeline_module._PIPELINE = None

    yield

    # Reset again after test
    pipeline_module._PIPELINE = None


@pytest.fixture()
def sample_document_text() -> str:
    return "Inclusion: Age >= 18 years. Exclusion: Pregnant."
