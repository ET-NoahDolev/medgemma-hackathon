"""Load protocols into the API database from PDFs or manifests."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import cast

import httpx

from data_pipeline.download_protocols import (
    DEFAULT_MANIFEST_PATH,
    ProtocolRecord,
    ingest_local_protocols,
)

logger = logging.getLogger(__name__)


def _derive_title(path: Path) -> str:
    fallback = path.stem.replace("_", " ").replace("-", " ").strip()
    return fallback or "Protocol"


def load_single_protocol(
    pdf_path: Path,
    api_url: str,
    auto_extract: bool = True,
) -> str:
    """Load a single PDF protocol into the database via the API.

    Args:
        pdf_path: Path to a protocol PDF file.
        api_url: API base URL (e.g., http://localhost:8000).
        auto_extract: Trigger criteria extraction after creating the protocol.

    Returns:
        The created protocol_id.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    title = _derive_title(pdf_path)
    with pdf_path.open("rb") as handle:
        response = httpx.post(
            f"{api_url.rstrip('/')}/v1/protocols/upload",
            params={"auto_extract": str(auto_extract).lower()},
            files={"file": (pdf_path.name, handle, "application/pdf")},
            timeout=60.0,
        )
    response.raise_for_status()
    payload = cast(dict[str, str], response.json())
    protocol_id = payload["protocol_id"]

    return protocol_id


def bulk_load_protocols(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    api_url: str = "http://localhost:8000",
    limit: int = 50,
    auto_extract: bool = False,
) -> list[str]:
    """Bulk load protocols from a manifest into the database.

    Args:
        manifest_path: Manifest JSONL containing downloaded PDFs.
        api_url: API base URL.
        limit: Max number of records to load.
        auto_extract: Trigger extraction for each protocol after creation.

    Returns:
        List of created protocol IDs.
    """
    records = ingest_local_protocols(manifest_path, limit=limit)
    protocol_ids: list[str] = []

    for record in records:
        pdf_path = Path(record.pdf_path)
        with pdf_path.open("rb") as handle:
            response = httpx.post(
                f"{api_url.rstrip('/')}/v1/protocols/upload",
                params={"auto_extract": str(auto_extract).lower()},
                files={"file": (pdf_path.name, handle, "application/pdf")},
                timeout=60.0,
            )
        if response.status_code != 200:
            logger.warning(
                "Failed to create protocol %s (%s)",
                record.title,
                response.text,
            )
            continue
        payload = cast(dict[str, str], response.json())
        protocol_id = payload["protocol_id"]
        protocol_ids.append(protocol_id)

    return protocol_ids


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load protocols into API database")
    parser.add_argument("--pdf", type=Path, help="Single PDF to load")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Manifest for bulk load",
    )
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--no-extract", action="store_true")
    return parser


def main() -> None:
    """CLI entrypoint."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.pdf:
        protocol_id = load_single_protocol(
            args.pdf,
            args.api_url,
            auto_extract=not args.no_extract,
        )
        print(f"Loaded protocol: {protocol_id}")
        return

    protocol_ids = bulk_load_protocols(
        manifest_path=args.manifest,
        api_url=args.api_url,
        limit=args.limit,
        auto_extract=not args.no_extract,
    )
    print(f"Loaded {len(protocol_ids)} protocols")


if __name__ == "__main__":
    main()
