# MedGemma Hackathon

This repository hosts the MedGemma hackathon demo for extracting atomic inclusion/exclusion criteria from clinical trial protocols, grounding them to SNOMED via UBKG, mapping field/relation/value for screening, and enabling a human-in-the-loop (HITL) review experience.

## Quick Links

- Overview: `docs/overview/project.md`
- Architecture: `docs/overview/architecture.md`
- Getting Started: `docs/overview/getting-started.md`
- Hackathon Plan: `docs/overview/hackathon-plan.md`
- API Spec: `docs/api/api_spec.md`
- Components: `docs/components-overview.md`

## Demo Goals

- Extract atomic criteria with evidence snippets.
- Ground criteria to SNOMED with ranked candidates and confidence.
- Map criteria to field/relation/value (e.g., `demographics.age > 75`).
- Provide a HITL UI for nurse review and corrections.
- Capture edits for training and evaluation.

## Repo Layout

```
components/     Service components (API, extraction, grounding, UI, etc.)
docs/           MkDocs documentation
scripts/        Utility scripts (protocol download, component creation, etc.)
instructions/   Planning documents
```

## Scripts

The `scripts/` directory contains utility scripts for common tasks:

- **Protocol Download**: `scripts/download_protocol_sources.py` - Downloads clinical trial protocol PDFs from multiple sources (DAC, ClinicalTrials.gov, BMJ Open, JMIR)
- **Component Creation**: `scripts/create_component.sh` - Initializes new components with proper structure
- **Documentation**: `scripts/generate_components_overview.py` and `scripts/update_root_navigation.py` - Auto-generate documentation

See [Getting Started](overview/getting-started.md#scripts) for detailed usage instructions.
