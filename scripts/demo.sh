#!/usr/bin/env bash
# End-to-end FHIR on MongoDB Atlas demo walkthrough.
#
# Prereqs (one-time):
#   cp .env.example .env  &&  edit MONGODB_URI / VOYAGE_API_KEY / GROVE_API_KEY
#   pip install -r requirements.txt
#   python src/fhir_data_generator.py --patients 200       # smaller for demos
#   python src/fhir_data_ingestor.py --mode per-type --drop
#   python src/create_indexes.py all
#
# Then run this script. Each step pauses for [Enter] so you can narrate.
set -euo pipefail

PY=${PYTHON:-python}
PAUSE=${PAUSE:-1}

section() {
    echo
    echo "==============================================================="
    echo "  $1"
    echo "==============================================================="
    [ "$PAUSE" = "1" ] && read -r -p "  press [Enter] to run..." _ || true
}

run() { echo "  $ $*"; eval "$@"; }

# --- 0. Verify setup --------------------------------------------------------
section "0. Atlas health check"
run "$PY src/atlas_check.py"

# --- 1. Pick demo patients --------------------------------------------------
section "1. Sample patient IDs (used by later steps)"
run "$PY src/sample_ids.py"
DIABETIC=$($PY src/sample_ids.py --profile diabetic)
READMIT=$($PY src/sample_ids.py --profile readmitted)
NOTES=$($PY src/sample_ids.py --profile rich-notes)
echo
echo "  selected: diabetic=$DIABETIC  readmitted=$READMIT  rich-notes=$NOTES"

# --- 2. Clinical analytics --------------------------------------------------
section "2. \$everything via \$lookup (single-query patient record)"
run "$PY src/fhir_queries.py patient-everything --patient-id $DIABETIC"

section "3. Diabetic cohort with elevated HbA1c"
run "$PY src/fhir_queries.py diabetic-cohort --hba1c 7.5 --limit 10"

section "4. 30-day readmissions via \$setWindowFields"
run "$PY src/fhir_queries.py readmissions --limit 10"

section "5. Population health: avg systolic BP by age + gender"
run "$PY src/fhir_queries.py population-health"

# --- 3. Atlas Search --------------------------------------------------------
section "6. Atlas Search: full-text + clinical synonyms (try 'MI', 'HTN', 'T2DM')"
run "$PY src/fhir_search.py notes --query \"MI\" --limit 5"

section "7. Fuzzy patient name (typo tolerant)"
run "$PY src/fhir_search.py fuzzy-name --query \"Jhonson\" --limit 5"

section "8. Faceted search: gender + state counts"
run "$PY src/fhir_search.py facets --query '*'"

# --- 4. Vector + Hybrid Search ----------------------------------------------
if [ -n "${VOYAGE_API_KEY:-}" ]; then
    section "9. Semantic search (Voyage embeddings + Vector Search)"
    run "$PY src/fhir_vector_search.py search --query \"patient with breathing issues\" --k 5"

    section "10. Hybrid Search (\$rankFusion: lexical + semantic + synonyms)"
    run "$PY src/fhir_search.py hybrid --query \"shortness of breath after MI\" --limit 5"
else
    echo
    echo "  skipping vector + hybrid search (VOYAGE_API_KEY not set)"
fi

# --- 5. RAG -----------------------------------------------------------------
if [ -n "${VOYAGE_API_KEY:-}" ] && [ -n "${GROVE_API_KEY:-}" ]; then
    section "11. RAG: grounded clinical Q&A"
    run "$PY src/fhir_vector_search.py ask --patient-ref Patient/$NOTES \\
            --question \"What conditions has this patient been treated for?\" --k 5"
else
    echo
    echo "  skipping RAG (VOYAGE_API_KEY / GROVE_API_KEY not set)"
fi

# --- 6. Next steps ----------------------------------------------------------
section "12. Real-time alerts (run in two terminals)"
cat <<EOF
  Terminal A:  $PY src/fhir_subscriptions.py watch
  Terminal B:  $PY src/fhir_subscriptions.py simulate -n 5 \\
                   --patient-ref Patient/$DIABETIC
EOF

section "13. FHIR REST API"
cat <<EOF
  uvicorn src.fhir_api:app --reload
  curl 'http://localhost:8000/Patient/$DIABETIC/\$everything'
EOF

echo
echo "Demo complete."
