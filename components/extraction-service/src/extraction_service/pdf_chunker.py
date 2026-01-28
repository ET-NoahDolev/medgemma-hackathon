"""PDF chunking utilities for large documents."""

from __future__ import annotations

import os
from dataclasses import dataclass

import fitz  # PyMuPDF


@dataclass(frozen=True)
class PDFChunk:
    """A chunked slice of a PDF document."""

    data: bytes
    chunk_index: int
    total_chunks: int
    page_start: int
    page_end: int


def _read_bool_env(name: str, default: bool) -> bool:
    """Read a boolean environment variable."""
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    return value in {"1", "true", "yes", "y"}


def _read_int_env(name: str, default: int) -> int:
    """Read an integer environment variable."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def is_chunking_enabled() -> bool:
    """Return True if PDF chunking is enabled."""
    return _read_bool_env("ENABLE_PDF_CHUNKING", False)


def should_chunk_pdf(pdf_bytes: bytes) -> bool:
    """Determine if a PDF needs to be split into chunks.

    Returns:
        True if chunking is enabled and thresholds are exceeded.
    """
    if not is_chunking_enabled():
        return False
    max_bytes = _read_int_env("PDF_CHUNK_MAX_BYTES", 10 * 1024 * 1024)
    max_pages = _read_int_env("PDF_CHUNK_MAX_PAGES", 50)
    if len(pdf_bytes) > max_bytes:
        return True
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_count = doc.page_count
    doc.close()
    return page_count > max_pages


def chunk_pdf(pdf_bytes: bytes) -> list[PDFChunk]:
    """Split a PDF into smaller chunks by page ranges.

    Args:
        pdf_bytes: Original PDF as bytes.

    Returns:
        List of PDFChunk objects, each containing a valid PDF.
    """
    max_pages = _read_int_env("PDF_CHUNK_MAX_PAGES", 50)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = doc.page_count

    if not is_chunking_enabled() or total_pages <= max_pages:
        doc.close()
        return [
            PDFChunk(
                data=pdf_bytes,
                chunk_index=0,
                total_chunks=1,
                page_start=0,
                page_end=max(total_pages - 1, 0),
            )
        ]

    total_chunks = (total_pages + max_pages - 1) // max_pages
    chunks: list[PDFChunk] = []
    for chunk_index, start in enumerate(range(0, total_pages, max_pages)):
        end = min(start + max_pages - 1, total_pages - 1)
        new_doc = fitz.open()
        new_doc.insert_pdf(doc, from_page=start, to_page=end)
        chunks.append(
            PDFChunk(
                data=new_doc.tobytes(),
                chunk_index=chunk_index,
                total_chunks=total_chunks,
                page_start=start,
                page_end=end,
            )
        )
        new_doc.close()

    doc.close()
    return chunks
