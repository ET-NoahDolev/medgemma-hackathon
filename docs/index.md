# MedGemma Hackathon

This repository hosts the MedGemma hackathon demo for extracting atomic inclusion/exclusion criteria from clinical trial protocols, grounding them to SNOMED via UBKG, and enabling a human-in-the-loop (HITL) review experience.

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
- Provide a HITL UI for nurse review and corrections.
- Capture edits for training and evaluation.

## Repo Layout

```
components/     Service components (API, extraction, grounding, UI, etc.)
docs/           MkDocs documentation
scripts/        Build and utility scripts
instructions/   Planning documents
```
