# FHIR Demo

An end-to-end demo of **FHIR R4 on MongoDB Atlas**. Generates synthetic FHIR
resources, ingests them with five document-modeling strategies, and exercises
the full Atlas data platform on the result — clinical aggregations, Atlas
Search with clinical synonyms, Vector Search + RAG over clinical notes, hybrid
search with `$rankFusion`, real-time alerts via Change Streams, a FHIR REST
search API, and reproducible cross-strategy benchmarks.

Intended audience: developers and architects evaluating MongoDB Atlas for
healthcare interoperability, clinical analytics, and AI-powered retrieval over
FHIR data.

## Features

- **FHIR R4 Compliance** — Standards-compliant resources with real code systems (SNOMED CT, LOINC, RxNorm, CVX, UCUM)
- **Pydantic-Validated Models** — 13 FHIR resource types with type-safe serialization
- **Five Data-Modeling Strategies** — Single-collection, per-type, patient-centric embedded, time-series, bucketed
- **Clinical Aggregation Analytics** — `$lookup`, `$graphLookup`, `$setWindowFields` examples for cohort, readmission, and population-health queries
- **Atlas Search with Clinical Synonyms** — Full-text, fuzzy, autocomplete, and faceted search with a built-in cardiology/endocrinology/respiratory synonym map (`MI` ↔ `myocardial infarction`, `HTN` ↔ `hypertension`, `T2DM` ↔ `type 2 diabetes`, …)
- **Atlas Vector Search + RAG** — Voyage AI `voyage-4` embeddings, semantic retrieval, and grounded Q&A via the Grove gateway to OpenAI Responses
- **Hybrid Search with `$rankFusion`** — Native Atlas RRF combining lexical and semantic pipelines in a single aggregation
- **FHIR Subscriptions via Change Streams** — Real-time clinical alerts (HbA1c/BP/HR/SpO2/glucose thresholds) on Atlas replica sets
- **FHIR REST Search API** — FastAPI implementation translating FHIR search parameters to MongoDB queries
- **Performance Benchmarks** — Reproducible ingest-throughput, query-latency, and storage comparisons across modeling strategies
- **Presenter-Ready Demo Script** — `scripts/demo.sh` walks through every section end-to-end with auto-selected sample patients

## FHIR Implementation

This project implements **FHIR R4** (Fast Healthcare Interoperability Resources, Release 4), the HL7 standard for healthcare data exchange. All resources are modeled as Pydantic classes that serialize to FHIR-compliant JSON.

### FHIR Data Types

Core FHIR data types used as building blocks across resources:

| Data Type | Purpose |
|-----------|---------|
| `Reference` | Links between resources (e.g., `Patient/{id}`, `Encounter/{id}`) |
| `Coding` | A single code from a terminology system (system + code + display) |
| `CodeableConcept` | One or more `Coding` values plus optional text |
| `Identifier` | Business identifiers (MRN, SSN, NPI) |
| `HumanName` | Patient/practitioner names (family, given) |
| `Address` | Postal addresses |
| `ContactPoint` | Phone, email, and other contact channels |
| `Period` | Time ranges with start/end (e.g., encounter duration) |
| `Quantity` | Numeric values with units (UCUM-coded measurements) |

### FHIR Resources

The generator produces 13 FHIR resource types covering a comprehensive patient health record:

#### Administrative Resources
| Resource | Description |
|----------|-------------|
| `Patient` | Demographics, identifiers (MRN, SSN), contact info, marital status |
| `Practitioner` | Healthcare providers with NPI identifiers |
| `Organization` | Healthcare facilities and provider organizations |

#### Clinical Resources
| Resource | Description |
|----------|-------------|
| `Encounter` | Patient visits (Ambulatory, Emergency, Inpatient, Observation) |
| `Condition` | Diagnoses coded with SNOMED CT (hypertension, diabetes, asthma, etc.) |
| `Observation` | Vital signs and laboratory results coded with LOINC |
| `MedicationRequest` | Prescriptions coded with RxNorm, with dosage instructions |
| `Procedure` | Medical procedures coded with SNOMED CT |
| `DiagnosticReport` | Lab report summaries grouping related observations |
| `AllergyIntolerance` | Patient allergies (medication, food, environment) |
| `Immunization` | Vaccination records coded with CVX |
| `CarePlan` | Treatment plans and care activities |
| `DocumentReference` | Clinical notes and document metadata |

