from __future__ import annotations

import pytest

from shared import models


@pytest.fixture()
def sample_criterion() -> models.Criterion:
    return models.build_criterion()


@pytest.fixture()
def sample_protocol() -> models.Protocol:
    return models.build_protocol()
