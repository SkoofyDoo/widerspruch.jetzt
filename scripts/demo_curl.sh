#!/usr/bin/env bash
# Demo script for WIDERSPRUCH.JETZT API
set -euo pipefail
BASE="${APP_URL:-http://127.0.0.1:8008}"

echo "== Health =="
curl -sS "$BASE/health" | python -m json.tool || curl -sS "$BASE/health"

echo
echo "== RAG search =="
curl -sS "$BASE/search?q=Akteneinsicht&k=3" | python -m json.tool || true

echo
echo "== Preview workflow =="
curl -sS -X POST "$BASE/widerspruch/workflow?preview=1" \
  -H "Content-Type: application/json" \
  --data-binary @samples/api_request_example.json || true

echo
echo "Open UI: $BASE/ui/"
