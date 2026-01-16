from __future__ import annotations

import pytest

from data_pipeline import download_protocols


@pytest.fixture()
def sample_record() -> download_protocols.ProtocolRecord:
    return download_protocols.ProtocolRecord(
        nct_id="NCT00000000",
        title="Example Trial",
        condition="Melanoma",
        phase="Phase 2",
        document_text="Inclusion: Age >= 18.",
    )