### Code Systems Used

The generator uses real-world medical coding standards as required by FHIR:

- **SNOMED CT** (`http://snomed.info/sct`) — Conditions, procedures, allergies
- **LOINC** (`http://loinc.org`) — Vital signs and laboratory tests
- **RxNorm** (`http://www.nlm.nih.gov/research/umls/rxnorm`) — Medications
- **CVX** (`http://hl7.org/fhir/sid/cvx`) — Vaccines
- **UCUM** (`http://unitsofmeasure.org`) — Units of measure
- **HL7 Terminology** (`http://terminology.hl7.org/CodeSystem/...`) — Status codes, categories, encounter classes

### Resource Relationships

Resources are linked via FHIR `Reference` types, forming a graph rooted at `Patient`:

```
Patient
├── AllergyIntolerance (2–5 per patient)
└── Encounter (80–120 per patient)
    ├── Condition (1–3 per encounter)
    ├── Observation — Vital Signs (5–10 per encounter)
    ├── Observation — Laboratory (10–30 per encounter)
    ├── DiagnosticReport (1–3 per encounter, references Observations)
    ├── MedicationRequest (1–5 per encounter, references Practitioner)
    ├── Procedure (0–3 per encounter, references Practitioner)
    ├── Immunization (0–2 per encounter)
    ├── CarePlan (~30% probability per encounter)
    └── DocumentReference (1–2 per encounter, references Practitioner)

Shared across all patients:
├── Practitioner (100 total)
└── Organization (20 total, referenced as Encounter.serviceProvider)
```

### Output Format

Resources are written as **NDJSON** (newline-delimited JSON), the format used by the FHIR Bulk Data Access specification. Each line is a complete, valid FHIR resource ready for streaming ingestion into MongoDB.

## Requirements

- Python 3.10 or higher (3.13 recommended)
- pip (Python package manager)
- A **MongoDB Atlas** cluster (M10+ for Atlas Search / Vector Search features).
  A local `mongod` works for ingestion, queries, and benchmarks only.

## Installation

1. Clone and enter the repository:
   ```bash
   git clone <repository-url>
   cd fhir_demo
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate            # macOS/Linux
   # venv\Scripts\activate             # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt # optional, for tests / linting
   ```

4. Configure environment variables:
   ```bash
   cp .env.example .env
   # then edit .env and fill in MONGODB_URI, VOYAGE_API_KEY, GROVE_API_KEY
   ```

   All scripts auto-load `.env` via `python-dotenv`, so no `export` /
   `source` step is needed.

   | Variable          | Used by                                            | Required for                         |
   |-------------------|----------------------------------------------------|--------------------------------------|
   | `MONGODB_URI`     | All scripts (overridable with `--uri`)             | Every command                        |
   | `FHIR_DB`         | All scripts (overridable with `--database`)        | Every command                        |
   | `VOYAGE_API_KEY`  | `fhir_vector_search.py` (`embed`/`search`/`ask`)   | Vector Search + RAG                  |
   | `GROVE_API_KEY`   | `fhir_vector_search.py ask`                        | RAG completion only                  |

## Quickstart for Atlas Demo

The fastest path from a fresh clone to a complete Atlas demo:

```bash
# 0. One-time setup (see Installation above)
cp .env.example .env && $EDITOR .env        # set MONGODB_URI, VOYAGE_API_KEY, GROVE_API_KEY
pip install -r requirements.txt

# 1. Generate a small demo dataset (~200 patients keeps embedding cost low)
python src/fhir_data_generator.py --patients 200

# 2. Ingest per-type (required by queries, search, API) and drop any prior run
python src/fhir_data_ingestor.py --mode per-type --drop

# 3. Create all indexes (standard B-tree + Atlas Search + Vector Search + synonyms)
python src/create_indexes.py all

# 4. Verify Atlas connectivity + index readiness
python src/atlas_check.py

# 5. Compute embeddings for clinical notes (required for vector + hybrid + RAG)
python src/fhir_vector_search.py embed

# 6. Run the guided end-to-end walkthrough (pauses between sections)
./scripts/demo.sh
```

