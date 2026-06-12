#!/usr/bin/env python3
"""Bulk import FHIR NDJSON files into MongoDB with multiple modeling strategies.

Modes:
  single          - All resources in one 'resources' collection (default)
  per-type        - One collection per FHIR resourceType (patients, encounters, ...)
  patient-centric - Embed encounters/observations/etc inside Patient documents
  time-series     - Observations into a MongoDB Time Series Collection
  bucketed        - Observations grouped into monthly buckets per patient
"""

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
from pymongo import MongoClient, InsertOne, UpdateOne
from pymongo.errors import BulkWriteError
from tqdm import tqdm

load_dotenv()

BATCH_SIZE = 5000


def iter_resources(data_dir: str) -> Iterator[dict]:
    """Yield every FHIR resource across all NDJSON files in data_dir."""
    for ndjson_file in sorted(Path(data_dir).glob("*.ndjson")):
        with open(ndjson_file, "r") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)


def _flush(coll, ops, total):
    if not ops:
        return total
    try:
        result = coll.bulk_write(ops, ordered=False)
        return total + result.inserted_count + result.upserted_count + result.modified_count
    except BulkWriteError as e:
        return total + e.details.get("nInserted", 0) + e.details.get("nUpserted", 0)


def ingest_single(db, data_dir: str):
    coll = db["resources"]
    coll.create_index([("resourceType", 1), ("id", 1)])
    coll.create_index([("subject.reference", 1)])
    coll.create_index([("patient.reference", 1)])
    coll.create_index([("encounter.reference", 1)])
    coll.create_index([("code.coding.code", 1)])

    ops, total = [], 0
    for r in tqdm(iter_resources(data_dir), desc="single"):
        r["_id"] = f"{r['resourceType']}/{r['id']}"
        ops.append(InsertOne(r))
        if len(ops) >= BATCH_SIZE:
            total = _flush(coll, ops, total); ops = []
    total = _flush(coll, ops, total)
    print(f"\u2713 single: {total:,} resources -> db.resources")


def ingest_per_type(db, data_dir: str):
    """One collection per resourceType. Pluralized lowercase names."""
    buffers: dict[str, list] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    for r in tqdm(iter_resources(data_dir), desc="per-type"):
        rtype = r["resourceType"]
        coll_name = rtype.lower() + "s"
        r["_id"] = r["id"]
        buffers[coll_name].append(InsertOne(r))
        if len(buffers[coll_name]) >= BATCH_SIZE:
            counts[coll_name] = _flush(db[coll_name], buffers[coll_name], counts[coll_name])
            buffers[coll_name] = []
    for name, ops in buffers.items():
        counts[name] = _flush(db[name], ops, counts[name])
    for name in counts:
        db[name].create_index([("subject.reference", 1)])
        db[name].create_index([("patient.reference", 1)])
        db[name].create_index([("encounter.reference", 1)])
    print("\u2713 per-type: " + ", ".join(f"{n}={c:,}" for n, c in counts.items()))


def _patient_ref(r: dict) -> str | None:
    ref = (r.get("subject") or r.get("patient") or {}).get("reference")
    return ref.split("/", 1)[1] if ref and ref.startswith("Patient/") else None


def ingest_patient_centric(db, data_dir: str):
    """Embed all child resources into a single Patient document."""
    coll = db["patient_records"]
    coll.create_index([("id", 1)], unique=True)
    coll.create_index([("encounters.id", 1)])

    patients: dict[str, dict] = {}
    children: dict[str, list[dict]] = defaultdict(list)

    for r in tqdm(iter_resources(data_dir), desc="patient-centric load"):
        if r["resourceType"] == "Patient":
            r["_id"] = r["id"]
            patients[r["id"]] = {**r, "encounters": [], "conditions": [],
                                  "observations": [], "medications": [],
                                  "procedures": [], "immunizations": [],
                                  "allergies": [], "carePlans": [], "documents": []}
        else:
            pid = _patient_ref(r)
            if pid:
                children[pid].append(r)

    bucket_map = {"Encounter": "encounters", "Condition": "conditions",
                  "Observation": "observations", "MedicationRequest": "medications",
                  "Procedure": "procedures", "Immunization": "immunizations",
                  "AllergyIntolerance": "allergies", "CarePlan": "carePlans",
                  "DocumentReference": "documents"}
    for pid, items in children.items():
        if pid not in patients:
            continue
        for r in items:
            key = bucket_map.get(r["resourceType"])
            if key:
                patients[pid][key].append(r)

    ops, total = [], 0
    for doc in tqdm(patients.values(), desc="patient-centric write"):
        ops.append(InsertOne(doc))
        if len(ops) >= 500:
            total = _flush(coll, ops, total); ops = []
    total = _flush(coll, ops, total)
    print(f"\u2713 patient-centric: {total:,} patient documents -> db.patient_records")


