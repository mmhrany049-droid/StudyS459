#!/usr/bin/env bash
# Starts the backend (uvicorn) on :8000 and the Vite dev server on :5173.
set -e
cd "$(dirname "$0")"
PY=../.venv/bin/python
if [ ! -x "$PY" ]; then PY=python3; fi
export STUDYS459_DB_PATH="${STUDYS459_DB_PATH:-$(pwd)/data/studys459.db}"
"$PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND=$!
trap "kill $BACKEND 2>/dev/null || true" EXIT
cd ../frontend && npm run dev
