#!/usr/bin/env bash
# Regenerate synthetic data and retrain ALL models. Add --fast for a quick smoke run.
set -euo pipefail
cd "$(dirname "$0")/../backend"
python -m app.ml.training.train_all "$@"
