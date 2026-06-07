"""Test de la migracion 0008 slim (c-57, task 1.7).

Verifica que:
- alembic upgrade slim@head en postgres:16-alpine aplica 0005 + 0008 sin error.
- Las 4 tablas de auth+biometria se crean correctamente.
- Las tablas de proctoring (0005) permanecen intactas.
- No hay ninguna referencia a timescaledb ni hypertables.

CRITICO: usa postgres:16-alpine, NO imagen timescale.
Requiere RUN_STACK_TESTS=1 con DATABASE_URL_SLIM apuntando a postgres:16-alpine.
"""

from __future__ import annotations

import os

import pytest

# DATABASE_URL_SLIM puede ser asyncpg o sync. Normalizamos a sync (psycopg2).
_DB_URL_SLIM_RAW = os.environ.get(
    "DATABASE_URL_SLIM",
    os.environ.get("DATABASE_URL_SYNC_SLIM", "postgresql://app@db-slim:5432/proctoring"),
)

# Normalizar a URL sync (psycopg2) para psycopg2.connect y para alembic.
def _to_sync(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url[len("postgresql+asyncpg://"):]
    return url

_DB_URL_SYNC_SLIM = _to_sync(_DB_URL_SLIM_RAW)


@pytest.mark.requires_stack
def test_migracion_0008_slim_upgrade_crea_tablas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """slim@head en postgres:16-alpine aplica 0005 + 0008, crea las 7 tablas."""
    import subprocess
    import sys
    import os

    alembic_ini = os.path.join(
        os.path.dirname(__file__), "..", "alembic.ini"
    )

    def run(args: list[str]) -> None:
        env = {**os.environ, "DATABASE_URL": _DB_URL_SYNC_SLIM}
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", alembic_ini] + args,
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"alembic {args} fallo:\n{result.stdout}\n{result.stderr}"
            )

    # Aplicar slim@head (0005 + 0008).
    run(["upgrade", "slim@head"])

    import psycopg2

    conn = psycopg2.connect(_DB_URL_SYNC_SLIM)
    cur = conn.cursor()

    # Verificar las 4 tablas de auth+biometria (creadas en 0008).
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name IN "
        "('usuario', 'refresh_tokens', 'foto_referencia', 'embedding_referencia');"
    )
    tablas_auth = {row[0] for row in cur.fetchall()}
    assert "usuario" in tablas_auth, "Tabla 'usuario' no creada por 0008"
    assert "refresh_tokens" in tablas_auth, "Tabla 'refresh_tokens' no creada por 0008"
    assert "foto_referencia" in tablas_auth, "Tabla 'foto_referencia' no creada por 0008"
    assert "embedding_referencia" in tablas_auth, "Tabla 'embedding_referencia' no creada por 0008"

    # Verificar las 3 tablas de proctoring (creadas en 0005, deben permanecer).
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name IN "
        "('proctoring_session', 'proctoring_event', 'proctoring_biometria');"
    )
    tablas_proctoring = {row[0] for row in cur.fetchall()}
    assert "proctoring_session" in tablas_proctoring, "proctoring_session desaparecio"
    assert "proctoring_event" in tablas_proctoring, "proctoring_event desaparecio"
    assert "proctoring_biometria" in tablas_proctoring, "proctoring_biometria desaparecio"

    # Verificar que NO existe la extension timescaledb (postgres:16-alpine puro).
    cur.execute(
        "SELECT extname FROM pg_extension WHERE extname = 'timescaledb';"
    )
    timescale = cur.fetchone()
    assert timescale is None, (
        "timescaledb esta instalado — este test debe correr contra "
        "postgres:16-alpine PURO (sin TimescaleDB). Verificar la imagen de Docker."
    )

    # Verificar columna foto_bytes en foto_referencia (slim: BYTEA, sin uri_storage).
    cur.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = 'foto_referencia' AND table_schema = 'public';"
    )
    columnas_foto = {row[0]: row[1] for row in cur.fetchall()}
    assert "foto_bytes" in columnas_foto, "foto_referencia no tiene columna foto_bytes"
    assert "uri_storage" not in columnas_foto, (
        "foto_referencia tiene uri_storage (columna del full, no del slim)"
    )
    assert columnas_foto["foto_bytes"] == "bytea", (
        f"foto_bytes no es BYTEA, es: {columnas_foto['foto_bytes']}"
    )

    cur.close()
    conn.close()


@pytest.mark.requires_stack
def test_migracion_0008_slim_downgrade_revierte_tablas() -> None:
    """slim downgrade a 0005 elimina las 4 tablas de auth+biometria, proctoring intacto."""
    import subprocess
    import sys
    import os

    alembic_ini = os.path.join(
        os.path.dirname(__file__), "..", "alembic.ini"
    )

    def run(args: list[str]) -> None:
        env = {**os.environ, "DATABASE_URL": _DB_URL_SYNC_SLIM}
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", alembic_ini] + args,
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"alembic {args} fallo:\n{result.stdout}\n{result.stderr}"
            )

    # Downgrade a 0005 (revierte las tablas de 0008).
    run(["downgrade", "slim@0005"])

    import psycopg2

    conn = psycopg2.connect(_DB_URL_SYNC_SLIM)
    cur = conn.cursor()

    # Las 4 tablas de auth+biometria deben haber desaparecido.
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name IN "
        "('usuario', 'refresh_tokens', 'foto_referencia', 'embedding_referencia');"
    )
    tablas_post = {row[0] for row in cur.fetchall()}
    assert len(tablas_post) == 0, (
        f"Tablas de auth+biometria no eliminadas: {tablas_post}"
    )

    # Las tablas de proctoring (0005) deben permanecer.
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name IN "
        "('proctoring_session', 'proctoring_event', 'proctoring_biometria');"
    )
    tablas_proctoring = {row[0] for row in cur.fetchall()}
    assert "proctoring_session" in tablas_proctoring
    assert "proctoring_event" in tablas_proctoring
    assert "proctoring_biometria" in tablas_proctoring

    cur.close()
    conn.close()

    # Volver a slim@head para no dejar la DB rota.
    run(["upgrade", "slim@head"])
