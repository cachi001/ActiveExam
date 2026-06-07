"""Test de la migracion 0007 (C-56): upgrade y downgrade.

Verifica que:
- upgrade hasta 0007 (rama PRINCIPAL, requiere TimescaleDB) crea las tablas
  foto_referencia y embedding_referencia.
- downgrade desde 0007 las elimina limpiamente.
- La DB queda en 0006 tras el downgrade.

RAMA: 0007 pertenece a la rama PRINCIPAL (full, con TimescaleDB), NO a la
rama slim. slim@head = solo 0005 (Railway/Postgres estandar). Ver fix del
bug documentado en engram (topic: migrations/branch-isolation).

Requiere el stack de DB con TimescaleDB (RUN_STACK_TESTS=1). Se salta en la
suite unitaria.
"""

from __future__ import annotations

import os

import pytest


@pytest.mark.requires_stack
def test_migracion_0007_upgrade_y_downgrade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """upgrade 0007 (rama principal) -> tablas existen; downgrade -1 -> tablas eliminadas.

    Usa alembic upgrade 0007 (NO slim@head) porque 0006/0007 pertenecen a la
    rama principal (full, con TimescaleDB). slim@head solo aplica 0005 en
    Railway (Postgres estandar sin TimescaleDB).
    """
    import subprocess
    import sys

    db_url_sync = os.environ.get(
        "DATABASE_URL_SYNC",
        "postgresql://app@db:5432/proctoring",
    )
    alembic_ini = os.path.join(
        os.path.dirname(__file__), "..", "alembic.ini"
    )

    def run(args: list[str]) -> int:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", alembic_ini] + args,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"alembic {args} fallo:\n{result.stdout}\n{result.stderr}"
            )
        return result.returncode

    # Upgrade a 0007 (rama PRINCIPAL — incluye 0001 TimescaleDB -> ... -> 0007).
    # NO usar slim@head: 0006/0007 NO estan en la rama slim desde el fix del
    # bug de dependencias cruzadas.
    run(["upgrade", "0007"])

    # Verificar que las tablas existen con psycopg2 (sync).
    import psycopg2

    conn = psycopg2.connect(db_url_sync)
    cur = conn.cursor()
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name IN "
        "('foto_referencia', 'embedding_referencia');"
    )
    tablas = {row[0] for row in cur.fetchall()}
    assert "foto_referencia" in tablas, "foto_referencia no existe tras upgrade"
    assert "embedding_referencia" in tablas, "embedding_referencia no existe tras upgrade"
    cur.close()
    conn.close()

    # Downgrade -1 (vuelve a 0006).
    run(["downgrade", "-1"])

    # Verificar que las tablas ya no existen.
    conn = psycopg2.connect(db_url_sync)
    cur = conn.cursor()
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name IN "
        "('foto_referencia', 'embedding_referencia');"
    )
    tablas_post = {row[0] for row in cur.fetchall()}
    assert "foto_referencia" not in tablas_post, "foto_referencia no se elimino tras downgrade"
    assert "embedding_referencia" not in tablas_post, "embedding_referencia no se elimino tras downgrade"
    cur.close()
    conn.close()

    # Volver a 0007 para no dejar la DB rota para otros tests.
    run(["upgrade", "0007"])
