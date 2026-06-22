"""Tests de persistencia del consentimiento de perfil (profile-consent-persistence).

DB real. Tabla consentimiento_perfil APPEND-ONLY atada a usuario_id (Ley 25.326):
- otorgar/consultar/revocar/re-otorgar -> estado vigente = fila mas reciente;
- el historico permanece intacto (revocar NO borra);
- hash de texto + hash de registro (demostrabilidad/integridad);
- eliminacion al egreso (purga por usuario) difiere ante hold.

Sin mocks de DB: crea usuario + consentimiento_perfil directo via Table.create().
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.asyncio


def _db_url() -> str | None:
    return os.environ.get("DATABASE_URL")


@pytest_asyncio.fixture
async def factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    url = _db_url()
    if not url:
        pytest.skip("DATABASE_URL no seteada; test de integracion (DB real).")

    from app.infrastructure.persistence.models.transactional import (
        ConsentimientoPerfilModel,
    )

    engine = create_async_engine(url, pool_pre_ping=True, future=True, poolclass=NullPool)
    tbl = ConsentimientoPerfilModel.__table__
    async with engine.begin() as conn:
        await conn.run_sync(tbl.drop, checkfirst=True)
        await conn.run_sync(tbl.create, checkfirst=True)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(tbl.drop, checkfirst=True)
    await engine.dispose()


async def _crear_usuario(factory: async_sessionmaker[AsyncSession], suf: str) -> str:
    from app.infrastructure.persistence.models.transactional import UsuarioModel

    suf = f"{suf}-{uuid.uuid4().hex[:8]}"
    async with factory() as s:
        u = UsuarioModel(
            id_institucional=f"cperf-{suf}",
            email=f"cperf-{suf}@test.local",
            roles=["estudiante"],
            auth_provider="local",
        )
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
    return uid


async def test_otorgar_y_consultar_vigente(factory) -> None:
    from app.infrastructure.persistence.repositories.consent_perfil import (
        ConsentimientoPerfilSqlRepository,
    )

    uid = await _crear_usuario(factory, "a")
    async with factory() as s:
        repo = ConsentimientoPerfilSqlRepository(s)
        await repo.registrar(
            usuario_id=uid, version_texto="v1", hash_texto="h" * 64, estado="otorgado"
        )
        await s.commit()
    async with factory() as s2:
        vigente = await ConsentimientoPerfilSqlRepository(s2).vigente(uid)
    assert vigente is not None
    assert vigente.estado == "otorgado"
    assert vigente.version_texto == "v1"
    assert len(vigente.hash_registro) == 64


async def test_revocar_preserva_historico_y_vigente_es_revocado(factory) -> None:
    from sqlalchemy import func, select

    from app.infrastructure.persistence.models.transactional import (
        ConsentimientoPerfilModel,
    )
    from app.infrastructure.persistence.repositories.consent_perfil import (
        ConsentimientoPerfilSqlRepository,
    )

    uid = await _crear_usuario(factory, "b")
    async with factory() as s:
        repo = ConsentimientoPerfilSqlRepository(s)
        await repo.registrar(usuario_id=uid, version_texto="v1", hash_texto="h" * 64, estado="otorgado")
        await repo.registrar(usuario_id=uid, version_texto="v1", hash_texto="h" * 64, estado="revocado")
        await s.commit()
    async with factory() as s2:
        vigente = await ConsentimientoPerfilSqlRepository(s2).vigente(uid)
        total = (
            await s2.execute(
                select(func.count()).select_from(ConsentimientoPerfilModel).where(
                    ConsentimientoPerfilModel.usuario_id == uid
                )
            )
        ).scalar_one()
    assert vigente.estado == "revocado"
    assert total == 2  # historico intacto (append-only)


async def test_reotorgar_vigente_es_mas_reciente(factory) -> None:
    from app.infrastructure.persistence.repositories.consent_perfil import (
        ConsentimientoPerfilSqlRepository,
    )

    uid = await _crear_usuario(factory, "c")
    async with factory() as s:
        repo = ConsentimientoPerfilSqlRepository(s)
        await repo.registrar(usuario_id=uid, version_texto="v1", hash_texto="h" * 64, estado="otorgado")
        await repo.registrar(usuario_id=uid, version_texto="v1", hash_texto="h" * 64, estado="revocado")
        await repo.registrar(usuario_id=uid, version_texto="v2", hash_texto="x" * 64, estado="otorgado")
        await s.commit()
    async with factory() as s2:
        vigente = await ConsentimientoPerfilSqlRepository(s2).vigente(uid)
    assert vigente.estado == "otorgado"
    assert vigente.version_texto == "v2"


async def test_purga_por_usuario_egreso(factory) -> None:
    """Eliminacion al egreso: purga TODAS las filas del usuario."""
    from app.infrastructure.persistence.repositories.consent_perfil import (
        ConsentimientoPerfilSqlRepository,
    )

    uid = await _crear_usuario(factory, "d")
    async with factory() as s:
        repo = ConsentimientoPerfilSqlRepository(s)
        await repo.registrar(usuario_id=uid, version_texto="v1", hash_texto="h" * 64, estado="otorgado")
        await repo.registrar(usuario_id=uid, version_texto="v1", hash_texto="h" * 64, estado="revocado")
        await s.commit()
    async with factory() as s2:
        borradas = await ConsentimientoPerfilSqlRepository(s2).purgar_por_usuario(uid)
        await s2.commit()
    assert borradas == 2
    async with factory() as s3:
        assert await ConsentimientoPerfilSqlRepository(s3).vigente(uid) is None
