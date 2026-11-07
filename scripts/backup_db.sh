#!/usr/bin/env bash
# PostgreSQL backup:  DATABASE_URL=postgresql://... ./scripts/backup_db.sh   (SQLite: just copy industrix.db while the app is stopped)
set -euo pipefail
: "${DATABASE_URL:?}"
mkdir -p backups
pg_dump "${DATABASE_URL/+psycopg2/}" -Fc -f "backups/industrix_$(date +%Y%m%d_%H%M%S).dump"
