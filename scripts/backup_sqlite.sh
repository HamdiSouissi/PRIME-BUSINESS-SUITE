#!/usr/bin/env bash
# Sauvegarde SQLite (développement). Usage : backup_sqlite.sh <db.sqlite3> <sortie>
# En production PostgreSQL, utiliser scripts/backup_pg.sh (pg_dump).
set -euo pipefail

SOURCE="${1:?Chemin de la base SQLite requis}"
CIBLE="${2:?Chemin de sortie requis}"

mkdir -p "$(dirname "$CIBLE")"
# Copie cohérente via l'API de sauvegarde SQLite (sûre même base ouverte)
python3 - "$SOURCE" "$CIBLE" <<'PY'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
source = sqlite3.connect(src)
dest = sqlite3.connect(dst)
source.backup(dest)
dest.close()
source.close()
print(f"Sauvegarde OK : {dst}")
PY
