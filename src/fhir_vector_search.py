#!/usr/bin/env python3
"""Vector search + RAG over FHIR clinical notes.

Embeddings: Voyage AI 'voyage-4' (1024-dim, set VOYAGE_API_KEY)
Completions: OpenAI Responses API via Grove gateway (set GROVE_API_KEY)

Subcommands:
  embed   - Compute Voyage embeddings for DocumentReference.content.attachment.data
  search  - Semantic search returning top-k matching documents
  ask     - RAG: retrieve top-k docs and ask the LLM a grounded question
"""

import argparse
import json
import os
import sys
from typing import Iterable

import httpx
import voyageai
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from tqdm import tqdm

load_dotenv()

VECTOR_INDEX = "documents_vector"
VOYAGE_MODEL = "voyage-4"
VOYAGE_DIMS = 1024
GROVE_URL = ("https://grove-gateway-prod.azure-api.net/"
             "grove-foundry-prod/openai/v1/responses")
GROVE_MODEL = "gpt-5.5"


def _voyage() -> voyageai.Client:
    if not os.environ.get("VOYAGE_API_KEY"):
        sys.exit("VOYAGE_API_KEY not set")
    return voyageai.Client()


def _extract_text(doc: dict) -> str:
    parts = []
    for c in doc.get("content", []) or []:
        att = c.get("attachment") or {}
        if att.get("data"):
            parts.append(str(att["data"]))
    return "\n".join(parts).strip()


def embed_documents(db, batch_size: int = 64, limit: int | None = None) -> int:
    """Embed all DocumentReference docs that don't yet have an 'embedding' field."""
    vo = _voyage()
    coll = db.documentreferences
    cursor = coll.find({"embedding": {"$exists": False}},
                       {"id": 1, "content": 1}).limit(limit or 0)
    pending: list[tuple] = []
    written = 0

    def flush():
        nonlocal written
        if not pending:
            return
        texts = [t for _, t in pending]
        result = vo.embed(texts, model=VOYAGE_MODEL, input_type="document")
        ops = [UpdateOne({"_id": _id}, {"$set": {"embedding": emb}})
               for (_id, _), emb in zip(pending, result.embeddings)]
        coll.bulk_write(ops, ordered=False)
        written += len(ops)
        pending.clear()

    for d in tqdm(cursor, desc="embedding"):
        text = _extract_text(d)
        if text:
            pending.append((d["_id"], text))
            if len(pending) >= batch_size:
                flush()
    flush()
    print(f"\u2713 embedded {written:,} DocumentReference records")
    return written


def semantic_search(db, query: str, k: int = 5,
                    patient_ref: str | None = None) -> list[dict]:
    """$vectorSearch over DocumentReference.embedding."""
    vo = _voyage()
    qvec = vo.embed([query], model=VOYAGE_MODEL,
                    input_type="query").embeddings[0]
    stage: dict = {
        "$vectorSearch": {
            "index": VECTOR_INDEX,
            "path": "embedding",
            "queryVector": qvec,
            "numCandidates": max(50, k * 10),
            "limit": k,
        }
    }
    if patient_ref:
        stage["$vectorSearch"]["filter"] = {"subject.reference": patient_ref}
    pipeline = [
        stage,
        {"$project": {"_id": 0, "id": 1, "subject": 1, "date": 1,
                      "text": {"$first": "$content.attachment.data"},
                      "score": {"$meta": "vectorSearchScore"}}},
    ]
    return list(db.documentreferences.aggregate(pipeline))


def _grove_complete(prompt: str) -> str:
    api_key = os.environ.get("GROVE_API_KEY")
    if not api_key:
        sys.exit("GROVE_API_KEY not set")
    r = httpx.post(GROVE_URL,
                   headers={"Content-Type": "application/json",
                            "api-key": api_key},
                   json={"model": GROVE_MODEL, "input": prompt},
                   timeout=60.0)
    r.raise_for_status()
    payload = r.json()
    # Responses API: prefer top-level output_text if present
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    chunks: list[str] = []
    for item in payload.get("output", []) or []:
        for c in item.get("content", []) or []:
            t = c.get("text")
            if isinstance(t, str):
                chunks.append(t)
            elif isinstance(t, dict) and "value" in t:
                chunks.append(t["value"])
    return "\n".join(chunks) or json.dumps(payload)[:2000]


def ask(db, question: str, k: int = 5,
        patient_ref: str | None = None) -> dict:
    """Retrieve top-k relevant notes and pass them to the LLM as grounding."""
    hits = semantic_search(db, question, k=k, patient_ref=patient_ref)
    context = "\n\n".join(
        f"[doc {i+1} | patient={h.get('subject',{}).get('reference')} "
        f"| date={h.get('date')}]\n{h.get('text','')}" for i, h in enumerate(hits))
    prompt = (
        "You are a clinical assistant. Answer the question using ONLY the "
        "provided FHIR DocumentReference notes. Cite documents as [doc N]. "
        "If the answer is not present, say so.\n\n"
        f"Question: {question}\n\nContext:\n{context}\n\nAnswer:")
    return {"answer": _grove_complete(prompt),
            "sources": [{"id": h.get("id"), "subject": h.get("subject"),
                         "score": h.get("score")} for h in hits]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("embed").add_argument("--limit", type=int, default=None)
    s = sub.add_parser("search"); s.add_argument("--query", required=True)
    s.add_argument("--k", type=int, default=5); s.add_argument("--patient-ref")
    a = sub.add_parser("ask"); a.add_argument("--question", required=True)
    a.add_argument("--k", type=int, default=5); a.add_argument("--patient-ref")
    for sp in (sub.choices["embed"], sub.choices["search"], sub.choices["ask"]):
        sp.add_argument("--uri", default=os.environ.get("MONGODB_URI", "mongodb://localhost:27017"))
        sp.add_argument("--database", default=os.environ.get("FHIR_DB", "fhir_poc"))
    args = p.parse_args()
    db = MongoClient(args.uri)[args.database]
    if args.cmd == "embed":
        embed_documents(db, limit=args.limit)
    elif args.cmd == "search":
        print(json.dumps(semantic_search(db, args.query, args.k, args.patient_ref),
                         indent=2, default=str))
    else:
        print(json.dumps(ask(db, args.question, args.k, args.patient_ref),
                         indent=2, default=str))


if __name__ == "__main__":
    main()
