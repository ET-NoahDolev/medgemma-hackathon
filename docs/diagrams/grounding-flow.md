# Grounding Flow

```mermaid
flowchart LR
  criterion[CriterionText] --> ubkg[UBKGSearch]
  ubkg --> candidates[SNOMEDCandidates]
  candidates --> rank[ModelRanking]
  rank --> review[HITLReview]
  criterion --> fieldmap[FieldRelationValueMapping]
  fieldmap --> review
```
