from __future__ import annotations

import pytest

from grounding_service import ubkg_client


@pytest.fixture()
def ubkg() -> ubkg_client.UbkgClient:
    return ubkg_client.UbkgClient()
