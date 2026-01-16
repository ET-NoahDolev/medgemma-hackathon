# Project Overview

The MedGemma hackathon demo focuses on protocol ingestion, criteria extraction, UBKG grounding, field/relation/value mapping, and HITL review. The objective is to reduce nurse review time while preserving transparency and provenance.

## Scope

- Protocol ingestion and parsing.
- Criteria extraction and classification.
- SNOMED grounding via UBKG.
- Field/relation/value mapping for EMR screening.
- HITL UI for review and corrections.
- Minimal evaluation metrics.

## Success Criteria

- Extraction F1 >= 0.85.
- SNOMED Top-1 accuracy >= 0.80.
- Field/relation/value mapping quality tracked (target TBD).
- Nurse acceptance rate >= 70%.
- Time per protocol reduction >= 60% vs manual.

## Deliverables

- End-to-end demo (protocol -> extraction -> grounding + field mapping -> HITL edits).
- API spec and component documentation.
- Training and evaluation notebook.
- 3-5 minute demo video.

## Out of Scope (Post-Hackathon)

- EMR/FHIR integration.
- Multi-site federated learning.
- Patient-level screening and matching.
