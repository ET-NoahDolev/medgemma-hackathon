import pytest


@pytest.fixture()
def sample_document_text() -> str:
    return "Inclusion: Age >= 18 years. Exclusion: Pregnant."
