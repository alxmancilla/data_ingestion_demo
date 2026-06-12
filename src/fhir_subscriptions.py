#!/usr/bin/env python3
"""Real-time clinical alerts via MongoDB Change Streams.

Emulates a FHIR Subscription channel: tails the observations collection and
emits an alert whenever a newly inserted Observation crosses a clinically
relevant threshold (HbA1c, BP, HR, SpO2, glucose, temperature, etc.).

Run this in the foreground in one terminal; in another terminal, trigger
alerts by inserting test observations (see --simulate).
"""

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import OperationFailure

load_dotenv()

# LOINC code -> (label, low alert, high alert, unit).
THRESHOLDS: dict[str, tuple[str, float | None, float | None, str]] = {
    "4548-4":  ("HbA1c",            None, 9.0,   "%"),
    "2339-0":  ("Glucose",          60.0, 250.0, "mg/dL"),
    "8480-6":  ("Systolic BP",      90.0, 180.0, "mmHg"),
    "8462-4":  ("Diastolic BP",     50.0, 120.0, "mmHg"),
    "8867-4":  ("Heart rate",       40.0, 120.0, "bpm"),
    "2708-6":  ("Oxygen saturation", 88.0, None, "%"),
    "8310-5":  ("Temperature",      None, 38.5,  "C"),
    "9279-1":  ("Respiratory rate", None, 24.0,  "/min"),
}


def _evaluate(obs: dict) -> tuple[str, float, str] | None:
    code = (obs.get("code", {}).get("coding") or [{}])[0].get("code")
    rule = THRESHOLDS.get(code)
    if not rule:
        return None
    label, low, high, _unit = rule
    val = (obs.get("valueQuantity") or {}).get("value")
    if val is None:
        return None
    if low is not None and val < low:
        return (f"LOW {label}", val, f"< {low}")
    if high is not None and val > high:
        return (f"HIGH {label}", val, f"> {high}")
    return None


def _emit(obs: dict, severity: str, value: float, rule: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    patient = obs.get("subject", {}).get("reference", "?")
    obs_id = obs.get("id", "?")
    print(f"\033[1;31m[{ts}] ALERT\033[0m  {severity}: {value} {rule}  "
          f"patient={patient}  observation={obs_id}", flush=True)


def watch(db) -> None:
    print(f"\u2713 Watching {db.name}.observations for clinical alerts. Ctrl+C to stop.\n")
    print("Monitored LOINC codes:")
    for code, (label, low, high, unit) in THRESHOLDS.items():
        rng = []
        if low is not None: rng.append(f"< {low}")
        if high is not None: rng.append(f"> {high}")
        print(f"  {code:<8} {label:<20} alert when {' or '.join(rng)} {unit}")
    print()
    try:
        with db.observations.watch([{"$match": {"operationType": "insert"}}],
                                   full_document="updateLookup") as stream:
            for change in stream:
                doc = change.get("fullDocument") or {}
                hit = _evaluate(doc)
                if hit:
                    _emit(doc, *hit)
    except OperationFailure as e:
        sys.exit(f"\u2717 Change Streams require a replica set or Atlas: {e}")
    except KeyboardInterrupt:
        print("\nStopped.")


def simulate(db, n: int = 5, patient_ref: str | None = None,
             interval: float = 1.0) -> None:
    """Insert n synthetic abnormal observations to trigger alerts."""
    if not patient_ref:
        first = db.patients.find_one({}, {"id": 1})
        if not first:
            sys.exit("\u2717 No patients found; ingest data first.")
        patient_ref = f"Patient/{first['id']}"

    scenarios = [
        ("4548-4", 11.2, "%"),       # HbA1c crisis
        ("2339-0", 320.0, "mg/dL"),  # Hyperglycemia
        ("8480-6", 195.0, "mmHg"),   # Hypertensive crisis
        ("8867-4", 38.0, "bpm"),     # Bradycardia
        ("2708-6", 84.0, "%"),       # Hypoxia
    ]
    print(f"Inserting {n} abnormal observations for {patient_ref} "
          f"(interval={interval}s)...\n")
    for i in range(n):
        code, value, unit = scenarios[i % len(scenarios)]
        label = THRESHOLDS[code][0]
        obs = {
            "_id": str(uuid.uuid4()),
            "resourceType": "Observation",
            "id": str(uuid.uuid4()),
            "status": "final",
            "subject": {"reference": patient_ref},
            "code": {"coding": [{"system": "http://loinc.org", "code": code,
                                  "display": label}]},
            "valueQuantity": {"value": value, "unit": unit,
                              "system": "http://unitsofmeasure.org"},
            "effectiveDateTime": datetime.now(timezone.utc).isoformat(),
        }
        db.observations.insert_one(obs)
        print(f"  \u2192 inserted {label}={value}{unit}")
        time.sleep(interval)
    print(f"\n\u2713 done. Check the watcher terminal for {n} alerts.")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("watch", help="Tail observations and print alerts (run in foreground)")
    s = sub.add_parser("simulate", help="Insert N abnormal observations to trigger alerts")
    s.add_argument("-n", type=int, default=5)
    s.add_argument("--patient-ref", help="Default: first patient in the DB")
    s.add_argument("--interval", type=float, default=1.0)
    for sp in (sub.choices["watch"], sub.choices["simulate"]):
        sp.add_argument("--uri", default=os.environ.get("MONGODB_URI",
                                                         "mongodb://localhost:27017"))
        sp.add_argument("--database", default=os.environ.get("FHIR_DB", "fhir_poc"))
    args = p.parse_args()

    db = MongoClient(args.uri)[args.database]
    if args.cmd == "watch":
        watch(db)
    else:
        simulate(db, n=args.n, patient_ref=args.patient_ref, interval=args.interval)


if __name__ == "__main__":
    main()
