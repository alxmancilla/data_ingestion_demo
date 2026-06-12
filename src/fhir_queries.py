#!/usr/bin/env python3
"""Clinical analytics over FHIR data using MongoDB aggregation pipelines.

Assumes the 'per-type' ingestion mode (collections: patients, encounters,
observations, conditions, medicationrequests, ...). For other modes, adjust
collection names.
"""

import argparse
import json
import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()


def patient_everything(db, patient_id: str) -> dict:
    """FHIR $everything via $lookup. Aggregates a patient's full record."""
    pipeline = [
        {"$match": {"id": patient_id}},
        {"$lookup": {"from": "encounters", "let": {"pid": "$id"},
                     "pipeline": [{"$match": {"$expr": {"$eq": [
                         "$subject.reference", {"$concat": ["Patient/", "$$pid"]}]}}}],
                     "as": "encounters"}},
        {"$lookup": {"from": "conditions", "let": {"pid": "$id"},
                     "pipeline": [{"$match": {"$expr": {"$eq": [
                         "$subject.reference", {"$concat": ["Patient/", "$$pid"]}]}}}],
                     "as": "conditions"}},
        {"$lookup": {"from": "medicationrequests", "let": {"pid": "$id"},
                     "pipeline": [{"$match": {"$expr": {"$eq": [
                         "$subject.reference", {"$concat": ["Patient/", "$$pid"]}]}}}],
                     "as": "medications"}},
        {"$lookup": {"from": "observations", "let": {"pid": "$id"},
                     "pipeline": [
                         {"$match": {"$expr": {"$eq": [
                             "$subject.reference", {"$concat": ["Patient/", "$$pid"]}]}}},
                         {"$limit": 100}],
                     "as": "recent_observations"}},
        {"$project": {"_id": 0, "id": 1, "name": 1, "gender": 1, "birthDate": 1,
                      "encounter_count": {"$size": "$encounters"},
                      "condition_count": {"$size": "$conditions"},
                      "medication_count": {"$size": "$medications"},
                      "observation_sample": {"$size": "$recent_observations"}}},
    ]
    return next(iter(db.patients.aggregate(pipeline)), {})


def patient_graph_lookup(db, patient_id: str) -> dict:
    """Same as patient_everything but using $graphLookup recursive traversal
    from encounters to all linked observations."""
    pipeline = [
        {"$match": {"id": patient_id}},
        {"$graphLookup": {
            "from": "observations",
            "startWith": {"$concat": ["Patient/", "$id"]},
            "connectFromField": "subject.reference",
            "connectToField": "subject.reference",
            "as": "all_observations",
            "maxDepth": 0}},
        {"$project": {"_id": 0, "id": 1, "observations_found": {"$size": "$all_observations"}}},
    ]
    return next(iter(db.patients.aggregate(pipeline)), {})


def diabetic_cohort_high_hba1c(db, hba1c_threshold: float = 7.0, limit: int = 25) -> list[dict]:
    """Find patients with Type 2 Diabetes AND HbA1c above threshold."""
    pipeline = [
        {"$match": {"code.coding.code": "44054006"}},  # Type 2 Diabetes (SNOMED)
        {"$group": {"_id": "$subject.reference"}},
        {"$lookup": {
            "from": "observations",
            "let": {"pref": "$_id"},
            "pipeline": [
                {"$match": {"$expr": {"$and": [
                    {"$eq": ["$subject.reference", "$$pref"]},
                    {"$in": ["4548-4", "$code.coding.code"]},   # HbA1c (LOINC); code.coding is an array
                    {"$gt": ["$valueQuantity.value", hba1c_threshold]}]}}},
                {"$sort": {"effectiveDateTime": -1}},
                {"$limit": 1}],
            "as": "latest_hba1c"}},
        {"$match": {"latest_hba1c.0": {"$exists": True}}},
        {"$project": {"_id": 0, "patient_ref": "$_id",
                      "hba1c": {"$arrayElemAt": ["$latest_hba1c.valueQuantity.value", 0]},
                      "date": {"$arrayElemAt": ["$latest_hba1c.effectiveDateTime", 0]}}},
        {"$sort": {"hba1c": -1}},
        {"$limit": limit},
    ]
    return list(db.conditions.aggregate(pipeline))


