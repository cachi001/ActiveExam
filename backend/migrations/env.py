"""Entorno de ejecucion de Alembic.

La URL de conexion se toma de la env var ``DATABASE_URL`` (twelve-factor): NUNCA
se hardcodea en ``alembic.ini`` (seria un secreto en el repo). Para Alembic se
usa un driver sincrono, por lo que se normaliza ``+asyncpg`` -> driver sync.

Desde C-05 ``target_metadata`` apunta a la ``Base`` de los modelos ORM de
dominio. La migracion 001 (CREATE EXTENSION) y la 002 (hypertable/trigger/
agregados de TimescaleDB) se escriben a MANO porque Alembic no autogenera la DDL
especial de Timescale ni los triggers; la metadata sirve para validacion y para
diffs futuros de tablas transaccionales.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL no esta seteada. Alembic carga la conexion por entorno "
            "(twelve-factor); inyectala via Vault/tmpfs antes de migrar."
        )
    # Algunos proveedores (Railway/Heroku) inyectan el esquema viejo 'postgres://',
    # que SQLAlchemy 2.0 ya no reconoce. Normalizar a 'postgresql://'.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    # Alembic corre sincrono: el driver async no aplica aqui.
    return url.replace("+asyncpg", "").replace("+psycopg_async", "+psycopg")


# Metadata de dominio (C-05): la Base declarativa con todos los modelos ORM. El
# import por efecto colateral registra cada tabla en la metadata.
from app.infrastructure.persistence import models  # noqa: E402,F401
from app.infrastructure.persistence.base import Base  # noqa: E402

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
