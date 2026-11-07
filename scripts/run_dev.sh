#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true
(cd backend && uvicorn app.main:app --reload --port 8000) &
(cd frontend && npm run dev)
wait