def population_health_by_demographics(db) -> list[dict]:
    """Average systolic BP by gender and age bucket."""
    pipeline = [
        {"$match": {"code.coding.code": "8480-6"}},  # Systolic BP (LOINC)
        {"$lookup": {"from": "patients",
                     "let": {"pref": "$subject.reference"},
                     "pipeline": [{"$match": {"$expr": {"$eq": [
                         {"$concat": ["Patient/", "$id"]}, "$$pref"]}}}],
                     "as": "patient"}},
        {"$unwind": "$patient"},
        {"$addFields": {
            "age": {"$dateDiff": {"startDate": {"$toDate": "$patient.birthDate"},
                                  "endDate": "$$NOW", "unit": "year"}}}},
        {"$bucket": {"groupBy": "$age",
                     "boundaries": [0, 30, 45, 60, 75, 120],
                     "default": "unknown",
                     "output": {
                         "count": {"$sum": 1},
                         "avg_systolic": {"$avg": "$valueQuantity.value"},
                         "by_gender": {"$push": "$patient.gender"}}}},
    ]
    return list(db.observations.aggregate(pipeline))


def readmissions_30_day(db, limit: int = 25) -> list[dict]:
    """Patients with an inpatient encounter followed by another within 30 days,
    detected via $setWindowFields."""
    pipeline = [
        {"$match": {"class.code": "IMP", "period.start": {"$ne": None}}},
        {"$addFields": {"start": {"$toDate": "$period.start"}}},
        {"$sort": {"subject.reference": 1, "start": 1}},
        {"$setWindowFields": {
            "partitionBy": "$subject.reference",
            "sortBy": {"start": 1},
            "output": {"prev_start": {
                "$shift": {"output": "$start", "by": -1, "default": None}}}}},
        {"$match": {"prev_start": {"$ne": None}}},
        {"$addFields": {"days_since_prev": {
            "$dateDiff": {"startDate": "$prev_start", "endDate": "$start", "unit": "day"}}}},
        {"$match": {"days_since_prev": {"$lte": 30}}},
        {"$project": {"_id": 0, "patient": "$subject.reference",
                      "current": "$start", "prev": "$prev_start",
                      "days_since_prev": 1}},
        {"$limit": limit},
    ]
    return list(db.encounters.aggregate(pipeline))


def medication_trends(db, top_n: int = 10) -> list[dict]:
    """Top prescribed medications and unique-patient counts."""
    pipeline = [
        {"$group": {"_id": "$medicationCodeableConcept.text",
                    "prescriptions": {"$sum": 1},
                    "patients": {"$addToSet": "$subject.reference"}}},
        {"$project": {"_id": 0, "medication": "$_id", "prescriptions": 1,
                      "unique_patients": {"$size": "$patients"}}},
        {"$sort": {"prescriptions": -1}},
        {"$limit": top_n},
    ]
    return list(db.medicationrequests.aggregate(pipeline))


QUERIES = {"patient-everything": lambda db, a: patient_everything(db, a.patient_id),
           "patient-graph": lambda db, a: patient_graph_lookup(db, a.patient_id),
           "diabetic-cohort": lambda db, a: diabetic_cohort_high_hba1c(db, a.hba1c, a.limit),
           "population-health": lambda db, a: population_health_by_demographics(db),
           "readmissions": lambda db, a: readmissions_30_day(db, a.limit),
           "medication-trends": lambda db, a: medication_trends(db, a.limit)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("query", choices=list(QUERIES))
    p.add_argument("--uri", default=os.environ.get("MONGODB_URI", "mongodb://localhost:27017"))
    p.add_argument("--database", default=os.environ.get("FHIR_DB", "fhir_poc"))
    p.add_argument("--patient-id", default=None)
    p.add_argument("--hba1c", type=float, default=7.0)
    p.add_argument("--limit", type=int, default=25)
    args = p.parse_args()

    db = MongoClient(args.uri)[args.database]
    result = QUERIES[args.query](db, args)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
