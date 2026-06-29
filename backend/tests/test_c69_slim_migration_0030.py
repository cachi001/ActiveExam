"""Test de la migración 0030 slim (C-69, D12 parte B): destino Moodle por examen.

Verifica con alembic REAL contra Postgres (postgres:16, sin TimescaleDB):
- `alembic upgrade slim@head` aplica hasta 0030: examen_contenido gana las
  columnas NULLABLE moodle_courseid (integer) y moodle_cmid (integer).
- `downgrade slim@0029` dropea ambas columnas, dejando intacto examen_contenido.

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


def _columnas_examen() -> dict[str, str]:
    import psycopg2

    conn = psycopg2.connect(_sync_url())
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='examen_contenido';"
        )
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()
    return {name: (data_type, is_nullable) for name, data_type, is_nullable in rows}


@pytest.mark.requires_stack
def test_migracion_0030_agrega_columnas_moodle_target() -> None:
    _alembic(["upgrade", "slim@head"])

    cols = _columnas_examen()
    assert "moodle_courseid" in cols, "falta examen_contenido.moodle_courseid"
    assert "moodle_cmid" in cols, "falta examen_contenido.moodle_cmid"
    # Ambas integer y NULLABLE (aditivas, fallback a global cuando NULL).
    assert cols["moodle_courseid"][0] == "integer"
    assert cols["moodle_courseid"][1] == "YES"
    assert cols["moodle_cmid"][0] == "integer"
    assert cols["moodle_cmid"][1] == "YES"


@pytest.mark.requires_stack
def test_migracion_0030_downgrade_revierte() -> None:
    _alembic(["downgrade", "slim@0029"])

    cols = _columnas_examen()
    assert "moodle_courseid" not in cols, "moodle_courseid no eliminada en downgrade"
    assert "moodle_cmid" not in cols, "moodle_cmid no eliminada en downgrade"

    # examen_contenido sigue existiendo (no se dropeó la tabla).
    import psycopg2

    conn = psycopg2.connect(_sync_url())
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='examen_contenido';"
        )
        assert cur.fetchone() is not None, "examen_contenido no debe desaparecer"
        cur.close()
    finally:
        conn.close()

    # Re-aplicar para no dejar la DB a medias.
    _alembic(["upgrade", "slim@head"])
