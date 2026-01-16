"""Extraction pipeline stubs for MedGemma Task A."""

from dataclasses import dataclass
from typing import List


@dataclass
class Criterion:
    text: str
    criterion_type: str
    confidence: float


def extract_criteria(document_text: str) -> List[Criterion]:
    """Extract atomic inclusion/exclusion criteria from protocol text."""
    return []
