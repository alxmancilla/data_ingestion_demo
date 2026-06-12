#!/usr/bin/env python3
"""Performance benchmarks across data-modeling strategies.

Measures:
  - Ingestion throughput per mode (docs/sec, MB read)
  - Patient $everything latency per mode
  - Diabetic cohort query latency
  - Storage size per mode (collection stats)

Default: 50 patients (~500k resources). Adjust with --patients.
"""

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from tabulate import tabulate

load_dotenv()

MODES = ["single", "per-type", "patient-centric", "time-series", "bucketed"]
PY = sys.executable


def regenerate(data_dir: Path, patients: int):
    if data_dir.exists() and any(data_dir.glob("*.ndjson")):
        print(f"reusing existing data in {data_dir}")
        return
    print(f"generating {patients} patients into {data_dir} ...")
    subprocess.run([PY, "src/fhir_data_generator.py",
                    "--patients", str(patients), "--batch-size",
                    str(min(patients, 100)), "--output", str(data_dir)], check=True)


def ingest(mode: str, uri: str, db_name: str, data_dir: Path) -> float:
    """Run the ingestor as a subprocess. Returns wall time in seconds."""
    start = time.perf_counter()
    subprocess.run([PY, "src/fhir_data_ingestor.py", "--mode", mode,
                    "--uri", uri, "--database", db_name,
                    "--data-dir", str(data_dir), "--drop"],
                   check=True, stdout=subprocess.DEVNULL)
    return time.perf_counter() - start


def _patient_everything_query(db, mode: str, pid: str):
    if mode == "patient-centric":
        return db.patient_records.find_one({"id": pid})
    return list(db.patients.aggregate([
        {"$match": {"id": pid}},
        {"$lookup": {"from": "encounters", "let": {"pid": "$id"},
                     "pipeline": [{"$match": {"$expr": {"$eq": [
                         "$subject.reference",
                         {"$concat": ["Patient/", "$$pid"]}]}}}],
                     "as": "encounters"}},
        {"$lookup": {"from": "observations" if mode != "time-series"
                              and mode != "bucketed" else "observation_buckets",
                     "let": {"pid": "$id"},
                     "pipeline": [{"$match": {"$expr": {"$eq": [
                         "$subject.reference" if mode == "per-type"
                         else "$patient",
                         {"$concat": ["Patient/", "$$pid"]} if mode == "per-type"
                         else "$$pid"]}}}],
                     "as": "observations"}},
    ]))


def _pick_patient_id(db, mode: str) -> str | None:
    if mode == "patient-centric":
        d = db.patient_records.find_one({}, {"id": 1})
    elif mode == "single":
        d = db.resources.find_one({"resourceType": "Patient"}, {"id": 1})
    else:
        d = db.patients.find_one({}, {"id": 1})
    return d.get("id") if d else None


def time_query(fn, runs: int = 5) -> dict:
    samples = []
    for _ in range(runs):
        s = time.perf_counter(); fn(); samples.append(time.perf_counter() - s)
    return {"min_ms": round(min(samples) * 1000, 1),
            "p50_ms": round(statistics.median(samples) * 1000, 1),
            "max_ms": round(max(samples) * 1000, 1)}


def storage_stats(db) -> dict:
    s = db.command("dbStats", scale=1)
    return {"collections": s.get("collections"),
            "data_mb": round(s.get("dataSize", 0) / (1024 * 1024), 2),
            "storage_mb": round(s.get("storageSize", 0) / (1024 * 1024), 2),
            "index_mb": round(s.get("indexSize", 0) / (1024 * 1024), 2)}


def run_benchmarks(uri: str, db_prefix: str, data_dir: Path, modes: list[str]) -> list[dict]:
    rows = []
    client = MongoClient(uri)
    for mode in modes:
        dbn = f"{db_prefix}_{mode.replace('-', '_')}"
        print(f"\n=== {mode} -> {dbn} ===")
        t_ingest = ingest(mode, uri, dbn, data_dir)
        db = client[dbn]
        pid = _pick_patient_id(db, mode)
        q_everything = time_query(lambda: _patient_everything_query(db, mode, pid)) \
            if pid else {"min_ms": None, "p50_ms": None, "max_ms": None}
        storage = storage_stats(db)
        rows.append({"mode": mode, "ingest_s": round(t_ingest, 2),
                     "everything_p50_ms": q_everything["p50_ms"],
                     "data_mb": storage["data_mb"],
                     "storage_mb": storage["storage_mb"],
                     "index_mb": storage["index_mb"]})
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--patients", type=int, default=50)
    p.add_argument("--uri", default=os.environ.get("MONGODB_URI", "mongodb://localhost:27017"))
    p.add_argument("--db-prefix", default="fhir_bench")
    p.add_argument("--data-dir", default="./bench_data")
    p.add_argument("--modes", nargs="+", choices=MODES, default=MODES)
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    args = p.parse_args()

    data_dir = Path(args.data_dir)
    regenerate(data_dir, args.patients)
    rows = run_benchmarks(args.uri, args.db_prefix, data_dir, args.modes)

    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print("\n" + tabulate(rows, headers="keys", tablefmt="github"))


if __name__ == "__main__":
    main()
