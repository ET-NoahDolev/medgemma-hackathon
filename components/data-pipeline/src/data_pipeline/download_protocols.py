"""Download protocols and emit normalized records."""

import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List

import httpx
from pypdf import PdfReader


@dataclass
class ProtocolRecord:
    """Normalized protocol record for downstream services.

    Args:
        nct_id: ClinicalTrials.gov identifier.
        title: Trial title.
        condition: Primary condition or disease area.
        phase: Trial phase label.
        document_text: Extracted protocol text for NLP processing.

    Examples:
        >>> ProtocolRecord(
        ...     nct_id="NCT00000000",
        ...     title="Example Trial",
        ...     condition="Melanoma",
        ...     phase="Phase 2",
        ...     document_text="Inclusion: Age >= 18.",
        ... )
        ProtocolRecord(
        ...     nct_id='NCT00000000',
        ...     title='Example Trial',
        ...     condition='Melanoma',
        ...     phase='Phase 2',
        ...     document_text='Inclusion: Age >= 18.',
        ... )

    Notes:
        This model represents the canonical ingestion output for the API service.
    """

    nct_id: str
    title: str
    condition: str
    phase: str
    document_text: str
    source: str | None = None


CT_API_BASE = "https://clinicaltrials.gov/api/v2/studies"
DEFAULT_MANIFEST_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "protocols" / "manifest.jsonl"
)

logger = logging.getLogger(__name__)


def fetch_from_clinicaltrials(query: str, limit: int = 50) -> List[ProtocolRecord]:
    """Fetch protocols from ClinicalTrials.gov API v2.

    Args:
        query: Condition or keyword to search.
        limit: Maximum records to fetch.

    Returns:
        List of normalized protocol records.

    Raises:
        ValueError: If limit is not positive.
    """
    if limit <= 0:
        raise ValueError("limit must be positive")

    page_size = min(limit, 100)
    params: dict[str, str | int] = {
        "query.cond": query,
        "fields": "NCTId|BriefTitle|Condition|Phase|EligibilityModule",
        "pageSize": page_size,
        "format": "json",
    }

    records: List[ProtocolRecord] = []
    next_token: str | None = None
    while len(records) < limit:
        if next_token:
            params["pageToken"] = next_token
        else:
            params.pop("pageToken", None)

        resp = httpx.get(CT_API_BASE, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()

        for study in payload.get("studies", []):
            proto = study.get("protocolSection", {})
            ident = proto.get("identificationModule", {})
            conds = proto.get("conditionsModule", {})
            design = proto.get("designModule", {})
            elig = proto.get("eligibilityModule", {})

            records.append(
                ProtocolRecord(
                    nct_id=ident.get("nctId", ""),
                    title=ident.get("briefTitle", ""),
                    condition=(conds.get("conditions") or [""])[0],
                    phase=(design.get("phases") or [""])[0],
                    document_text=elig.get("eligibilityCriteria", ""),
                )
            )
            if len(records) >= limit:
                break

        next_token = payload.get("nextPageToken")
        if not next_token:
            break

    return records


def extract_text_from_pdf(path: Path) -> str:
    """Extract text from a PDF file using pypdf."""
    reader = PdfReader(str(path))
    chunks: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text:
            chunks.append(page_text)
    return "\n".join(chunks).strip()


def _derive_title(path: Path, text: str) -> str:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if first_line and len(first_line) >= 5:
        return first_line[:200]
    fallback = path.stem.replace("_", " ").replace("-", " ").strip()
    return fallback or "Protocol"


def _extract_nct_id(url: str) -> str:
    match = re.search(r"/(NCT\d{8})/", url)
    return match.group(1) if match else ""


def ingest_local_protocols(
    manifest_path: Path = DEFAULT_MANIFEST_PATH, limit: int = 50
) -> List[ProtocolRecord]:
    """Load protocol PDFs referenced in a manifest and extract document text."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    records: list[ProtocolRecord] = []
    with manifest_path.open(encoding="utf-8") as handle:
        for line in handle:
            if len(records) >= limit:
                break
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("status") != "downloaded":
                continue
            path_value = entry.get("path")
            if not path_value:
                continue
            pdf_path = Path(path_value)
            if not pdf_path.exists():
                logger.warning("Missing PDF at %s", pdf_path)
                continue
            try:
                text = extract_text_from_pdf(pdf_path)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to read %s: %s", pdf_path, exc)
                continue
            if not text:
                logger.warning("Empty text extracted from %s", pdf_path)
                continue

            url = entry.get("url", "")
            title = _derive_title(pdf_path, text)
            records.append(
                ProtocolRecord(
                    nct_id=_extract_nct_id(url),
                    title=title,
                    condition="",
                    phase="",
                    document_text=text,
                    source=entry.get("source"),
                )
            )
    return records


def emit_records(
    records: List[ProtocolRecord], output_path: Path | None = None
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
            raise RuntimeError(f"Failed to write output to {output_path}: {exc}") from exc
    else:
        for line in lines:
            print(line)

def main() -> None:
    """CLI entrypoint."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Download protocols from ClinicalTrials.gov or local PDFs"
    )
    parser.add_argument("--query", default="oncology", help="Search condition")
    parser.add_argument("--limit", type=int, default=50, help="Max records")
    parser.add_argument(
        "--local",
        action="store_true",
        help="Ingest protocols from local PDFs using the manifest.jsonl",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path to manifest.jsonl for local ingestion",
    )
    parser.add_argument("--output", type=Path, help="Output JSONL path")
    args = parser.parse_args()

    if args.local:
        records = ingest_local_protocols(args.manifest_path, args.limit)
    else:
        records = fetch_from_clinicaltrials(args.query, args.limit)
    emit_records(records, args.output)
    print(f"Downloaded {len(records)} protocols")


if __name__ == "__main__":
    main()
