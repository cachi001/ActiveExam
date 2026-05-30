"""Base declarativa de SQLAlchemy y metadata del esquema de dominio.

Esta ``Base`` agrupa la metadata de TODOS los modelos ORM de dominio (C-05). Es
la que ``migrations/env.py`` puede tomar como ``target_metadata`` para autogenerar
diffs, aunque la migracion 002 se escribe a mano (necesita SQL de TimescaleDB:
hypertable, compresion, continuous aggregates, y el trigger del audit log, que
Alembic no autogenera).

Convencion de nombres de constraints (reproducibilidad de migraciones): nombres
deterministas para PK/FK/UQ/CK/IX, asi los downgrades pueden referenciarlos.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Convencion de nombres deterministas para constraints e indices. Evita nombres
# autogenerados no portables y permite que la migracion los referencie al revertir.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base declarativa comun a todos los modelos ORM de dominio."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
