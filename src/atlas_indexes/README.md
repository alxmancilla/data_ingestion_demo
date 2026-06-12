# Atlas Search & Vector Search Index Definitions

These index definitions are intended for **MongoDB Atlas** (M10+).

The easiest way to create them is via the centralized script:

```bash
python src/create_indexes.py atlas
```

That script reads every JSON file in this directory and pushes it to the
correct collection using PyMongo's `create_search_index` API. The sections
below cover manual alternatives (Atlas UI, Atlas CLI, Admin API).

## Indexes

| File | Collection | Type | Purpose |
|------|------------|------|---------|
| `search_documents.json` | `documentreferences` | Atlas Search | Full-text search over clinical notes |
| `search_patients.json`  | `patients`           | Atlas Search | Fuzzy/autocomplete on patient names; facets on demographics |
| `vector_documents.json` | `documentreferences` | Vector Search | Semantic search over note embeddings (1024-dim, voyage-4) |

Index names match the `name` field in each JSON document and are referenced by
the example queries in `src/fhir_search.py` and `src/fhir_vector_search.py`.

## Creating via Atlas CLI

```bash
atlas clusters search indexes create \
  --clusterName <cluster> \
  --db fhir_poc \
  --collection documentreferences \
  --file src/atlas_indexes/search_documents.json
```

Repeat for each `*.json` file, adjusting `--collection` as shown in the table
above.

## Prerequisites

- Atlas cluster on M10 or higher
- Per-type ingestion mode used (`fhir_data_ingestor.py --mode per-type`) so
  collection names match (`patients`, `documentreferences`, etc.)
- For vector search: `VOYAGE_API_KEY` set when running
  `src/fhir_vector_search.py embed` to populate the `embedding` field
