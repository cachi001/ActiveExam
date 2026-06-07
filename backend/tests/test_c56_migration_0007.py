"""Test de la migracion 0007 (C-56): upgrade y downgrade.

Verifica que:
- upgrade desde 0006 crea las tablas foto_referencia y embedding_referencia.
- downgrade desde 0007 las elimina limpiamente.
- La DB queda en 0006 tras el downgrade.

Requiere el stack de DB (RUN_STACK_TESTS=1). Se salta en la suite unitaria.
"""

from __future__ import annotations

import os

import pytest


@pytest.mark.requires_stack
def test_migracion_0007_upgrade_y_downgrade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """upgrade head (0007) → tablas existen; downgrade -1 → tablas eliminadas."""
    import subprocess
    import sys

    db_url = os.environ.get(
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

    # Upgrade a head de la rama slim (incluye 0007).
    # El proyecto tiene dos branches (default y slim): 'head' es ambiguo.
    # Usar 'slim@head' o 'heads' para resolver las dos cabezas.
    run(["upgrade", "slim@head"])

    # Verificar que las tablas existen con psycopg2.
    import psycopg2

    conn = psycopg2.connect(db_url)
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
    conn = psycopg2.connect(db_url)
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

    # Volver a slim@head para no dejar la DB rota para otros tests.
    run(["upgrade", "slim@head"])