def _ensure_ts_collection(db, name: str):
    """Create a Time Series collection if it does not already exist."""
    if name in db.list_collection_names():
        return
    db.create_collection(
        name,
        timeseries={"timeField": "effectiveDateTime",
                    "metaField": "subject", "granularity": "hours"},
    )


def ingest_time_series(db, data_dir: str):
    """Observations -> time series collection. Other resources -> 'resources'."""
    _ensure_ts_collection(db, "observations_ts")
    ts = db["observations_ts"]
    other = db["resources"]
    other.create_index([("resourceType", 1), ("id", 1)])

    ts_ops, other_ops, ts_total, other_total = [], [], 0, 0
    for r in tqdm(iter_resources(data_dir), desc="time-series"):
        if r["resourceType"] == "Observation" and r.get("effectiveDateTime"):
            r["effectiveDateTime"] = datetime.fromisoformat(
                r["effectiveDateTime"].replace("Z", "+00:00"))
            ts_ops.append(InsertOne(r))
            if len(ts_ops) >= BATCH_SIZE:
                ts_total = _flush(ts, ts_ops, ts_total); ts_ops = []
        else:
            r["_id"] = f"{r['resourceType']}/{r['id']}"
            other_ops.append(InsertOne(r))
            if len(other_ops) >= BATCH_SIZE:
                other_total = _flush(other, other_ops, other_total); other_ops = []
    ts_total = _flush(ts, ts_ops, ts_total)
    other_total = _flush(other, other_ops, other_total)
    print(f"\u2713 time-series: observations_ts={ts_total:,}, resources={other_total:,}")


def _bucket_key(iso_date: str) -> str:
    return iso_date[:7]  # YYYY-MM


def ingest_bucketed(db, data_dir: str):
    """Observations bucketed by (patient, YYYY-MM). Other resources -> 'resources'."""
    buckets = db["observation_buckets"]
    buckets.create_index([("patient", 1), ("bucket", 1)], unique=True)
    other = db["resources"]
    other.create_index([("resourceType", 1), ("id", 1)])

    bucket_ops, other_ops, bcount, ocount = [], [], 0, 0
    for r in tqdm(iter_resources(data_dir), desc="bucketed"):
        if r["resourceType"] == "Observation" and r.get("effectiveDateTime"):
            pid = _patient_ref(r) or "unknown"
            bkey = _bucket_key(r["effectiveDateTime"])
            bucket_ops.append(UpdateOne(
                {"patient": pid, "bucket": bkey},
                {"$push": {"observations": r},
                 "$inc": {"count": 1},
                 "$min": {"first": r["effectiveDateTime"]},
                 "$max": {"last": r["effectiveDateTime"]}},
                upsert=True))
            if len(bucket_ops) >= 1000:
                bcount = _flush(buckets, bucket_ops, bcount); bucket_ops = []
        else:
            r["_id"] = f"{r['resourceType']}/{r['id']}"
            other_ops.append(InsertOne(r))
            if len(other_ops) >= BATCH_SIZE:
                ocount = _flush(other, other_ops, ocount); other_ops = []
    bcount = _flush(buckets, bucket_ops, bcount)
    ocount = _flush(other, other_ops, ocount)
    print(f"\u2713 bucketed: buckets touched={bcount:,}, resources={ocount:,}")


INGESTORS = {"single": ingest_single, "per-type": ingest_per_type,
             "patient-centric": ingest_patient_centric,
             "time-series": ingest_time_series, "bucketed": ingest_bucketed}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=list(INGESTORS), default="single")
    p.add_argument("--uri", default=os.environ.get("MONGODB_URI", "mongodb://localhost:27017"))
    p.add_argument("--database", default=os.environ.get("FHIR_DB", "fhir_poc"))
    p.add_argument("--data-dir", default="./fhir_data")
    p.add_argument("--drop", action="store_true", help="Drop database before ingest")
    args = p.parse_args()

    client = MongoClient(args.uri)
    if args.drop:
        client.drop_database(args.database)
    db = client[args.database]
    INGESTORS[args.mode](db, args.data_dir)

    if args.mode == "per-type":
        _print_next_steps(db)


def _print_next_steps(db) -> None:
    print("\nNext steps:")
    print("  1. Create indexes:   python src/create_indexes.py all")
    print("  2. Verify setup:     python src/atlas_check.py")
    print("  3. Sample patient IDs for demo:")
    try:
        from sample_ids import PROFILES, _fmt
        for label, fn in PROFILES.items():
            print(f"     {label:<13} {_fmt(fn(db))}")
    except Exception as e:
        print(f"     (sample_ids unavailable: {e})")


if __name__ == "__main__":
    main()
