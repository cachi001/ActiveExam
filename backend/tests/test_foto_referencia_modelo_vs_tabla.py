"""El modelo ORM de ``foto_referencia`` describe la tabla que realmente existe.

Por qué existe
--------------
``FotoReferenciaModel`` declaraba ``uri_storage`` y ``bucket`` (punteros a MinIO)
y no declaraba ``foto_bytes``. Esas columnas vienen de la migración 0007, de la
rama "full", que **no está aplicada en ninguna base viva**: la cadena que corre
en producción y en dev es la de activeexam (0005 -> 0008 -> 0009 -> ...), y ahí
la foto se guarda como BYTEA en ``foto_bytes``.

O sea que el modelo describía una tabla que no existe en ningún lado. El daño no
era teórico:

  - cualquier ``select(FotoReferenciaModel)`` entero revienta con
    ``UndefinedColumnError`` contra la base real
  - los tests que creaban la tabla desde el modelo la creaban MAL, y por eso el
    estado biométrico del detalle del usuario no tenía cobertura real

Este módulo fija el contrato: **el modelo tiene que poder escribir y leer contra
la tabla tal como la crea la migración 0008**. Si mañana vuelve MinIO, hay que
migrar la tabla y actualizar este test junto con el modelo, no al revés.

Contra DB REAL, sin mocks (regla dura de código).
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.transactional import (
    FotoReferenciaModel,
    UsuarioModel,
)
from app.infrastructure.persistence.repositories.biometric_reference import (
    FotoReferenciaRepository,
)

# Columnas de `foto_referencia` según migrations/versions/0008_c57_auth_biometria_activeexam.py.
# Es la tabla que existe en Render y en dev.
_COLUMNAS_REALES = {
    "id",
    "usuario_id",
    "foto_bytes",
    "hash_sha256",
    "vigente",
    "created_at",
    "updated_at",
}

# DDL calcada de esa migración. Se crea a mano (y no desde el modelo) justamente
# para que el test no pueda "aprobarse a sí mismo": si el modelo se desalinea,
# el INSERT falla.
_DDL_FOTO_REFERENCIA = """
CREATE TABLE foto_referencia (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id UUID NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    foto_bytes BYTEA NOT NULL,
    hash_sha256 TEXT NOT NULL,
    vigente BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada")
    return url


@pytest_asyncio.fixture(scope="module")
async def engine(db_url):
    eng = create_async_engine(db_url, pool_pre_ping=True, future=True, poolclass=NullPool)
    async with eng.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS foto_referencia CASCADE"))
        await conn.execute(text('DROP TABLE IF EXISTS "usuario" CASCADE'))
        await conn.run_sync(Base.metadata.create_all, tables=[UsuarioModel.__table__])
        await conn.execute(text(_DDL_FOTO_REFERENCIA))
    yield eng
    async with eng.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS foto_referencia CASCADE"))
        await conn.execute(text('DROP TABLE IF EXISTS "usuario" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _crear_usuario(factory) -> str:
    sufijo = uuid.uuid4().hex[:8]
    async with factory() as s:
        u = UsuarioModel(
            username=f"foto-{sufijo}",
            email=f"foto-{sufijo}@test.local",
            roles=["estudiante"],
            auth_provider="local",
        )
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
    return uid


def test_el_modelo_declara_exactamente_las_columnas_de_la_tabla():
    declaradas = {c.name for c in FotoReferenciaModel.__table__.columns}
    assert declaradas == _COLUMNAS_REALES, (
        "El modelo se desalineó de la tabla que crea la migración 0008. "
        f"De más: {declaradas - _COLUMNAS_REALES}. De menos: {_COLUMNAS_REALES - declaradas}."
    )


@pytest.mark.asyncio
async def test_se_puede_guardar_y_leer_una_foto_con_el_modelo(factory):
    """Lo que importa de verdad: el ORM escribe y lee contra la tabla real."""
    uid = await _crear_usuario(factory)

    async with factory() as s:
        s.add(
            FotoReferenciaModel(
                usuario_id=uid,
                foto_bytes=b"\x89PNG\r\n\x1a\n",
                hash_sha256="hash-de-prueba",
                vigente=True,
            )
        )
        await s.commit()

    async with factory() as s:
        fila = (
            await s.execute(
                select(FotoReferenciaModel).where(FotoReferenciaModel.usuario_id == uid)
            )
        ).scalar_one()

    assert fila.foto_bytes == b"\x89PNG\r\n\x1a\n"
    assert fila.hash_sha256 == "hash-de-prueba"
    assert fila.vigente is True


@pytest.mark.asyncio
async def test_el_repositorio_mantiene_una_sola_foto_vigente(factory):
    """Triangulación por el camino real: el gate de perfil usa este repositorio."""
    uid = await _crear_usuario(factory)

    async with factory() as s:
        repo = FotoReferenciaRepository(s)
        primera = await repo.crear(
            usuario_id=uid, foto_bytes=b"primera", hash_sha256="hash-1"
        )
        await s.commit()
        primera_id = primera.id

    async with factory() as s:
        repo = FotoReferenciaRepository(s)
        await repo.marcar_anteriores_no_vigentes(uid)
        segunda = await repo.crear(
            usuario_id=uid, foto_bytes=b"segunda", hash_sha256="hash-2"
        )
        await s.commit()
        segunda_id = segunda.id

    assert primera_id != segunda_id

    async with factory() as s:
        repo = FotoReferenciaRepository(s)
        vigente = await repo.obtener_vigente(uid)

    assert vigente == segunda_id, "la vigente tiene que ser la última que se guardó"


@pytest.mark.asyncio
async def test_sin_foto_no_hay_vigente(factory):
    """Triangulación: el gate de perfil frena por este None."""
    uid = await _crear_usuario(factory)

    async with factory() as s:
        vigente = await FotoReferenciaRepository(s).obtener_vigente(uid)

    assert vigente is None
