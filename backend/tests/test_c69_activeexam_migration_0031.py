"""Test de la migración 0031 activeexam (C-69, opción B): pool de preguntas seleccionables.

Verifica con alembic REAL contra Postgres (postgres:16, sin TimescaleDB):
- `alembic upgrade activeexam@head` aplica hasta 0031: pregunta_examen gana la columna
  `seleccionada` BOOLEAN NOT NULL DEFAULT true. Las filas preexistentes (creadas
  antes de la migración) quedan con seleccionada=true (compat: todas seleccionadas).
- `downgrade activeexam@0030` dropea la columna, dejando intacto pregunta_examen.

Requiere RUN_STACK_TESTS / DATABASE_URL apuntando a un Postgres sin timescale.
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


def _columnas_pregunta() -> dict[str, tuple[str, str, str | None]]:
    import psycopg2

    conn = psycopg2.connect(_sync_url())
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='pregunta_examen';"
        )
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()
    return {name: (data_type, is_nullable, default) for name, data_type, is_nullable, default in rows}


@pytest.mark.requires_stack
def test_migracion_0031_agrega_seleccionada_default_true() -> None:
    import psycopg2

    # Partimos del estado 0030 (sin la columna) para insertar una pregunta vieja.
    _alembic(["downgrade", "activeexam@0030"])

    conn = psycopg2.connect(_sync_url())
    conn.autocommit = True
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO examen_contenido (id, titulo) "
            "VALUES (gen_random_uuid(), 'mig-0031') RETURNING id;"
        )
        examen_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO pregunta_examen (examen_id, enunciado, tipo) "
            "VALUES (%s, 'pre-migracion', 'multichoice') RETURNING id;",
            (examen_id,),
        )
        pregunta_id = cur.fetchone()[0]
        cur.close()
    finally:
        conn.close()

    # Aplicamos 0031: agrega la columna con server_default true.
    _alembic(["upgrade", "activeexam@head"])

    cols = _columnas_pregunta()
    assert "seleccionada" in cols, "falta pregunta_examen.seleccionada"
    assert cols["seleccionada"][0] == "boolean"
    assert cols["seleccionada"][1] == "NO", "seleccionada debe ser NOT NULL"
    assert cols["seleccionada"][2] is not None
    assert "true" in cols["seleccionada"][2].lower(), "default debe ser true"

    # La fila preexistente queda con seleccionada=true (backfill por server_default).
    conn = psycopg2.connect(_sync_url())
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT seleccionada FROM pregunta_examen WHERE id = %s;", (pregunta_id,)
        )
        assert cur.fetchone()[0] is True, "la pregunta preexistente debe quedar seleccionada=true"
        cur.execute("DELETE FROM examen_contenido WHERE id = %s;", (examen_id,))
        conn.commit()
        cur.close()
    finally:
        conn.close()


@pytest.mark.requires_stack
def test_migracion_0031_downgrade_revierte() -> None:
    _alembic(["downgrade", "activeexam@0030"])

    cols = _columnas_pregunta()
    assert "seleccionada" not in cols, "seleccionada no eliminada en downgrade"

    # pregunta_examen sigue existiendo (no se dropeó la tabla).
    import psycopg2

    conn = psycopg2.connect(_sync_url())
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='pregunta_examen';"
        )
        assert cur.fetchone() is not None, "pregunta_examen no debe desaparecer"
        cur.close()
    finally:
        conn.close()

    # Re-aplicar para no dejar la DB a medias.
    _alembic(["upgrade", "activeexam@head"])
