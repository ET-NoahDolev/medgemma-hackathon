"""Download ClinicalTrials.gov protocols and emit normalized records."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List

import httpx


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


CT_API_BASE = "https://clinicaltrials.gov/api/v2/studies"


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

    params = {
        "query.cond": query,
        "fields": "NCTId|BriefTitle|Condition|Phase|EligibilityModule",
        "pageSize": min(limit, 100),
        "format": "json",
    }

    resp = httpx.get(CT_API_BASE, params=params, timeout=30)
    resp.raise_for_status()

    records: List[ProtocolRecord] = []
    for study in resp.json().get("studies", []):
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

    return records[:limit]


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
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines) + "\n")
    else:
        for line in lines:
            print(line)

def main() -> None:
    """CLI entrypoint."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Download protocols from ClinicalTrials.gov"
    )
    parser.add_argument("--query", default="oncology", help="Search condition")
    parser.add_argument("--limit", type=int, default=50, help="Max records")
    parser.add_argument("--output", type=Path, help="Output JSONL path")
    args = parser.parse_args()

    records = fetch_from_clinicaltrials(args.query, args.limit)
    emit_records(records, args.output)
    print(f"Downloaded {len(records)} protocols")


if __name__ == "__main__":
    main()
