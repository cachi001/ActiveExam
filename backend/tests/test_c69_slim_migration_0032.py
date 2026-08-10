"""Test de la migración 0032 slim (C-69): configuración del examen POR EXAMEN.

Verifica con alembic REAL contra Postgres (postgres:16, sin TimescaleDB):
- `alembic upgrade slim@head` aplica hasta 0032: examen_contenido gana las 7
  columnas de configuración con sus defaults. Una fila preexistente (creada antes
  de la migración) queda con la config por defecto (1 intento, nota_maxima 100,
  nota_aprobacion 60, mezclar_preguntas false, ventana/límite NULL). El default
  de nota_maxima/nota_aprobacion fue 10/6 hasta la migración 0061, que lo subió
  a 100/60 (escala 0-100, nunca "sobre 10") — este test corre contra slim@head,
  así que verifica el default VIGENTE, no el de 0032 en aislamiento.
- `downgrade slim@0031` dropea las 7 columnas, dejando intacto examen_contenido.

Requiere RUN_STACK_TESTS / DATABASE_URL apuntando a un Postgres sin timescale.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

_ALEMBIC_INI = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")

_COLS_NUEVAS = {
    "tiempo_limite_min",
    "intentos_permitidos",
    "apertura",
    "cierre",
    "nota_maxima",
    "nota_aprobacion",
    "mezclar_preguntas",
}


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


def _columnas_examen() -> dict[str, tuple[str, str, str | None]]:
    import psycopg2

    conn = psycopg2.connect(_sync_url())
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='examen_contenido';"
        )
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()
    return {
        name: (data_type, is_nullable, default)
        for name, data_type, is_nullable, default in rows
    }


@pytest.mark.requires_stack
def test_migracion_0032_agrega_config_con_defaults() -> None:
    import psycopg2

    # Partimos del estado 0031 (sin las columnas) para insertar un examen viejo.
    _alembic(["downgrade", "slim@0031"])

    conn = psycopg2.connect(_sync_url())
    conn.autocommit = True
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO examen_contenido (id, titulo) "
            "VALUES (gen_random_uuid(), 'mig-0032') RETURNING id;"
        )
        examen_id = cur.fetchone()[0]
        cur.close()
    finally:
        conn.close()

    # Aplicamos 0032: agrega las 7 columnas con sus defaults.
    _alembic(["upgrade", "slim@head"])

    cols = _columnas_examen()
    for c in _COLS_NUEVAS:
        assert c in cols, f"falta examen_contenido.{c}"

    # Nullabilidad
    assert cols["tiempo_limite_min"][1] == "YES"
    assert cols["apertura"][1] == "YES"
    assert cols["cierre"][1] == "YES"
    assert cols["intentos_permitidos"][1] == "NO"
    assert cols["nota_maxima"][1] == "NO"
    assert cols["nota_aprobacion"][1] == "NO"
    assert cols["mezclar_preguntas"][1] == "NO"

    # Tipos
    assert cols["intentos_permitidos"][0] == "integer"
    assert cols["tiempo_limite_min"][0] == "integer"
    assert cols["nota_maxima"][0] == "numeric"
    assert cols["nota_aprobacion"][0] == "numeric"
    assert cols["mezclar_preguntas"][0] == "boolean"
    assert "timestamp" in cols["apertura"][0]
    assert "timestamp" in cols["cierre"][0]

    # Defaults (vigentes en slim@head, post-migración 0061)
    assert "1" in (cols["intentos_permitidos"][2] or "")
    assert "100" in (cols["nota_maxima"][2] or "")
    assert "60" in (cols["nota_aprobacion"][2] or "")
    assert "false" in (cols["mezclar_preguntas"][2] or "").lower()

    # La fila preexistente toma los defaults (backfill por server_default).
    conn = psycopg2.connect(_sync_url())
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT tiempo_limite_min, intentos_permitidos, apertura, cierre, "
            "nota_maxima, nota_aprobacion, mezclar_preguntas "
            "FROM examen_contenido WHERE id = %s;",
            (examen_id,),
        )
        row = cur.fetchone()
        assert row[0] is None  # tiempo_limite_min
        assert row[1] == 1  # intentos_permitidos
        assert row[2] is None  # apertura
        assert row[3] is None  # cierre
        assert float(row[4]) == 100.0  # nota_maxima
        assert float(row[5]) == 60.0  # nota_aprobacion
        assert row[6] is False  # mezclar_preguntas
        cur.execute("DELETE FROM examen_contenido WHERE id = %s;", (examen_id,))
        conn.commit()
        cur.close()
    finally:
        conn.close()


@pytest.mark.requires_stack
def test_migracion_0032_downgrade_revierte() -> None:
    _alembic(["downgrade", "slim@0031"])

    cols = _columnas_examen()
    for c in _COLS_NUEVAS:
        assert c not in cols, f"{c} no eliminada en downgrade"

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
