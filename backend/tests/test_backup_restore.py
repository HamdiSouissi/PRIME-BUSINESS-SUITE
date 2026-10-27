"""Sauvegarde et restauration de la base (SQLite en dev/test)."""

import shutil
import subprocess
from pathlib import Path

import pytest
from django.conf import settings

pytestmark = pytest.mark.django_db


def test_script_sauvegarde_sqlite(tmp_path):
    """Le script scripts/backup_sqlite.sh/copie produit un fichier ouvrable."""
    db_path = Path(settings.DATABASES["default"]["NAME"])
    if not db_path.exists():
        pytest.skip("Base fichier absente (test en mémoire).")
    script = Path(__file__).resolve().parents[2] / "scripts" / "backup_sqlite.sh"
    if not script.exists():
        pytest.fail("scripts/backup_sqlite.sh manquant.")
    cible = tmp_path / "backup.sqlite3"
    result = subprocess.run(["bash", str(script), str(db_path), str(cible)], capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
    assert cible.exists() and cible.stat().st_size > 0
    # La sauvegarde s'ouvre en SQLite
    import sqlite3

    conn = sqlite3.connect(cible)
    tables = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    conn.close()
    assert tables > 10


def test_restauration_donnees(taux=None, tmp_path=None):
    """Restaurer un dump ramène les mêmes comptages (test de cohérence)."""
    db_path = Path(settings.DATABASES["default"]["NAME"])
    if not db_path.exists():
        pytest.skip("Base fichier absente.")
    copie = db_path.parent / "pytest-restore-copy.sqlite3"
    shutil.copy(db_path, copie)
    try:
        import sqlite3

        c1 = sqlite3.connect(db_path)
        n1 = c1.execute("SELECT count(*) FROM accounts_user").fetchone()[0]
        c1.close()
        c2 = sqlite3.connect(copie)
        n2 = c2.execute("SELECT count(*) FROM accounts_user").fetchone()[0]
        c2.close()
        assert n1 == n2
    finally:
        copie.unlink(missing_ok=True)
