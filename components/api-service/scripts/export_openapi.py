"""Export the FastAPI OpenAPI spec to the docs folder."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

if "grounding_service" not in sys.modules:
    grounding_service = types.ModuleType("grounding_service")
    umls_client = types.ModuleType("grounding_service.umls_client")

    class _UmlsClient:
        def search_snomed(self, _text: str) -> list[object]:
            return []

    def _propose_field_mapping(_text: str) -> list[object]:
        return []

    setattr(umls_client, "UmlsClient", _UmlsClient)
    setattr(umls_client, "propose_field_mapping", _propose_field_mapping)
    setattr(grounding_service, "umls_client", umls_client)
    sys.modules["grounding_service"] = grounding_service
    sys.modules["grounding_service.umls_client"] = umls_client

from api_service.main import app  # noqa: E402


def main() -> None:
    """Write the app OpenAPI spec to the docs folder."""
    spec = app.openapi()
    output_path = Path(__file__).resolve().parents[3] / "docs" / "api" / "api_spec.yaml"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(spec, sort_keys=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
