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

    Uses form-feed characters if present; otherwise groups paragraphs into
    roughly max_chars pages.
    """
    if not text.strip():
        return []

    if _PAGE_SEPARATOR in text:
        raw_pages = [page for page in text.split(_PAGE_SEPARATOR) if page.strip()]
        return [
            Page(text=page.strip(), page_number=index + 1)
            for index, page in enumerate(raw_pages)
        ]

    paragraphs = _split_paragraph_text(text)
    pages: list[Page] = []
    current_parts: list[str] = []
    current_len = 0
    page_number = 1

    for paragraph in paragraphs:
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
