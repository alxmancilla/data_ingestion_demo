#!/usr/bin/env python3
"""Atlas Search examples over FHIR resources.

Requires MongoDB Atlas (M10+) with the search indexes defined under
src/atlas_indexes/ created first. Assumes per-type ingestion mode.
"""

import argparse
import json
import os

from dotenv import load_dotenv
from pymongo import MongoClient

from fhir_vector_search import VECTOR_INDEX, VOYAGE_MODEL, _voyage

load_dotenv()

DOCS_INDEX = "documents_text"
PATIENTS_INDEX = "patients_search"
SYNONYMS_NAME = "clinical_synonyms"


def full_text_notes(db, query: str, limit: int = 10) -> list[dict]:
    """Full-text search across DocumentReference clinical notes with highlights."""
    pipeline = [
        {"$search": {
            "index": DOCS_INDEX,
            "text": {"query": query,
                     "path": {"value": "content.attachment.data",
                              "multi": "standard"},
                     "synonyms": SYNONYMS_NAME},
            "highlight": {"path": {"value": "content.attachment.data",
                                   "multi": "standard"}}}},
        {"$limit": limit},
        {"$project": {"_id": 0, "id": 1, "date": 1,
                      "subject": 1,
                      "score": {"$meta": "searchScore"},
                      "highlights": {"$meta": "searchHighlights"}}},
    ]
    return list(db.documentreferences.aggregate(pipeline))


def fuzzy_patient_name(db, name: str, limit: int = 10) -> list[dict]:
    """Fuzzy name match tolerating typos."""
    pipeline = [
        {"$search": {
            "index": PATIENTS_INDEX,
            "text": {"query": name, "path": ["name.family", "name.given"],
                     "fuzzy": {"maxEdits": 2, "prefixLength": 1}}}},
        {"$limit": limit},
        {"$project": {"_id": 0, "id": 1, "name": 1, "gender": 1, "birthDate": 1,
                      "score": {"$meta": "searchScore"}}},
    ]
    return list(db.patients.aggregate(pipeline))


def autocomplete_patient_name(db, prefix: str, limit: int = 10) -> list[dict]:
    """Type-ahead style search on patient names."""
    pipeline = [
        {"$search": {
            "index": PATIENTS_INDEX,
            "autocomplete": {"query": prefix, "path": "name.family",
                             "tokenOrder": "sequential"}}},
        {"$limit": limit},
        {"$project": {"_id": 0, "id": 1, "name": 1}},
    ]
    return list(db.patients.aggregate(pipeline))


def faceted_patient_search(db, query: str = "*") -> dict:
    """Faceted counts by gender and state for a search result set."""
    pipeline = [
        {"$searchMeta": {
            "index": PATIENTS_INDEX,
            "facet": {
                "operator": {"exists": {"path": "name.family"}} if query == "*"
                            else {"text": {"query": query,
                                           "path": ["name.family", "name.given"]}},
                "facets": {
                    "genderFacet": {"type": "string", "path": "gender"},
                    "stateFacet": {"type": "string", "path": "address.state",
                                   "numBuckets": 10}}}}},
    ]
    return next(iter(db.patients.aggregate(pipeline)), {})


def compound_clinical_search(db, query: str, patient_ref: str | None = None,
                              limit: int = 10) -> list[dict]:
    """Combine full-text with a structured filter on patient reference."""
    must = [{"text": {"query": query,
                      "path": {"value": "content.attachment.data",
                               "multi": "standard"},
                      "synonyms": SYNONYMS_NAME}}]
    filter_clauses = []
    if patient_ref:
        filter_clauses.append({"equals": {"path": "subject.reference",
                                          "value": patient_ref}})
    pipeline = [
        {"$search": {
            "index": DOCS_INDEX,
            "compound": {"must": must, "filter": filter_clauses}}},
        {"$limit": limit},
        {"$project": {"_id": 0, "id": 1, "date": 1, "subject": 1,
                      "score": {"$meta": "searchScore"}}},
    ]
    return list(db.documentreferences.aggregate(pipeline))


def hybrid_search(db, query: str, k: int = 10,
                  search_weight: float = 0.5,
                  vector_weight: float = 0.5) -> list[dict]:
    """Hybrid lexical + semantic retrieval via $rankFusion (RRF).

    Combines Atlas Search (full-text + clinical synonyms) and Vector Search
    (Voyage semantic embeddings) in a single aggregation. Documents ranked
    by Reciprocal Rank Fusion across both pipelines.
    """
    vo = _voyage()
    qvec = vo.embed([query], model=VOYAGE_MODEL,
                    input_type="query").embeddings[0]
    pipeline = [
        {"$rankFusion": {
            "input": {"pipelines": {
                "searchPipeline": [
                    {"$search": {
                        "index": DOCS_INDEX,
                        "text": {"query": query,
                                 "path": {"value": "content.attachment.data",
                                          "multi": "standard"},
                                 "synonyms": SYNONYMS_NAME}}},
                    {"$limit": k * 4},
                ],
                "vectorPipeline": [
                    {"$vectorSearch": {
                        "index": VECTOR_INDEX,
                        "path": "embedding",
                        "queryVector": qvec,
                        "numCandidates": max(50, k * 10),
                        "limit": k * 4}},
                ],
            }},
            "combination": {"weights": {"searchPipeline": search_weight,
                                        "vectorPipeline": vector_weight}},
            "scoreDetails": True,
        }},
        {"$limit": k},
        {"$project": {"_id": 0, "id": 1, "subject": 1, "date": 1,
                      "text": {"$first": "$content.attachment.data"},
                      "score": {"$meta": "score"},
                      "scoreDetails": {"$meta": "scoreDetails"}}},
    ]
    return list(db.documentreferences.aggregate(pipeline))


SEARCHES = {
    "notes": lambda db, a: full_text_notes(db, a.query, a.limit),
    "fuzzy-name": lambda db, a: fuzzy_patient_name(db, a.query, a.limit),
    "autocomplete": lambda db, a: autocomplete_patient_name(db, a.query, a.limit),
    "facets": lambda db, a: faceted_patient_search(db, a.query),
    "compound": lambda db, a: compound_clinical_search(db, a.query, a.patient_ref, a.limit),
    "hybrid": lambda db, a: hybrid_search(db, a.query, a.limit,
                                          a.search_weight, a.vector_weight),
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("operation", choices=list(SEARCHES))
    p.add_argument("--query", required=True)
    p.add_argument("--patient-ref", default=None,
                   help="e.g. Patient/<uuid> for compound search filter")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--search-weight", type=float, default=0.5,
                   help="hybrid: weight for $search pipeline (default 0.5)")
    p.add_argument("--vector-weight", type=float, default=0.5,
                   help="hybrid: weight for $vectorSearch pipeline (default 0.5)")
    p.add_argument("--uri", default=os.environ.get("MONGODB_URI", "mongodb://localhost:27017"))
    p.add_argument("--database", default=os.environ.get("FHIR_DB", "fhir_poc"))
    args = p.parse_args()

    db = MongoClient(args.uri)[args.database]
    result = SEARCHES[args.operation](db, args)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
