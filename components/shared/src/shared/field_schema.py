"""Semantic type to field category mapping for UMLS concepts."""

SEMANTIC_TYPE_MAPPING: dict[str, dict[str, str]] = {
    "T032": {"name": "Organism Attribute", "field_category": "demographics"},
    "T034": {"name": "Laboratory or Test Result", "field_category": "labs"},
    "T081": {"name": "Quantitative Concept", "field_category": "vitals"},
    "T201": {"name": "Clinical Attribute", "field_category": "performance"},
    "T033": {"name": "Finding", "field_category": "conditions"},
    "T184": {"name": "Sign or Symptom", "field_category": "conditions"},
    "T047": {"name": "Disease or Syndrome", "field_category": "diagnosis"},
}
