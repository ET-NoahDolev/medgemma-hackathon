"""Shared data models for API and UI."""

from dataclasses import dataclass
from typing import List


@dataclass
class Criterion:
    id: str
    text: str
    criterion_type: str
    confidence: float
    snomed_codes: List[str]