`scripts/demo.sh` chains the §4–§9 commands together, auto-selecting illustrative
patient UUIDs via `src/sample_ids.py` (diabetic / hypertensive / readmitted /
rich-notes). Set `PAUSE=0` to run non-interactively.

## Project Structure

```
fhir_demo/
├── src/                          # Source code
│   ├── fhir_data_generator.py    # FHIR R4 resource generator (NDJSON output)
│   ├── fhir_data_ingestor.py     # Bulk ingestion with 5 modeling strategies
│   ├── fhir_queries.py           # Clinical aggregation pipeline examples
│   ├── fhir_search.py            # Atlas Search examples (full-text, fuzzy, facets)
│   ├── fhir_vector_search.py     # Voyage AI embeddings + $vectorSearch + RAG
│   ├── fhir_api.py               # FastAPI FHIR REST search endpoints
│   ├── fhir_subscriptions.py     # Change Streams watcher for real-time alerts
│   ├── benchmarks.py             # Cross-strategy performance benchmarks
│   ├── create_indexes.py         # Standard + Atlas Search/Vector index creator
│   ├── atlas_check.py            # Pre-flight check: Atlas detection + readiness
│   ├── sample_ids.py             # Print illustrative patient UUIDs for demos
│   └── atlas_indexes/            # Atlas Search & Vector Search index JSON
│       └── synonyms.json         # Cardiology / endocrinology / respiratory abbreviations
├── scripts/
│   └── demo.sh                   # End-to-end presenter walkthrough
├── tests/                        # Test files
├── requirements.txt              # Production dependencies
├── requirements-dev.txt          # Development dependencies
├── pyproject.toml                # Project configuration
├── .env.example                  # Template for MongoDB / Voyage / Grove credentials
├── .gitignore                    # Git ignore rules (also excludes .env)
└── README.md                     # This file
```

## Usage

### 1. Generate FHIR Data

```bash
python src/fhir_data_generator.py --patients 1000 --batch-size 100 --output fhir_data
```

This produces NDJSON files in the `fhir_data/` directory:
- `shared_resources.ndjson` — Practitioners and Organizations
- `patients_00001_to_00100.ndjson`, ... — Patient resource batches

### 2. Ingest into MongoDB

Connection parameters come from `MONGODB_URI` / `FHIR_DB` in `.env`; the
`--uri` and `--database` CLI flags override per-command when needed.

The ingestor supports five data-modeling strategies, selectable via `--mode`:

| Mode | Layout | Use case |
|------|--------|----------|
| `single` (default) | All resources in `resources` collection | Polymorphic queries; FHIR Bulk import baseline |
| `per-type` | One collection per `resourceType` (`patients`, `encounters`, …) | Targeted indexing; required by `fhir_queries.py`, `fhir_search.py`, `fhir_api.py` |
| `patient-centric` | Each `Patient` document embeds its full record | Single-read patient summary; document model showcase |
| `time-series` | `Observation` → MongoDB Time Series Collection | Compressed vital-sign / lab trend storage |
| `bucketed` | `Observation` → monthly per-patient buckets | Bucket pattern; index-efficient time scans |

```bash
python src/fhir_data_ingestor.py --mode per-type --drop
python src/fhir_data_ingestor.py --mode patient-centric --database fhir_centric --drop
```

### 3. Create Indexes

Standard MongoDB indexes (covering every filter used by `fhir_queries.py` and
`fhir_api.py`) plus Atlas Search and Vector Search indexes can all be
provisioned with a single script. It is idempotent and safe to rerun.

```bash
# Local mongod or non-Atlas deployment:
python src/create_indexes.py standard

# Full Atlas setup (standard + Atlas Search + Vector Search):
python src/create_indexes.py all

# Just (re)push the Atlas Search / Vector Search index definitions:
python src/create_indexes.py atlas
```

