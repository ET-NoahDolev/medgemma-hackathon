"""Computed field registry for grounded criteria."""

from __future__ import annotations

from typing import Any

COMPUTED_FIELDS: dict[str, dict[str, Any]] = {
    "age": {
        "source_concept": "Date of birth",
        "source_umls_id": "C0011002",
        "computation": "today() - date_of_birth",
        "output_unit": "years",
    },
    "bmi": {
        "source_concepts": ["body weight", "body height"],
        "computation": "weight_kg / (height_m ** 2)",
        "output_unit": "kg/m2",
    },
}


def detect_computed_field(entity: str) -> dict[str, Any] | None:
    """Return computed field metadata for a normalized entity name.

    Args:
        entity: Normalized entity name (e.g., "age", "bmi").

    Returns:
        Computed field metadata if entity is known, otherwise None.
    """
    key = entity.strip().lower()
    return COMPUTED_FIELDS.get(key)
