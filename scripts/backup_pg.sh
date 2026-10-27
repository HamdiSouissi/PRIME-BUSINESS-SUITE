#!/usr/bin/env bash
# Sauvegarde PostgreSQL (production). Usage : backup_pg.sh <sortie.dump>
# Variables : PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE (ou DATABASE_URL)
set -euo pipefail

CIBLE="${1:?Chemin de sortie requis (ex. backups/pbs-$(date +%F).dump)}"
mkdir -p "$(dirname "$CIBLE")"

if [ -n "${DATABASE_URL:-}" ]; then
  pg_dump "$DATABASE_URL" -Fc -f "$CIBLE"
else
  export PGHOST="${PGHOST:-localhost}" PGPORT="${PGPORT:-5432}"
  export PGDATABASE="${PGDATABASE:?PGDATABASE requis}"
  pg_dump -Fc -f "$CIBLE"
fi
echo "Sauvegarde OK : $CIBLE ($(du -h "$CIBLE" | cut -f1))"
echo "Restauration : pg_restore -d \$PGDATABASE --clean --if-exists $CIBLE"
