"""Test de la migración 0034 activeexam (C-69): flags chat_habilitado / pausas_habilitadas.

Verifica con alembic REAL contra Postgres (postgres:16, sin TimescaleDB):
- `alembic upgrade activeexam@head` aplica hasta 0034: configuracion_sistema gana las 2
  columnas booleanas con server_default true. La fila singleton preexistente
  ('global', creada por 0014) queda con chat_habilitado=true y pausas_habilitadas=true
  (backfill por server_default).
- `downgrade activeexam@0033` dropea las 2 columnas, dejando intacta configuracion_sistema.

Requiere RUN_STACK_TESTS=1 / DATABASE_URL apuntando a un Postgres sin timescale.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

_ALEMBIC_INI = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")

_COLS_NUEVAS = {"chat_habilitado", "pausas_habilitadas"}


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


def _columnas_config() -> dict[str, tuple[str, str, str | None]]:
    import psycopg2

    conn = psycopg2.connect(_sync_url())
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='configuracion_sistema';"
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
def test_migracion_0034_agrega_flags_con_defaults() -> None:
    import psycopg2

    # Aplicamos hasta head: agrega las 2 columnas con server_default true.
    _alembic(["upgrade", "activeexam@head"])

    cols = _columnas_config()
    for c in _COLS_NUEVAS:
        assert c in cols, f"falta configuracion_sistema.{c}"

    # Tipo boolean, NOT NULL, default true.
    for c in _COLS_NUEVAS:
        assert cols[c][0] == "boolean", f"{c} debe ser boolean"
        assert cols[c][1] == "NO", f"{c} debe ser NOT NULL"
        assert "true" in (cols[c][2] or "").lower(), f"{c} default debe ser true"

    # La fila singleton preexistente toma el default true (backfill server_default).
    conn = psycopg2.connect(_sync_url())
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT chat_habilitado, pausas_habilitadas "
            "FROM configuracion_sistema WHERE id = 'global';"
        )
        row = cur.fetchone()
        assert row is not None, "falta el singleton 'global'"
        assert row[0] is True  # chat_habilitado
        assert row[1] is True  # pausas_habilitadas
        cur.close()
    finally:
        conn.close()


@pytest.mark.requires_stack
def test_migracion_0034_downgrade_revierte() -> None:
    _alembic(["downgrade", "activeexam@0033"])

    cols = _columnas_config()
    for c in _COLS_NUEVAS:
        assert c not in cols, f"{c} no eliminada en downgrade"

    # configuracion_sistema sigue existiendo (no se dropeó la tabla).
    import psycopg2

    conn = psycopg2.connect(_sync_url())
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='configuracion_sistema';"
        )
        assert cur.fetchone() is not None, "configuracion_sistema no debe desaparecer"
        cur.close()
    finally:
        conn.close()

    # Re-aplicar para no dejar la DB a medias.
    _alembic(["upgrade", "activeexam@head"])
