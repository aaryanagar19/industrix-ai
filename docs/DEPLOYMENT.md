# Deployment Guide

> **Status: nothing has been deployed by the authors of this package.** Docker files, CI and the hosting notes below were written but **not executed** in the build environment (no Docker daemon, no cloud accounts). Verify each step.

## Local (verified): SQLite
```bash
./scripts/setup_local.sh      # venv, deps, migrations + seed, npm install
./scripts/run_dev.sh          # API :8000 (docs at /docs) · UI :5173
```

## Docker Compose (PostgreSQL) — unverified
```bash
cp .env.example .env          # set POSTGRES_PASSWORD and SECRET_KEY
docker compose up --build     # UI http://localhost:8080 · API http://localhost:8000/docs
```
The backend entrypoint runs `alembic upgrade head`, trains models only if artifacts are missing, seeds when `SEED_ON_START=true`, then starts uvicorn. Set `SEED_ON_START=false` for real deployments.

## Backend on Render / Railway (suggested)
1. Create managed PostgreSQL; copy its URL as `DATABASE_URL` (`postgresql+psycopg2://…`).
2. Deploy `backend/Dockerfile` with the repo root as build context. Env: `DATABASE_URL`, `SECRET_KEY`, `CORS_ORIGINS=https://<your-frontend>`, `SIMULATOR_AUTOSTART=true|false`, `SEED_ON_START=true` on first boot only.
3. Use ≥ 1 GB RAM (TensorFlow + SHAP). Run a single instance (the simulator and in-memory rate limiter are per-process).
4. Health check: `GET /api/health`.

## Frontend on Vercel
- Root directory `frontend`, build `npm run build`, output `dist`, env `VITE_API_URL=https://<backend>`.
- WebSockets connect to `VITE_API_URL` (wss). Add an SPA rewrite `/(.*) -> /index.html`.

## Security checklist before exposing publicly
Change all demo passwords/`SECRET_KEY`; set `ALLOW_SELF_REGISTER=false`; restrict `CORS_ORIGINS`; use HTTPS; back up the database (`scripts/backup_db.sh`); review `docs/KNOWN_LIMITATIONS.md`.
