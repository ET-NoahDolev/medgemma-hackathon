"""Document chunking utilities for long protocol text."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentChunk:
    """A chunk of document text with metadata."""

    text: str
    start_char: int
    end_char: int
    section_type: str | None
    page_hint: int | None


INCLUSION_HEADER = re.compile(
    r"(?:^|\n)\s*(?:inclusion\s*criteria|eligibility\s*criteria|include)\s*:?\s*(?:\n|$)",
    re.IGNORECASE | re.MULTILINE,
)
EXCLUSION_HEADER = re.compile(
    r"(?:^|\n)\s*(?:exclusion\s*criteria|ineligibility\s*criteria|exclude)\s*:?\s*(?:\n|$)",
    re.IGNORECASE | re.MULTILINE,
)


def _estimate_tokens(text: str) -> int:
    """Estimate token count using a simple character heuristic."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def detect_section_boundaries(text: str) -> list[tuple[int, str]]:
    """Find character positions of inclusion/exclusion section headers."""
    boundaries: list[tuple[int, str]] = []
    for match in INCLUSION_HEADER.finditer(text):
        boundaries.append((match.start(), "inclusion"))
    for match in EXCLUSION_HEADER.finditer(text):
        boundaries.append((match.start(), "exclusion"))
    return sorted(boundaries, key=lambda item: item[0])


def _split_paragraphs(text: str) -> list[tuple[int, int]]:
    """Return paragraph spans as (start, end) indices."""
    spans: list[tuple[int, int]] = []
    for match in re.finditer(r"(?:[^\n]|\n(?!\n))+", text):
        if match.group(0).strip():
            spans.append((match.start(), match.end()))
    return spans


def _overlap_start(text: str, end_char: int, overlap_tokens: int) -> int:
    """Find start index that yields roughly overlap_tokens from end_char."""
    if overlap_tokens <= 0:
        return end_char
    target_chars = overlap_tokens * 4
    return max(0, end_char - target_chars)


def _section_type_for_chunk(
    boundaries: list[tuple[int, str]], start_char: int
) -> str | None:
    current = None
    for pos, section in boundaries:
        if pos <= start_char:
            current = section
        else:
            break
    return current


def _page_hint_for_chunk(text: str, start_char: int) -> int | None:
    if "\f" not in text:
        return None
    return text.count("\f", 0, start_char) + 1


def chunk_document(
    text: str,
    max_tokens: int = 6000,
    overlap_tokens: int = 400,
    respect_sections: bool = True,
) -> list[DocumentChunk]:
    """Split document into overlapping chunks respecting section boundaries."""
    if not text.strip():
        return []

    boundaries = detect_section_boundaries(text) if respect_sections else []
    paragraph_spans = _split_paragraphs(text)

    chunks: list[DocumentChunk] = []
    current_start: int | None = None
    current_end: int | None = None

    for start, end in paragraph_spans:
        if current_start is None:
            current_start = start
            current_end = end
            continue

        candidate_text = text[current_start:end]
        if _estimate_tokens(candidate_text) <= max_tokens:
            current_end = end
            continue

        if current_end is None:
            continue
        chunk_text = text[current_start:current_end]
        section_type = _section_type_for_chunk(boundaries, current_start)
        page_hint = _page_hint_for_chunk(text, current_start)
        chunks.append(
            DocumentChunk(
                text=chunk_text,
                start_char=current_start,
                end_char=current_end,
                section_type=section_type,
                page_hint=page_hint,
            )
        )

        overlap_start = _overlap_start(text, current_end, overlap_tokens)
        current_start = min(overlap_start, start)
        current_end = end

    if current_start is not None and current_end is not None:
        chunk_text = text[current_start:current_end]
        section_type = _section_type_for_chunk(boundaries, current_start)
        page_hint = _page_hint_for_chunk(text, current_start)
        chunks.append(
            DocumentChunk(
                text=chunk_text,
                start_char=current_start,
                end_char=current_end,
                section_type=section_type,
                page_hint=page_hint,
            )
        )

    return chunks
