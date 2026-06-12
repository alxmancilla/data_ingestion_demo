#!/usr/bin/env python3
"""Create MongoDB indexes for the FHIR demo.

Modes:
  standard  - Regular MongoDB indexes on per-type collections (works on any
              MongoDB deployment, including local mongod).
  atlas     - Atlas Search + Vector Search indexes from src/atlas_indexes/*.json
              (requires MongoDB Atlas M10+).
  all       - Both of the above.

All indexes are created idempotently; rerunning is safe.
"""

import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import OperationFailure
from pymongo.operations import SearchIndexModel

load_dotenv()

# Standard indexes per collection (used by fhir_queries.py, fhir_api.py).
STANDARD_INDEXES: dict[str, list[list[tuple[str, int]]]] = {
    "patients": [
        [("id", ASCENDING)],
        [("name.family", ASCENDING)],
        [("name.given", ASCENDING)],
        [("gender", ASCENDING)],
        [("birthDate", ASCENDING)],
    ],
    "encounters": [
        [("subject.reference", ASCENDING)],
        [("status", ASCENDING)],
        [("class.code", ASCENDING)],
        [("period.start", ASCENDING)],
        [("class.code", ASCENDING), ("subject.reference", ASCENDING),
         ("period.start", ASCENDING)],
    ],
    "observations": [
        [("subject.reference", ASCENDING)],
        [("code.coding.code", ASCENDING)],
        [("category.coding.code", ASCENDING)],
        [("effectiveDateTime", DESCENDING)],
        [("subject.reference", ASCENDING), ("code.coding.code", ASCENDING),
         ("effectiveDateTime", DESCENDING)],
    ],
    "conditions": [
        [("subject.reference", ASCENDING)],
        [("code.coding.code", ASCENDING)],
    ],
    "medicationrequests": [
        [("subject.reference", ASCENDING)],
        [("medicationCodeableConcept.text", ASCENDING)],
    ],
    "procedures": [[("subject.reference", ASCENDING)]],
    "immunizations": [[("patient.reference", ASCENDING)]],
    "allergyintolerances": [[("patient.reference", ASCENDING)]],
    "documentreferences": [
        [("subject.reference", ASCENDING)],
        [("date", DESCENDING)],
    ],
    "diagnosticreports": [[("subject.reference", ASCENDING)]],
    "careplans": [[("subject.reference", ASCENDING)]],
}

# Atlas Search/Vector Search index files -> target collection.
ATLAS_INDEXES: list[tuple[str, str]] = [
    ("search_patients.json", "patients"),
    ("search_documents.json", "documentreferences"),
    ("vector_documents.json", "documentreferences"),
]

SYNONYMS_FILE = "synonyms.json"


def create_standard(db) -> None:
    existing_colls = set(db.list_collection_names())
    for coll_name, specs in STANDARD_INDEXES.items():
        if coll_name not in existing_colls:
            print(f"  - skip {coll_name} (collection missing; ingest first)")
            continue
        for keys in specs:
            name = db[coll_name].create_index(keys)
            print(f"  \u2713 {coll_name}.{name}")


def load_synonyms(db, index_dir: Path) -> None:
    """Replace the synonyms source collection from synonyms.json (idempotent)."""
    path = index_dir / SYNONYMS_FILE
    if not path.exists():
        print(f"  - skip synonyms ({SYNONYMS_FILE} not found)")
        return
    spec = json.loads(path.read_text())
    coll_name = spec["collection"]
    docs = spec["mappings"]
    db[coll_name].drop()
    if docs:
        db[coll_name].insert_many(docs)
    print(f"  \u2713 {coll_name}: {len(docs)} synonym mappings loaded")


def create_atlas(db, index_dir: Path) -> None:
    load_synonyms(db, index_dir)
    for filename, coll_name in ATLAS_INDEXES:
        path = index_dir / filename
        if not path.exists():
            print(f"  - skip {filename} (file not found)")
            continue
        spec = json.loads(path.read_text())
        model = SearchIndexModel(
            definition=spec["definition"],
            name=spec["name"],
            type=spec.get("type", "search"),
        )
        try:
            db[coll_name].create_search_index(model)
            print(f"  \u2713 {coll_name}.{spec['name']} ({model.document['type']})")
        except OperationFailure as e:
            if "already exists" in str(e).lower() or e.code == 68:
                db[coll_name].update_search_index(spec["name"], spec["definition"])
                print(f"  \u21bb {coll_name}.{spec['name']} (updated)")
            else:
                raise


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", choices=["standard", "atlas", "all"], default="all", nargs="?")
    p.add_argument("--uri", default=os.environ.get("MONGODB_URI", "mongodb://localhost:27017"))
    p.add_argument("--database", default=os.environ.get("FHIR_DB", "fhir_poc"))
    p.add_argument("--index-dir", default="src/atlas_indexes",
                   help="Directory containing Atlas Search/Vector index JSON files")
    args = p.parse_args()

    db = MongoClient(args.uri)[args.database]
    print(f"Database: {args.database}")

    if args.mode in ("standard", "all"):
        print("\nStandard MongoDB indexes:")
        t0 = time.perf_counter()
        create_standard(db)
        print(f"  done in {time.perf_counter() - t0:.2f}s")

    if args.mode in ("atlas", "all"):
        print("\nAtlas Search / Vector Search indexes:")
        t0 = time.perf_counter()
        create_atlas(db, Path(args.index_dir))
        print(f"  done in {time.perf_counter() - t0:.2f}s")
        print("  (Atlas indexes build asynchronously; check status in the Atlas UI.)")


if __name__ == "__main__":
    main()
