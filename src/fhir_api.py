#!/usr/bin/env python3
"""Subset of the FHIR R4 REST Search API backed by MongoDB.

Assumes per-type ingestion mode (patients, encounters, observations, conditions,
medicationrequests, ...). Returns FHIR-shaped Bundle responses.

Run:
  uvicorn src.fhir_api:app --reload
"""

import os
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from pymongo import MongoClient

load_dotenv()
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.environ.get("FHIR_DB", "fhir_poc")

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]
app = FastAPI(title="FHIR R4 Search API (MongoDB demo)",
              description=__doc__, version="0.1.0")

DATE_PREFIXES = {"eq": "$eq", "ne": "$ne", "gt": "$gt", "lt": "$lt",
                 "ge": "$gte", "le": "$lte"}


def _parse_date_param(value: str) -> dict:
    """FHIR date search supports prefixes: ge2024-01-01, le2024-12-31, etc."""
    prefix, raw = "eq", value
    if len(value) >= 2 and value[:2] in DATE_PREFIXES:
        prefix, raw = value[:2], value[2:]
    return {DATE_PREFIXES[prefix]: raw}


def _parse_token(value: str) -> dict:
    """FHIR token search: 'system|code' or just 'code'."""
    if "|" in value:
        system, code = value.split("|", 1)
        clauses = []
        if system:
            clauses.append({"coding.system": system})
        if code:
            clauses.append({"coding.code": code})
        return {"$and": clauses} if len(clauses) > 1 else clauses[0]
    return {"coding.code": value}


def _bundle(request: Request, resource_type: str, docs: list[dict],
            total: int | None = None) -> dict:
    base = str(request.base_url).rstrip("/")
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": total if total is not None else len(docs),
        "link": [{"relation": "self",
                  "url": f"{base}{request.url.path}?{urlencode(request.query_params)}"}],
        "entry": [{"fullUrl": f"{base}/{resource_type}/{d.get('id')}",
                   "resource": d} for d in docs],
    }


def _project_no_id(d: dict) -> dict:
    d.pop("_id", None); return d


@app.get("/Patient/{patient_id}")
def read_patient(patient_id: str):
    doc = db.patients.find_one({"id": patient_id})
    if not doc:
        raise HTTPException(404, f"Patient/{patient_id} not found")
    return _project_no_id(doc)


@app.get("/Patient")
def search_patient(request: Request,
                   name: str | None = None, family: str | None = None,
                   given: str | None = None, gender: str | None = None,
                   birthdate: str | None = None,
                   _count: int = Query(20, ge=1, le=200)):
    q: dict[str, Any] = {}
    if family: q["name.family"] = family
    if given: q["name.given"] = given
    if name: q["$or"] = [{"name.family": {"$regex": name, "$options": "i"}},
                         {"name.given": {"$regex": name, "$options": "i"}}]
    if gender: q["gender"] = gender
    if birthdate: q["birthDate"] = _parse_date_param(birthdate)
    docs = [_project_no_id(d) for d in db.patients.find(q).limit(_count)]
    return _bundle(request, "Patient", docs)


@app.get("/Observation")
def search_observation(request: Request,
                       subject: str | None = None, patient: str | None = None,
                       code: str | None = None, category: str | None = None,
                       date: list[str] | None = Query(None),
                       _count: int = Query(20, ge=1, le=200)):
    q: dict[str, Any] = {}
    ref = subject or (f"Patient/{patient}" if patient else None)
    if ref: q["subject.reference"] = ref
    if code: q.update({"code." + k: v for k, v in _parse_token(code).items()})
    if category: q["category.coding.code"] = category
    if date:
        q["effectiveDateTime"] = {}
        for d in date:
            q["effectiveDateTime"].update(_parse_date_param(d))
    docs = [_project_no_id(d) for d in db.observations.find(q).limit(_count)]
    return _bundle(request, "Observation", docs)


@app.get("/Encounter")
def search_encounter(request: Request,
                     subject: str | None = None, patient: str | None = None,
                     status: str | None = None, type: str | None = None,
                     date: list[str] | None = Query(None),
                     _count: int = Query(20, ge=1, le=200)):
    q: dict[str, Any] = {}
    ref = subject or (f"Patient/{patient}" if patient else None)
    if ref: q["subject.reference"] = ref
    if status: q["status"] = status
    if type: q["class.code"] = type
    if date:
        q["period.start"] = {}
        for d in date:
            q["period.start"].update(_parse_date_param(d))
    docs = [_project_no_id(d) for d in db.encounters.find(q).limit(_count)]
    return _bundle(request, "Encounter", docs)


@app.get("/Condition")
def search_condition(request: Request,
                     subject: str | None = None, patient: str | None = None,
                     code: str | None = None,
                     _count: int = Query(20, ge=1, le=200)):
    q: dict[str, Any] = {}
    ref = subject or (f"Patient/{patient}" if patient else None)
    if ref: q["subject.reference"] = ref
    if code: q.update({"code." + k: v for k, v in _parse_token(code).items()})
    docs = [_project_no_id(d) for d in db.conditions.find(q).limit(_count)]
    return _bundle(request, "Condition", docs)


@app.get("/Patient/{patient_id}/$everything")
def patient_everything(request: Request, patient_id: str):
    if not db.patients.find_one({"id": patient_id}, {"_id": 1}):
        raise HTTPException(404, f"Patient/{patient_id} not found")
    pref = f"Patient/{patient_id}"
    entries: list[dict] = []
    for coll_name, ref_field in [("encounters", "subject.reference"),
                                  ("conditions", "subject.reference"),
                                  ("observations", "subject.reference"),
                                  ("medicationrequests", "subject.reference"),
                                  ("procedures", "subject.reference"),
                                  ("immunizations", "patient.reference"),
                                  ("allergyintolerances", "patient.reference"),
                                  ("documentreferences", "subject.reference")]:
        for d in db[coll_name].find({ref_field: pref}):
            entries.append(_project_no_id(d))
    patient = _project_no_id(db.patients.find_one({"id": patient_id}))
    return _bundle(request, "Patient", [patient] + entries, total=len(entries) + 1)
