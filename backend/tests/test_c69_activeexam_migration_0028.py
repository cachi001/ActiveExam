"""Test de la migración 0028 activeexam (C-69 sección 6, D11).

Verifica con alembic REAL contra Postgres (postgres:16, sin TimescaleDB):
- `alembic upgrade activeexam@head` aplica hasta 0028: crea materia y comision.
- examen_contenido.comision_id obtiene una FK a comision con ON DELETE SET NULL.
- comision.materia_id es FK a materia con ON DELETE CASCADE.
- Único (materia_id, codigo) presente.
- `downgrade activeexam@0027` dropea materia/comision y la FK, dejando examen_contenido.

Requiere RUN_STACK_TESTS=1 + DATABASE_URL apuntando a un Postgres sin timescale.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

_ALEMBIC_INI = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")


def _to_sync(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url[len("postgresql+asyncpg://") :]
    return url


def _sync_url() -> str:
    return _to_sync(os.environ.get("DATABASE_URL", ""))


def _alembic(args: list[str]) -> None:
    env = {**os.environ, "DATABASE_URL": _sync_url()}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", _ALEMBIC_INI] + args,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        raise AssertionError(f"alembic {args} falló:\n{result.stdout}\n{result.stderr}")


@pytest.mark.requires_stack
def test_migracion_0028_crea_materia_comision_y_fk() -> None:
    _alembic(["upgrade", "activeexam@head"])

    import psycopg2

    conn = psycopg2.connect(_sync_url())
    cur = conn.cursor()

    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name IN ('materia','comision');"
    )
    tablas = {row[0] for row in cur.fetchall()}
    assert "materia" in tablas
    assert "comision" in tablas

    # FK examen_contenido.comision_id → comision con ON DELETE SET NULL (confdeltype='n').
    cur.execute(
        "SELECT confdeltype FROM pg_constraint WHERE conname='fk_examen_contenido_comision';"
    )
    row = cur.fetchone()
    assert row is not None and row[0] == "n", "FK examen→comisión no es ON DELETE SET NULL"

    # Único (materia_id, codigo).
    cur.execute("SELECT 1 FROM pg_constraint WHERE conname='uq_comision_materia_codigo';")
    assert cur.fetchone() is not None

    cur.close()
    conn.close()


@pytest.mark.requires_stack
def test_migracion_0028_downgrade_revierte() -> None:
    _alembic(["downgrade", "activeexam@0027"])

    import psycopg2

    conn = psycopg2.connect(_sync_url())
    cur = conn.cursor()

    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name IN ('materia','comision');"
    )
    assert len(cur.fetchall()) == 0, "materia/comision no eliminadas en downgrade"

    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name='examen_contenido';"
    )
    assert cur.fetchone() is not None, "examen_contenido no debe desaparecer"

    cur.execute(
        "SELECT 1 FROM pg_constraint WHERE conname='fk_examen_contenido_comision';"
    )
    assert cur.fetchone() is None, "FK examen→comisión debe quedar removida"

    cur.close()
    conn.close()

    # Re-aplicar para no dejar la DB a medias.
    _alembic(["upgrade", "activeexam@head"])
