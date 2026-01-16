# MedGemma Hackathon – Concise Operational Plan

**Goal:** Deliver a hackathon‑ready MedGemma HITL demo that extracts atomic inclusion/exclusion criteria from trial protocols, grounds them to SNOMED via UBKG, and maps criteria to field/relation/value (e.g., `demographics.age > 75`), with a clear ElixirTrials integration story.

## 1. Project Brief

### 1.1 Problem & Impact
- Clinical trial protocols are unstructured; screening is slow and error‑prone.
- We build an AI‑assisted system that:
  - Extracts **atomic inclusion/exclusion criteria** from protocols.
  - Maps them to **SNOMED** (via UBKG REST API).
  - Maps criteria to **field + relation + value** for EMR screening (e.g., `demographics.age > 75`).
  - Lets a **nurse reviewer** correct mappings through a simple HITL UI.
- Target **time savings:** ~65–70% nurse time per protocol vs. manual review.  

### 1.2 Success Criteria (Hackathon)

**Judging‑aligned:**
1. **Human‑Centered AI**
   - Simple, transparent HITL UI.
   - Shows provenance (evidence snippets) + confidence scores.
   - Nurse can accept/edit SNOMED codes and field/relation/value mappings inline.

2. **Technical Rigor**
   - MedGemma 1.5–4B‑IT with LoRA adapters for:
     - Task A: Criteria extraction.
    - Task B: SNOMED grounding + field/relation/value mapping.
   - 8‑bit quantized inference on DGX Spark‑class hardware.

3. **Impact & Feasibility**
   - Measured **extraction F1** and **SNOMED Top‑1 accuracy**.
   - Measured **time per protocol**: baseline vs AI‑assisted.
   - Clear story to plug into ElixirTrials/Cauldron.

**Quantitative Targets (Hackathon):**
- Extraction F1: **≥ 0.85**
- SNOMED Top‑1 accuracy: **≥ 0.80**
- Nurse acceptance rate: **≥ 70%**
- Time per protocol: **≥ 60% reduction** vs manual.

---

## 2. Scope

### 2.1 In Scope (Hackathon)

- Ingest **public ClinicalTrials.gov protocols** (200–300).
- Extract **atomic inclusion/exclusion criteria**.
- Ground criteria to **SNOMED** via UBKG REST API (no external dependencies beyond public APIs).
- Map criteria to **field + relation + value** for EMR screening (field‑value mapping).
- **HITL backend**:
  - Save criteria, suggested codes, and nurse edits.
  - Simple review UI (Gradio or minimal React view).
- LoRA fine‑tuning of MedGemma on nurse‑validated labels.
- 8‑bit quantized inference on DGX Spark‑class workstation.
- Kaggle deliverables:
  - Writeup.
  - Training/eval notebook.
  - GitHub repo.
  - 3–5 min video demo.

### 2.2 Out of Scope (Post‑Hackathon Only)

- Federated learning / multi‑site aggregation.
- EMR / FHIR / Redox integration.
- Patient‑level screening & matching.
- Full Triplane/Screening integration.

---

## 3. Architecture (High‑Level)

### 3.1 Data Flow

1. **Protocol Upload**
   - Input: PDF/text from ClinicalTrials.gov.
   - Stored as `protocol` and `document` rows.

2. **Extraction**
   - Endpoint: `POST /v1/protocols/{id}/extract`
   - Uses MedGemma (LoRA Task A) → atomic criteria + type.

3. **Grounding**
   - Endpoint: `POST /v1/criteria/{id}/ground`
   - UBKG REST API (terminology lookup) + MedGemma (LoRA Task B) → ranked SNOMED codes + field/relation/value mapping.

4. **HITL Review**
   - Nurse UI fetches:
     - Criteria list.
     - Suggested SNOMED codes + confidence + evidence snippets.
     - Suggested field/relation/value mapping (e.g., `demographics.age > 75`).
   - Nurse edits logged in `hitl_edits`.

5. **Retraining Loop (Single‑site)**
   - Export edits as new training data.
   - Periodic LoRA re‑training of MedGemma adapters.

### 3.2 Minimal API Contract (Hackathon)

Base URL: `/v1`

- `POST /v1/protocols`
  - Create protocol metadata + initial document (text or PDF).
- `POST /v1/protocols/{protocolId}/extract`
  - Trigger criteria extraction (sync is enough).
- `GET /v1/protocols/{protocolId}/criteria`
  - List criteria for review.
- `PATCH /v1/criteria/{criterionId}`
  - Edit criterion text/type/etc.
- `POST /v1/criteria/{criterionId}/ground`
  - Get SNOMED candidates via UBKG REST API + field/relation/value mapping.
- `POST /v1/hitl/feedback`
  - Log nurse actions (accept/remove/add code etc).

(Full OpenAPI spec lives in `docs/api_spec.yaml`.)

### 3.3 Core Components

