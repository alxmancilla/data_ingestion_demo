#!/usr/bin/env python3
"""Find illustrative patient IDs for the demo walkthrough.

Picks a representative patient for each of several clinical profiles so the
presenter can pass real UUIDs into fhir_queries.py / fhir_api.py / etc.
Requires per-type ingestion mode.

Profiles:
  diabetic       - Patient with Type 2 Diabetes (SNOMED 44054006) and an HbA1c
  hypertensive   - Patient with Essential Hypertension (SNOMED 59621000)
  readmitted     - Patient with an inpatient encounter < 30 days after another
  rich-notes     - Patient with the most DocumentReferences (best RAG candidate)
  generic        - First patient by id (fallback / baseline)
"""

import argparse
import json
import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

DIABETES_SCT = "44054006"
HYPERTENSION_SCT = "59621000"
HBA1C_LOINC = "4548-4"


def _patient(db, ref: str) -> dict | None:
    if not ref or not ref.startswith("Patient/"):
        return None
    return db.patients.find_one({"id": ref.split("/", 1)[1]},
                                {"_id": 0, "id": 1, "name": 1, "gender": 1,
                                 "birthDate": 1})


def diabetic(db) -> dict | None:
    doc = db.conditions.find_one({"code.coding.code": DIABETES_SCT},
                                 {"subject.reference": 1})
    if not doc:
        return None
    p = _patient(db, doc["subject"]["reference"])
    if not p:
        return None
    obs = db.observations.find_one(
        {"subject.reference": doc["subject"]["reference"],
         "code.coding.code": HBA1C_LOINC},
        sort=[("effectiveDateTime", -1)],
        projection={"valueQuantity.value": 1, "effectiveDateTime": 1})
    p["latest_hba1c"] = obs.get("valueQuantity", {}).get("value") if obs else None
    return p


def hypertensive(db) -> dict | None:
    doc = db.conditions.find_one({"code.coding.code": HYPERTENSION_SCT},
                                 {"subject.reference": 1})
    return _patient(db, doc["subject"]["reference"]) if doc else None


def readmitted(db) -> dict | None:
    pipeline = [
        {"$match": {"class.code": "IMP", "period.start": {"$ne": None}}},
        {"$addFields": {"start": {"$toDate": "$period.start"}}},
        {"$sort": {"subject.reference": 1, "start": 1}},
        {"$setWindowFields": {
            "partitionBy": "$subject.reference",
            "sortBy": {"start": 1},
            "output": {"prev": {
                "$shift": {"output": "$start", "by": -1, "default": None}}}}},
        {"$match": {"prev": {"$ne": None},
                    "$expr": {"$lte": [{"$dateDiff": {
                        "startDate": "$prev", "endDate": "$start",
                        "unit": "day"}}, 30]}}},
        {"$limit": 1},
        {"$project": {"_id": 0, "ref": "$subject.reference"}},
    ]
    hit = next(iter(db.encounters.aggregate(pipeline)), None)
    return _patient(db, hit["ref"]) if hit else None


def rich_notes(db) -> dict | None:
    pipeline = [
        {"$group": {"_id": "$subject.reference", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
        {"$limit": 1},
    ]
    hit = next(iter(db.documentreferences.aggregate(pipeline)), None)
    if not hit:
        return None
    p = _patient(db, hit["_id"])
    if p:
        p["document_count"] = hit["n"]
    return p


def generic(db) -> dict | None:
    return db.patients.find_one({}, {"_id": 0, "id": 1, "name": 1,
                                     "gender": 1, "birthDate": 1})


PROFILES = {"diabetic": diabetic, "hypertensive": hypertensive,
            "readmitted": readmitted, "rich-notes": rich_notes,
            "generic": generic}


def _fmt(p: dict | None) -> str:
    if not p:
        return "(none found)"
    name = (p.get("name") or [{}])[0]
    fam = name.get("family", "?")
    given = " ".join(name.get("given") or [])
    extras = {k: v for k, v in p.items()
              if k in ("latest_hba1c", "document_count")}
    extra = f"  [{', '.join(f'{k}={v}' for k, v in extras.items())}]" if extras else ""
    return f"{p['id']}  {given} {fam} ({p.get('gender')}, {p.get('birthDate')}){extra}"


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--uri", default=os.environ.get("MONGODB_URI", "mongodb://localhost:27017"))
    p.add_argument("--database", default=os.environ.get("FHIR_DB", "fhir_poc"))
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.add_argument("--profile", choices=list(PROFILES),
                   help="Print only this profile's UUID (no labels) - for scripting")
    args = p.parse_args()

    db = MongoClient(args.uri)[args.database]
    results = {name: fn(db) for name, fn in PROFILES.items()}

    if args.profile:
        hit = results.get(args.profile)
        print(hit["id"] if hit else "", end="")
        return

    if args.json:
        print(json.dumps(results, indent=2, default=str))
        return

    print("Sample patient IDs for demo walkthrough\n")
    width = max(len(k) for k in results) + 2
    for label, hit in results.items():
        print(f"  {label:<{width}} {_fmt(hit)}")
    print("\nCopy any UUID above into --patient-id / --patient-ref flags.")


if __name__ == "__main__":
    main()
