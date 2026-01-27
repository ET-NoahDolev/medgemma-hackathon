"""Semantic chunking utilities for protocol text."""

from __future__ import annotations

import re
from dataclasses import dataclass

_PAGE_SEPARATOR = "\f"
_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n+")


@dataclass(frozen=True)
class Page:
    """A page-sized chunk of document text."""

    text: str
    page_number: int


@dataclass(frozen=True)
class Paragraph:
    """A paragraph within a page."""

    text: str
    page_number: int
    paragraph_index: int


def split_into_pages(text: str, max_chars: int = 4000) -> list[Page]:
    """Split document into page-sized chunks.

    Uses form-feed characters if present, but sub-splits any pages that exceed
    max_chars. Falls back to paragraph-based chunking if no form-feeds exist.
    """
    if not text.strip():
        return []

    if _PAGE_SEPARATOR in text:
        raw_pages = [
            page.strip() for page in text.split(_PAGE_SEPARATOR) if page.strip()
        ]
        pages: list[Page] = []
        page_number = 1
        for raw_page in raw_pages:
            if len(raw_page) <= max_chars:
                pages.append(Page(text=raw_page, page_number=page_number))
                page_number += 1
            else:
                # Sub-split oversized pages using paragraph-based chunking
                sub_pages = _split_text_by_paragraphs(raw_page, max_chars, page_number)
                pages.extend(sub_pages)
                page_number += len(sub_pages)
        return pages

    return _split_text_by_paragraphs(text, max_chars, start_page=1)


def _split_text_by_paragraphs(
    text: str, max_chars: int, start_page: int = 1
) -> list[Page]:
    """Split text into pages based on paragraph boundaries.

    Args:
        text: Text to split.
        max_chars: Maximum characters per page.
        start_page: Starting page number.

    Returns:
        List of Page objects.
    """
    paragraphs = _split_paragraph_text(text)
    pages: list[Page] = []
    current_parts: list[str] = []
    current_len = 0
    page_number = start_page

    for paragraph in paragraphs:
        # If a single paragraph is too long, split it further
        if len(paragraph) > max_chars:
            # Flush current parts first
            if current_parts:
                pages.append(
                    Page(
                        text="\n\n".join(current_parts).strip(), page_number=page_number
                    )
                )
                page_number += 1
                current_parts = []
                current_len = 0

            # Split the long paragraph by single newlines or at max_chars
            sub_chunks = _split_long_paragraph(paragraph, max_chars)
            for chunk in sub_chunks:
                pages.append(Page(text=chunk.strip(), page_number=page_number))
                page_number += 1
            continue

        paragraph_len = len(paragraph)
        if current_parts and current_len + paragraph_len + 2 > max_chars:
            pages.append(
                Page(text="\n\n".join(current_parts).strip(), page_number=page_number)
            )
            page_number += 1
            current_parts = [paragraph]
            current_len = paragraph_len
            continue

        if current_parts:
            current_len += 2  # account for paragraph separator
        current_parts.append(paragraph)
        current_len += paragraph_len

    if current_parts:
        pages.append(
            Page(text="\n\n".join(current_parts).strip(), page_number=page_number)
        )

    return pages


def _split_long_paragraph(text: str, max_chars: int) -> list[str]:
    """Split a long paragraph into smaller chunks.

    First tries to split on single newlines, then falls back to
    splitting at sentence boundaries, and finally at character boundaries.

    Args:
        text: Long paragraph text.
        max_chars: Maximum characters per chunk.

    Returns:
        List of text chunks.
    """
    # Try splitting on single newlines first
    lines = text.split("\n")
    if len(lines) > 1:
        chunks = _merge_lines_into_chunks(lines, max_chars)
        # If we got meaningful chunks, return them
        if len(chunks) > 1 or (chunks and len(chunks[0]) <= max_chars):
            return chunks

    # Fall back to splitting at approximately max_chars boundaries
    return _split_at_sentence_boundaries(text, max_chars)


def _merge_lines_into_chunks(lines: list[str], max_chars: int) -> list[str]:
    """Merge lines into chunks respecting max_chars limit."""
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_len = 0

    for line in lines:
        line_len = len(line)
        if current_chunk and current_len + line_len + 1 > max_chars:
            chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_len = line_len
        else:
            if current_chunk:
                current_len += 1  # newline separator
            current_chunk.append(line)
            current_len += line_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


def _split_at_sentence_boundaries(text: str, max_chars: int) -> list[str]:
    """Split text at sentence boundaries, falling back to char boundaries."""
    chunks: list[str] = []
    remaining = text

    while len(remaining) > max_chars:
        split_point = _find_sentence_boundary(remaining, max_chars)
        chunks.append(remaining[:split_point].strip())
        remaining = remaining[split_point:].strip()

    if remaining:
        chunks.append(remaining)

    return chunks


def _find_sentence_boundary(text: str, max_chars: int) -> int:
    """Find the best split point near max_chars."""
    for boundary in [".\n", ". ", "?\n", "? ", "\n"]:
        last_boundary = text[:max_chars].rfind(boundary)
        if last_boundary > max_chars // 2:  # Only use if reasonably far in
            return last_boundary + len(boundary)
    return max_chars


def split_into_paragraphs(page: Page) -> list[Paragraph]:
    """Split a page into paragraphs."""
    paragraphs = _split_paragraph_text(page.text)
    return [
        Paragraph(
            text=paragraph.strip(),
            page_number=page.page_number,
            paragraph_index=index,
        )
        for index, paragraph in enumerate(paragraphs)
        if paragraph.strip()
    ]


def _split_paragraph_text(text: str) -> list[str]:
    paragraphs = [
        chunk.strip()
        for chunk in _PARAGRAPH_SPLIT_RE.split(text)
        if chunk.strip()
    ]
    if paragraphs:
        return paragraphs
    if text.strip():
        return [text.strip()]
    return []
