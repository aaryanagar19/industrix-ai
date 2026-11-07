#!/bin/sh
set -e
echo "[entrypoint] running migrations"
alembic upgrade head
if [ ! -f "$MODELS_DIR/risk_model.joblib" ]; then
  echo "[entrypoint] no trained models found - training (this takes a few minutes)"
  python -m app.ml.training.train_all
fi
if [ "${SEED_ON_START:-true}" = "true" ]; then
  python -c "from app.seed import seed; print(seed())"
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
