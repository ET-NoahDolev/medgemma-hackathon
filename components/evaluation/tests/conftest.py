from __future__ import annotations

import pytest


@pytest.fixture()
def sample_actions() -> list[str]:
    return ["accept", "reject", "accept"]
