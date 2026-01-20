from __future__ import annotations

import pytest

from grounding_service import umls_client


@pytest.fixture()
def umls() -> umls_client.UmlsClient:
    return umls_client.UmlsClient(api_key="test-key")
