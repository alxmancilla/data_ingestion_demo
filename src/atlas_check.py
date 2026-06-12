#!/usr/bin/env python3
"""Pre-flight check for the FHIR Atlas demo.

Reports:
  - whether the connection is to MongoDB Atlas vs a local/self-hosted mongod
  - server version, replica set, and shard topology
  - per-type collection presence and document counts
  - Atlas Search / Vector Search indexes and their build status
  - which demo sections (READMEsections 3-8) are ready to run

Exits 0 even if some features are unavailable; this is a diagnostic, not a gate.
"""

import argparse
import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError

load_dotenv()

EXPECTED_COLLS = ["patients", "encounters", "observations", "conditions",
                  "medicationrequests", "procedures", "immunizations",
                  "allergyintolerances", "documentreferences",
                  "diagnosticreports", "careplans"]
SEARCH_INDEXES = {"patients": ["patients_search"],
                  "documentreferences": ["documents_text", "documents_vector"]}


def _is_atlas(uri: str, hello: dict) -> bool:
    if "mongodb.net" in uri or "+srv" in uri:
        return True
    return bool(hello.get("setName") and hello.get("hosts"))


def _check_topology(client) -> dict:
    admin = client.admin
    return {"build": admin.command("buildInfo"), "hello": admin.command("hello")}


def _list_search_indexes(coll) -> list[dict]:
    try:
        return list(coll.list_search_indexes())
    except (OperationFailure, PyMongoError):
        return []


def _print_section(title: str) -> None:
    print(f"\n\033[1m{title}\033[0m")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--uri", default=os.environ.get("MONGODB_URI", "mongodb://localhost:27017"))
    p.add_argument("--database", default=os.environ.get("FHIR_DB", "fhir_poc"))
    args = p.parse_args()

    try:
        client = MongoClient(args.uri, serverSelectionTimeoutMS=5000)
        topo = _check_topology(client)
    except PyMongoError as e:
        sys.exit(f"\u2717 cannot connect to {args.uri}: {e}")

    is_atlas = _is_atlas(args.uri, topo["hello"])
    db = client[args.database]

    _print_section("Connection")
    print(f"  database         : {args.database}")
    print(f"  server version   : {topo['build'].get('version', '?')}")
    print(f"  deployment       : {'Atlas / replica set' if is_atlas else 'standalone or local'}")
    if topo["hello"].get("setName"):
        print(f"  replica set      : {topo['hello']['setName']}")
    if topo["hello"].get("msg") == "isdbgrid":
        print("  sharding         : enabled (mongos)")

    _print_section("Collections (per-type ingestion)")
    existing = set(db.list_collection_names())
    missing = []
    for name in EXPECTED_COLLS:
        if name in existing:
            count = db[name].estimated_document_count()
            print(f"  \u2713 {name:<22} {count:>10,} docs")
        else:
            missing.append(name)
            print(f"  - {name:<22} missing")

    _print_section("Atlas Search / Vector Search indexes")
    search_status: dict[str, str] = {}
    if not is_atlas:
        print("  skipped (not connected to Atlas)")
    else:
        for coll_name, expected in SEARCH_INDEXES.items():
            if coll_name not in existing:
                continue
            indexes = {i["name"]: i for i in _list_search_indexes(db[coll_name])}
            for name in expected:
                if name in indexes:
                    status = indexes[name].get("status", "?")
                    queryable = indexes[name].get("queryable", False)
                    flag = "\u2713" if queryable else "\u23f3"
                    print(f"  {flag} {coll_name}.{name:<20} status={status} queryable={queryable}")
                    search_status[name] = status
                else:
                    print(f"  - {coll_name}.{name:<20} not created")

    _print_section("Embeddings")
    if "documentreferences" in existing:
        embedded = db.documentreferences.count_documents({"embedding": {"$exists": True}})
        total = db.documentreferences.estimated_document_count()
        print(f"  documentreferences with embeddings: {embedded:,} / {total:,}")
    else:
        print("  documentreferences collection missing")

    _print_section("Demo readiness")
    rows = [
        ("\u00a73 create_indexes",     "patients" in existing,
         "run per-type ingest first" if "patients" not in existing else ""),
        ("\u00a74 fhir_queries",       not missing, ", ".join(missing) if missing else ""),
        ("\u00a75 atlas-search",       is_atlas and search_status.get("documents_text") == "READY",
         "" if is_atlas else "Atlas required"),
        ("\u00a76 vector-search",      is_atlas and search_status.get("documents_vector") == "READY"
                                       and bool(os.environ.get("VOYAGE_API_KEY")),
         "missing VOYAGE_API_KEY" if not os.environ.get("VOYAGE_API_KEY") else ""),
        ("\u00a76 rag-ask",            bool(os.environ.get("GROVE_API_KEY")),
         "missing GROVE_API_KEY" if not os.environ.get("GROVE_API_KEY") else ""),
        ("\u00a77 fhir_api",           not missing, ""),
        ("\u00a78 benchmarks",         True, ""),
    ]
    for label, ready, note in rows:
        flag = "\u2713" if ready else "\u2717"
        suffix = f"  ({note})" if note else ""
        print(f"  {flag} {label}{suffix}")


if __name__ == "__main__":
    main()
