"""Test de la migración 0087 activeexam (c-78 D1): examen_contenido.eliminado_en.

Verifica con alembic REAL contra Postgres (nunca un mock de DB):
- `upgrade activeexam@head` agrega la columna TIMESTAMPTZ NULLABLE. Los exámenes
  preexistentes quedan con `eliminado_en` NULL (= activos) sin backfill, y siguen
  siendo listables por la consulta del catálogo.
- `downgrade activeexam@0086` dropea SOLO esa columna: examen_contenido sigue
  existiendo con sus filas, y ninguna otra tabla del dominio se toca.

Requiere RUN_STACK_TESTS=1 / DATABASE_URL apuntando a un Postgres de test.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid

import pytest

_ALEMBIC_INI = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")

# Tablas del dominio que el downgrade NO debe tocar. Si el drop de la columna se
# lleva puesta alguna de estas, el rollback deja de ser seguro.
_TABLAS_INTACTAS = (
    "examen_contenido",
    "pregunta_examen",
    "opcion_respuesta",
    "materia",
    "comision",
    "proctoring_session",
)


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


def _columnas_examen() -> dict[str, tuple[str, str]]:
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


def _tablas_presentes() -> set[str]:
    import psycopg2

    conn = psycopg2.connect(_sync_url())
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public';"
        )
        nombres = {fila[0] for fila in cur.fetchall()}
        cur.close()
    finally:
        conn.close()
    return nombres


@pytest.fixture()
def examen_preexistente() -> str:
    """Inserta un examen ANTES de mirar la migración y lo limpia al final."""
    import psycopg2

    examen_id = str(uuid.uuid4())
    conn = psycopg2.connect(_sync_url())
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO examen_contenido (id, titulo) VALUES (%s, %s);",
            (examen_id, "Examen previo a la migración 0087"),
        )
        cur.close()
    finally:
        conn.close()

    yield examen_id

    conn = psycopg2.connect(_sync_url())
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("DELETE FROM examen_contenido WHERE id = %s;", (examen_id,))
        cur.close()
    finally:
        conn.close()


@pytest.mark.requires_stack
def test_migracion_0087_agrega_eliminado_en_nullable(examen_preexistente: str) -> None:
    import psycopg2

    _alembic(["upgrade", "activeexam@head"])

    cols = _columnas_examen()
    assert "eliminado_en" in cols, "falta examen_contenido.eliminado_en"
    tipo, nullable = cols["eliminado_en"]
    assert tipo == "timestamp with time zone", "eliminado_en debe ser TIMESTAMPTZ"
    assert nullable == "YES", "eliminado_en debe ser NULLABLE (NULL = activo)"

    # Sin backfill: el examen que ya existía queda activo y sigue apareciendo en
    # la consulta del catálogo (la que filtra por eliminado_en IS NULL).
    conn = psycopg2.connect(_sync_url())
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT eliminado_en FROM examen_contenido WHERE id = %s;",
            (examen_preexistente,),
        )
        fila = cur.fetchone()
        assert fila is not None, "la migración no debe borrar exámenes existentes"
        assert fila[0] is None, "un examen preexistente debe quedar activo (NULL)"

        cur.execute(
            "SELECT count(*) FROM examen_contenido "
            "WHERE id = %s AND eliminado_en IS NULL;",
            (examen_preexistente,),
        )
        assert cur.fetchone()[0] == 1, "el examen preexistente debe seguir listándose"
        cur.close()
    finally:
        conn.close()


@pytest.mark.requires_stack
def test_migracion_0087_downgrade_solo_dropea_la_columna(
    examen_preexistente: str,
) -> None:
    import psycopg2

    _alembic(["upgrade", "activeexam@head"])
    tablas_antes = _tablas_presentes()

    _alembic(["downgrade", "activeexam@0086"])

    cols = _columnas_examen()
    assert "eliminado_en" not in cols, "eliminado_en no se eliminó en el downgrade"

    # Ninguna otra tabla se cayó, y el examen sigue ahí (el rollback pierde la
    # MARCA de baja, no el examen ni su evidencia).
    tablas_despues = _tablas_presentes()
    for tabla in _TABLAS_INTACTAS:
        if tabla in tablas_antes:
            assert tabla in tablas_despues, f"el downgrade se llevó puesta {tabla}"

    conn = psycopg2.connect(_sync_url())
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT count(*) FROM examen_contenido WHERE id = %s;",
            (examen_preexistente,),
        )
        assert cur.fetchone()[0] == 1, "el downgrade no debe borrar el examen"
        cur.close()
    finally:
        conn.close()

    # Re-aplicar para no dejar la DB a medias.
    _alembic(["upgrade", "activeexam@head"])
