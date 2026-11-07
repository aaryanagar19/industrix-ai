#!/usr/bin/env bash
# One-time local setup (SQLite). Usage: ./scripts/setup_local.sh
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements-dev.txt
(cd backend && python -m app.seed --reset)       # migrations + demo data (uses committed model artifacts)
(cd frontend && npm install)
echo "Done. Run ./scripts/run_dev.sh"