| Component         | Tech / Notes                          |
|------------------|----------------------------------------|
| Backend API      | FastAPI (Python)                      |
| Model Inference  | MedGemma 1.5–4B‑IT + LoRA (8‑bit)     |
| Terminology      | UBKG REST API (no custom wrapper)     |
| DB               | PostgreSQL (protocols, criteria, edits) |
| HITL UI          | Gradio or minimal Cauldron‑style view |
| Hardware         | DGX Spark‑class GPU workstation       |

### 3.4 UBKG Integration

**Why UBKG:**
- Pre‑built, production‑grade knowledge graph combining UMLS + external ontologies.
- REST API + Neo4j options.
- Zero licensing overhead for hackathon (public/research access).
- Multi‑terminology support (SNOMED, LOINC, RxNorm, ICD‑10) built‑in.

**Usage Pattern:**
```python
# Lookup term in UBKG
POST https://ubkg-api.xconsortia.org/search
{
  "query": "stage III melanoma",
  "ontology": "SNOMED",
  "limit": 5
}

# Response includes SNOMED codes + definitions + related terms
{
  "results": [
    {
      "code": "372244006",
      "display": "Malignant melanoma, stage III",
      "ontology": "SNOMED CT",
      "confidence": 0.92
    }
  ]
}
```

**Implementation:**
- Simple HTTP client in `backend/ubkg_client.py`.
- Optional local caching (Redis or in‑memory) for frequent lookups.
- Fallback to pre‑cached SNOMED subset if API unavailable.

---

## 4. Sprints & Daily Execution

### 4.1 Week 1 – Data & UBKG Integration (Jan 15–21)

**Goals:**
- Have protocols in DB.
- UBKG API client working + cached.
- Minimal extraction pipeline running (base model).

**Tasks:**

- **Data & DB**
  - Implement `scripts/download_protocols.py` to fetch 200–300 oncology/cardio trials from ClinicalTrials.gov.
  - Store `{nct_id, title, i/e text, condition, phase}` in PostgreSQL.
  - Define DB schema:
    - `protocols`, `documents`, `criteria`, `groundings`, `hitl_edits`.

- **UBKG Integration**
  - Implement `backend/ubkg_client.py`:
    - HTTP client to UBKG REST API.
    - Query term → get SNOMED candidates.
    - Simple in‑memory cache (TTL configurable).
    - Fallback: load local SNOMED subset (CSV from UBKG downloads).
  - CLI smoke test: terms like "stage III melanoma", "ECOG PS 0–1".

- **Baseline Extraction**
  - Implement rough parsing of I/E sections into candidate criteria (regex/sentence splitting).
  - Run base MedGemma (no LoRA) for:
    - Type classification (inclusion/exclusion).
    - Draft SNOMED suggestions via UBKG.
    - Draft field/relation/value mapping suggestions.

**Decision / Risk:**
- By **end of Week 1**:
  - If UBKG API rate limits hit → use local SNOMED subset file only.

---

### 4.2 Week 2 – HITL & Labeling (Jan 22–28)

**Goals:**
- Usable HITL UI for nurse.
- ~1,000 labeled examples for training.

**Tasks:**

- **HITL UI (MVP)**
  - Build simple UI (Gradio or minimal React) with:
    - Protocol text on left, highlighted criterion.
    - Criterion card on right:
      - Type, text, confidence.
      - SNOMED candidates with checkboxes.
      - Field/relation/value mapping preview + edits.
      - Add/remove code, rationale.
  - Wire to backend:
    - `GET /protocols/{id}/criteria`
    - `POST /criteria/{id}/ground`
    - `POST /hitl/feedback`.

- **Annotation Workflow**
  - Pre‑label criteria using base MedGemma + UBKG:
    - Save as `criteria_prelabeled.jsonl`.
  - Define gold label schema (criterion text, type, SNOMED codes, field/relation/value, evidence spans).
  - Target: **~1,000 validated criteria** (spanning ~120 protocols).
  - Coordinate nurse schedule (~200h total across hackathon).

- **Dataset Preparation**
  - Create train/val/test splits:
    - Train: 1,000 examples (~120 protocols).
    - Val: 100 examples (~15 protocols).
    - Test: 100 examples (held‑out conditions).

**Decision / Risk:**
- If by end of Week 2:
  - <700 labeled examples → reduce model ambition (e.g., only Task B LoRA) and focus on demo quality.

---

### 4.3 Week 3 – Training & Backend (Jan 29–Feb 4)

**Goals:**
- LoRA adapters trained and deployed.
- Backend API stable.
- Basic metrics computed.

**Tasks:**

- **Model Training**
  - Task A (Extraction):
    - LoRA config: `r=16`, `alpha=32`, target `q_proj/v_proj/o_proj`.
    - 3 epochs, batch size 4 (grad accum 4), lr `2e‑4`.
  - Task B (Grounding):
    - Separate LoRA adapter, same config.
    - Training data from nurse‑validated mapping + UBKG candidates.
  - Use 8‑bit QLoRA on DGX Spark; save adapters in `models/`.

