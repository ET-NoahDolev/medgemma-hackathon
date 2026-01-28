"""Download protocols and emit normalized records."""

import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from shared.models import Protocol


@dataclass
class ProtocolRecord:
    """Normalized protocol record for downstream services.

    Args:
        nct_id: ClinicalTrials.gov identifier.
        title: Trial title.
        condition: Primary condition or disease area.
        phase: Trial phase label.
        pdf_path: Local path to the protocol PDF.

    Examples:
        >>> ProtocolRecord(
        ...     nct_id="NCT00000000",
        ...     title="Example Trial",
        ...     condition="Melanoma",
        ...     phase="Phase 2",
        ...     pdf_path="/path/to/protocol.pdf",
        ... )
        ProtocolRecord(
        ...     nct_id='NCT00000000',
        ...     title='Example Trial',
        ...     condition='Melanoma',
        ...     phase='Phase 2',
        ...     pdf_path='/path/to/protocol.pdf',
        ... )

    Notes:
        This model represents the canonical ingestion output for the API service.
    """

    nct_id: str
    title: str
    condition: str
    phase: str
    pdf_path: str
    source: str | None = None
    registry_id: str | None = None
    registry_type: str | None = None
    source_url: str | None = None

    def to_protocol(self, protocol_id: str) -> Protocol:
        """Convert to shared Protocol model."""
        return Protocol(
            id=protocol_id,
            title=self.title,
            nct_id=self.nct_id,
            condition=self.condition,
            phase=self.phase,
            source=self.source,
            registry_id=self.registry_id,
            registry_type=self.registry_type,
        )

DEFAULT_MANIFEST_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "protocols" / "manifest.jsonl"
)

logger = logging.getLogger(__name__)


def _derive_title(path: Path) -> str:
    fallback = path.stem.replace("_", " ").replace("-", " ").strip()
    return fallback or "Protocol"


def _extract_registry_id(url: str) -> tuple[str | None, str | None]:
    nct_match = re.search(r"(NCT\d{8})", url)
    if nct_match:
        return nct_match.group(1), "nct"
    isrctn_match = re.search(r"(ISRCTN\d+)", url, flags=re.IGNORECASE)
    if isrctn_match:
        return isrctn_match.group(1).upper(), "isrctn"
    return None, None


def read_manifest_entries(manifest_path: Path) -> list[dict[str, object]]:
    """Read manifest entries from a JSONL file."""
    entries: list[dict[str, object]] = []
    with manifest_path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError as exc:
                    logger.warning(
                        "Skipping malformed manifest line: %s (%s)",
                        line[:200].rstrip(),
                        exc,
                    )
                    continue
                if isinstance(parsed, dict):
                    entries.append(parsed)
                else:
                    logger.warning(
                        "Skipping non-dict manifest entry: %r",
                        type(parsed),
                    )
    return entries


def _get_optional_str(entry: dict[str, object], key: str) -> str | None:
    value = entry.get(key)
    return value if isinstance(value, str) else None


def _build_record_from_entry(entry: dict[str, object]) -> ProtocolRecord | None:
    if _get_optional_str(entry, "status") != "downloaded":
        return None
    path_value = _get_optional_str(entry, "path")
    if not path_value:
        return None
    pdf_path = Path(path_value)
    if not pdf_path.exists():
        logger.warning("Missing PDF at %s", pdf_path)
        return None
    url = _get_optional_str(entry, "url") or ""
    title = _derive_title(pdf_path)
    registry_id = _get_optional_str(entry, "registry_id")
    registry_type = _get_optional_str(entry, "registry_type")
    if not registry_id or not registry_type:
        derived_id, derived_type = _extract_registry_id(url)
        registry_id = registry_id or derived_id
        registry_type = registry_type or derived_type
    return ProtocolRecord(
        nct_id=registry_id if registry_type == "nct" and registry_id else "",
        title=title,
        condition="",
        phase="",
        pdf_path=str(pdf_path),
        source=_get_optional_str(entry, "source"),
        registry_id=registry_id,
        registry_type=registry_type,
        source_url=url or None,
    )


def ingest_local_protocols(
    manifest_path: Path = DEFAULT_MANIFEST_PATH, limit: int = 50
) -> list[ProtocolRecord]:
    """Load protocol PDFs referenced in a manifest."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    records: list[ProtocolRecord] = []
    for entry in read_manifest_entries(manifest_path):
        if len(records) >= limit:
            break
        record = _build_record_from_entry(entry)
        if record is not None:
            records.append(record)
    return records


def emit_records(
    records: list[ProtocolRecord], output_path: Path | None = None
) -> None:
    """Write protocol records to JSONL file.

    Args:
        records: Protocol records to emit.
        output_path: Output file path. If None, prints to stdout.

    Returns:
        None.
    """
    lines = [json.dumps(asdict(record)) for record in records]

    if output_path:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("\n".join(lines) + "\n")
        except OSError as exc:
            message = f"Failed to write output to {output_path}: {exc}"
            raise RuntimeError(message) from exc
    else:
        for line in lines:
            print(line)


def main() -> None:
    """CLI entrypoint."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Ingest protocols from local PDFs using manifest.jsonl"
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path to manifest.jsonl for local ingestion",
    )
    parser.add_argument("--limit", type=int, default=50, help="Max records")
    parser.add_argument("--output", type=Path, help="Output JSONL path")
    args = parser.parse_args()

    records = ingest_local_protocols(args.manifest_path, args.limit)
    emit_records(records, args.output)
    print(f"Ingested {len(records)} protocols")


if __name__ == "__main__":
    main()
