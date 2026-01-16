from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api_service.main import _reset_state, app


@pytest.fixture()
def client() -> TestClient:
    _reset_state()
    return TestClient(app)