- **Backend Hardening**
  - Implement final versions of:
    - `POST /protocols`
    - `POST /protocols/{id}/extract`
    - `GET /protocols/{id}/criteria`
    - `PATCH /criteria/{id}`
    - `POST /criteria/{id}/ground`
    - `POST /hitl/feedback`
  - Add logging & basic error handling.
  - Add minimal tests (Pytest) for core API paths.

- **Evaluation**
  - Run on test set:
    - Extraction F1.
    - SNOMED Top‑1 accuracy.
    - Field/relation/value mapping quality.
    - Nurse acceptance rate on small test batch.
  - Measure:
    - Time per protocol (manual vs AI‑assisted with small pilot).
    - Inference latency per protocol (<15s target).

**Stretch (Only if above done early):**
- Toy federated simulation with 2–3 synthetic "sites" using site splits.

---

### 4.4 Week 4 – Demo, Writeup & Polish (Feb 5–12)

**Goals:**
- Kaggle submission ready.
- Demo smooth and reproducible.

**Tasks:**

- **Demo Experience**
  - End‑to‑end flow:
    1. Upload or select existing protocol.
    2. Run extraction.
    3. Show criteria list with SNOMED codes + field/relation/value & confidence.
    4. Perform a couple of nurse edits.
    5. Show metrics/time‑saved panel.
  - Ensure no manual dev hacks (one‑command run via Docker Compose).

- **Kaggle Writeup**
  - Sections (with word limits):
    1. Problem & Impact (~300 words).
    2. Architecture (~400–500 words + 1 diagram).
    3. Human‑in‑the‑loop workflow (~300 words).
    4. Model & Training (~400–500 words).
    5. Results & Error Analysis (~400–500 words).
    6. ElixirTrials Integration Roadmap (~300–400 words).
    7. Reproducibility & Open Source (~200 words).

- **Notebook**
  - `notebooks/training_pipeline.ipynb`:
    - Load sample data.
    - Show preprocessing.
    - Demo LoRA training steps (small subset for Kaggle runtime).
    - Show metrics + inference example.

- **GitHub Repo**
  - Structure:
    ```text
    gemma-hackathon/
      backend/
        main.py
        models/
        ubkg_client.py
        tests/
      notebooks/
      data/ (small sample only)
      docs/
        api_spec.yaml
        architecture.md
        ubkg_notes.md
      docker-compose.yml
      README.md
    ```
  - README:
    - One‑command run.
    - Hardware assumptions.
    - UBKG API & UMLS licensing notes.
    - "Demo only – not for clinical use" disclaimer.

- **Video (3–5 min)**
  - Script:
    - 30s: Problem framing.
    - 60–90s: Live demo of upload → extraction → review.
    - 60s: Metrics summary.
    - 30–60s: ElixirTrials integration story.

---

## 5. Key Implementation Notes

### 5.1 UMLS Approval Already Secured
✅ No NLM license delay; proceed directly with full deployment.

### 5.2 UBKG as Single Source of Truth
- Use UBKG REST API for all terminology lookups (SNOMED, LOINC, RxNorm, ICD‑10).
- No custom wrapper needed; simple HTTP client + optional caching.
- Fallback: pre‑download SNOMED subset as CSV from UBKG downloads.

### 5.3 Data Privacy
- All protocols and edits stay in‑prem during hackathon.
- Only LoRA adapter weights and anonymized metrics shared post‑hackathon.

---

## 6. Metrics & Decision Gates

### 6.1 Core Metrics

- **Extraction (Task A)**
  - F1 on test set.
- **Grounding (Task B)**
  - SNOMED Top‑1 accuracy.
- **Field Mapping**
  - Field/relation/value mapping quality.
- **HITL**
  - Nurse acceptance rate.
  - Time per protocol (manual vs AI‑assisted).

### 6.2 Go / No‑Go for Stretch Work (Federated Prototype)

- **Only attempt if by end of Week 3:**
  - Extraction F1 ≥ 0.85.
  - SNOMED Top‑1 ≥ 0.80.
  - End‑to‑end demo stable.
  - At least 120 protocols annotated.

Otherwise, invest Week 4 fully in polish, metrics clarity, and submission quality.

---

## 7. Submission Checklist

### T‑72 Hours

- [ ] Run Docker Compose from clean environment.
- [ ] Run Kaggle notebook from top to bottom on Kaggle GPU.
- [ ] Freeze model artifacts (tagged release in GitHub).

### T‑24 Hours

- [ ] Finalize Kaggle writeup text.
- [ ] Upload demo video (YouTube unlisted).
- [ ] Verify all GitHub + notebook links.

### T‑0

- [ ] Submit Kaggle entry and confirm appearance in challenge.
- [ ] Backup repo + models to long‑term storage.
- [ ] Note learnings + next‑steps for ElixirTrials production track.