| Index category        | Collections covered                                                       | Created by                          |
|-----------------------|---------------------------------------------------------------------------|-------------------------------------|
| Standard B-tree       | `patients`, `encounters`, `observations`, `conditions`, `medicationrequests`, `procedures`, `immunizations`, `allergyintolerances`, `documentreferences`, `diagnosticreports`, `careplans` | `create_indexes.py standard`        |
| Atlas Search          | `patients` (fuzzy/autocomplete/facets), `documentreferences` (full-text)  | `create_indexes.py atlas`           |
| Atlas Vector Search   | `documentreferences` (1024-dim `embedding` + `subject.reference` filter)  | `create_indexes.py atlas`           |

Atlas Search/Vector Search indexes build asynchronously; check status in the
Atlas UI or via `atlas clusters search indexes list`.

### 4. Clinical Analytics (Aggregation Pipelines)

Requires `--mode per-type` ingestion. Demonstrates `$lookup`, `$graphLookup`,
`$setWindowFields`, `$bucket`, and grouping for population health.

```bash
python src/fhir_queries.py patient-everything --patient-id <uuid>
python src/fhir_queries.py patient-graph     --patient-id <uuid>
python src/fhir_queries.py diabetic-cohort   --hba1c 7.0 --limit 25
python src/fhir_queries.py population-health
python src/fhir_queries.py readmissions      --limit 25
python src/fhir_queries.py medication-trends --limit 10
```

### 5. Atlas Search (Full-Text on Clinical Notes)

**Requires MongoDB Atlas (M10+).** Provision the indexes once with
`python src/create_indexes.py atlas` (see §3), then:

```bash
python src/fhir_search.py notes        --query "chest pain"
python src/fhir_search.py notes        --query "MI"                # synonym → myocardial infarction
python src/fhir_search.py fuzzy-name   --query "Jhonson"          # tolerates typos
python src/fhir_search.py autocomplete --query "Smi"               # type-ahead
python src/fhir_search.py facets       --query "*"                 # gender / state facets
python src/fhir_search.py compound     --query "diabetes" \
    --patient-ref "Patient/<uuid>"
```

**Clinical synonyms.** `src/atlas_indexes/synonyms.json` ships with ~30
cardiology, endocrinology, and respiratory abbreviations (`MI` ↔ `myocardial
infarction`, `HTN` ↔ `hypertension`, `T2DM` ↔ `type 2 diabetes`, `COPD`,
`SOB`, `HbA1c`, …). It is loaded into a dedicated `clinical_synonyms`
collection by `create_indexes.py atlas` and wired into the `documents_text`
search index automatically.

### 6. Vector Search + RAG (Semantic Q&A)

**Requires Atlas Vector Search.** Uses **Voyage AI `voyage-4`** (1024-dim) for
embeddings and the **OpenAI Responses API via the Grove gateway** (`gpt-5.5`)
for grounded answer generation. `VOYAGE_API_KEY` and `GROVE_API_KEY` come
from `.env`.

```bash
# 1. Compute embeddings for DocumentReference clinical notes
python src/fhir_vector_search.py embed

# 2. Provision the vector index (if not done in §3)
python src/create_indexes.py atlas

# 3. Semantic retrieval (no LLM call)
python src/fhir_vector_search.py search --query "patient with breathing issues" --k 5

# 4. Full RAG: retrieve + generate grounded answer
python src/fhir_vector_search.py ask \
    --question "What conditions has this patient been treated for?" \
    --patient-ref "Patient/<uuid>" --k 5
```

### 7. Hybrid Search with `$rankFusion`

**Requires Atlas 8.1+ with both `documents_text` and `documents_vector` indexes
plus embeddings populated (§3, §6).** Combines lexical Atlas Search (synonyms +
fuzzy) with semantic Vector Search in a single aggregation using the native
Reciprocal Rank Fusion stage:

```bash
python src/fhir_search.py hybrid --query "shortness of breath after MI" --limit 5
python src/fhir_search.py hybrid --query "elevated A1c diabetic neuropathy" \
    --search-weight 1.0 --vector-weight 1.5
```

