"""La base de test tiene las FK que declaran los modelos (28/8/2026).

POR QUÉ EXISTE ESTE TEST. Varios módulos hacen `DROP TABLE usuario CASCADE`
para arrancar de cero. Ese CASCADE no se lleva sólo la tabla: borra también las
FK de OTRAS tablas, las que apuntaban a `usuario`. Esas tablas siguen ahí, así
que el hook de `conftest.py` que re-crea "lo que falta" no las mira nunca más y
la constraint no vuelve.

Una FK que falta no rompe nada de golpe, y por eso es peor: hace pasar tests que
deberían fallar. `test_dar_de_baja_al_usuario_arrastra_su_credencial` verifica
que borrar un usuario arrastra su credencial de Moodle. Sin la FK no hay cascada
y el token queda huérfano — el test falla contra un producto que está bien, o
peor, un día pasa porque la fila se borró por otro motivo y nadie revisa.

Lo que se vigila acá es el ESQUEMA DE LA BASE DE TEST, no el producto: en
producción las FK las pone la migración sobre una base limpia. Si este test
falla, la base de test se contaminó y el hook de conftest no la reparó.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.base import Base

#: Sus FK reales viven en la migración, no en el modelo (ver `_TABLAS_QUE_NO_SE_RECREAN`
#: en conftest.py): compararlas contra el ORM diría cualquier cosa.
_FUERA_DE_ALCANCE = frozenset({"audit_log", "foto_referencia"})

_FKS_EXISTENTES = """
    SELECT c.conrelid::regclass::text AS tabla,
           array_agg(a.attname ORDER BY a.attname) AS columnas
    FROM pg_constraint c
    JOIN unnest(c.conkey) AS k(attnum) ON true
    JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
    WHERE c.contype = 'f'
    GROUP BY c.oid, c.conrelid
"""


@pytest_asyncio.fixture
async def estado_real():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada — test de integración omitido")
    engine = create_async_engine(url, poolclass=NullPool, future=True)
    try:
        async with engine.begin() as conn:
            tablas = {
                f[0]
                for f in await conn.exec_driver_sql(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                )
            }
            fks: set[tuple[str, tuple[str, ...]]] = set()
            for tabla, columnas in await conn.exec_driver_sql(_FKS_EXISTENTES):
                fks.add((tabla, tuple(sorted(columnas))))
        return tablas, fks
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_ninguna_tabla_perdio_una_fk_declarada_por_su_modelo(estado_real):
    tablas, fks = estado_real
    faltantes: list[str] = []
    for tabla in Base.metadata.sorted_tables:
        if tabla.name in _FUERA_DE_ALCANCE or tabla.name not in tablas:
            continue
        for fk in tabla.foreign_key_constraints:
            # Si la tabla APUNTADA no existe, no hay constraint perdida que
            # reponer: falta la tabla, que es otro problema y otro mensaje.
            if any(e.column.table.name not in tablas for e in fk.elements):
                continue
            columnas = tuple(sorted(c.name for c in fk.columns))
            if (tabla.name, columnas) not in fks:
                faltantes.append(f"{tabla.name}({', '.join(columnas)})")

    assert not faltantes, (
        "La base de test perdió estas FK: "
        + "; ".join(sorted(faltantes))
        + ". Suele venir de un `DROP TABLE ... CASCADE` de un módulo anterior. "
        "El hook `_esquema_completo_por_modulo` de conftest.py tiene que "
        "reponerlas — si esto falla, dejó de hacerlo."
    )