`--search-weight` / `--vector-weight` tune the contribution of each pipeline
before rank fusion.

### 8. Real-Time Subscriptions via Change Streams

**Requires a replica set or Atlas (any tier).** Emulates a FHIR Subscription
channel: `fhir_subscriptions.py watch` tails the `observations` collection and
prints an alert whenever a newly inserted Observation crosses a clinical
threshold (HbA1c, BP, HR, SpO2, glucose, temperature, respiratory rate).

Run the watcher in one terminal and trigger alerts from another:

```bash
# Terminal A — foreground watcher (Ctrl+C to stop)
python src/fhir_subscriptions.py watch

# Terminal B — insert 5 abnormal observations for a real patient
python src/fhir_subscriptions.py simulate -n 5 \
    --patient-ref "Patient/$(python src/sample_ids.py --profile diabetic)"
```

### 9. FHIR REST Search API (FastAPI)

Translates FHIR R4 search parameters into MongoDB queries and returns
FHIR `Bundle` responses. Requires `--mode per-type` ingestion. The app
reads `MONGODB_URI` / `FHIR_DB` from `.env` on startup.

```bash
uvicorn src.fhir_api:app --reload
```

Interactive docs at <http://localhost:8000/docs>. Example requests:

```bash
curl 'http://localhost:8000/Patient?family=Smith&_count=5'
curl 'http://localhost:8000/Observation?patient=<uuid>&code=http://loinc.org|8867-4'
curl 'http://localhost:8000/Encounter?date=ge2024-01-01&date=le2024-12-31&status=finished'
curl 'http://localhost:8000/Patient/<uuid>/$everything'
```

### 10. Performance Benchmarks

Generates a small dataset (default 50 patients), runs every ingestion mode, and
measures ingest time, `$everything` latency, and storage footprint.

```bash
python src/benchmarks.py --patients 50
python src/benchmarks.py --patients 100 --modes single per-type patient-centric
```

### 11. Demo Utilities

Small helpers used by `scripts/demo.sh` and useful on their own:

```bash
# Verify Atlas connectivity, list search/vector indexes, report readiness
python src/atlas_check.py

# Print illustrative patient UUIDs for each clinical profile
python src/sample_ids.py                          # human-readable table
python src/sample_ids.py --json                   # raw JSON
python src/sample_ids.py --profile diabetic       # bare UUID (for shell scripting)
```

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black src/ tests/
```

### Linting

```bash
flake8 src/ tests/
```

### Type Checking

```bash
mypy src/
```

## Dependencies

**Core**
- **pydantic** (>=2.6) — Data validation for FHIR resource models
- **faker** (>=22.0) — Synthetic demographic and clinical data
- **pymongo** (==4.16.0) — MongoDB driver for bulk ingestion and queries
- **tqdm** (>=4.66) — Progress bars
- **python-dotenv** (>=1.0) — `.env` auto-loading for all entry points

**FHIR REST API**
- **fastapi** (>=0.115) — Web framework for the search API
- **uvicorn[standard]** (>=0.30) — ASGI server

**Vector Search + RAG**
- **voyageai** (>=0.4) — Voyage AI client for `voyage-4` embeddings
- **httpx** (>=0.27) — HTTP client for the Grove gateway / OpenAI Responses API

**Benchmarks**
- **numpy** (>=2.0) — Numeric utilities
- **tabulate** (>=0.9) — Pretty-printed result tables

### External Service Requirements

| Feature                       | Requirement                                                          |
|-------------------------------|----------------------------------------------------------------------|
| Atlas Search (§5)             | MongoDB Atlas M10+ with indexes from `python src/create_indexes.py atlas` |
| Vector Search (§6)            | Same as above + `VOYAGE_API_KEY` in `.env`                           |
| RAG `ask` (§6)                | Additionally requires `GROVE_API_KEY` in `.env`                      |
| Hybrid `$rankFusion` (§7)     | Atlas 8.1+ with both `documents_text` and `documents_vector` indexes and embeddings populated |
| Change Streams (§8)           | A MongoDB replica set, sharded cluster, or any Atlas cluster         |

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

For questions or feedback, please open an issue in the repository.

