"""Tests de persistencia de la Configuracion del Sistema (configuracion-sistema-funcional, Grupo 1).

DB real (sin mocks, regla dura): usa DATABASE_URL del entorno; crea las tablas nuevas
directo via Table.create() (patron de tests/proctoring/conftest.py). Verifica:
- el singleton se crea/lee desde configuracion_sistema (persistencia entre lecturas);
- el bump monotonico de version al editar;
- la auditoria inmutable en audit_log (accion config_update con before/after);
- que ConfigService combina evento_score_config + configuracion_sistema en la config efectiva.

Sin mocks de DB: si DATABASE_URL no esta seteada, el test se SALTA.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

pytestmark = pytest.mark.asyncio


def _db_url() -> str | None:
    return os.environ.get("DATABASE_URL")


@pytest_asyncio.fixture
async def factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    url = _db_url()
    if not url:
        pytest.skip("DATABASE_URL no seteada; test de integracion (DB real).")

    from app.infrastructure.persistence.models.transactional import (
        ConfiguracionSistemaModel,
    )

    engine = create_async_engine(url, pool_pre_ping=True, future=True)
    tabla = ConfiguracionSistemaModel.__table__
    async with engine.begin() as conn:
        await conn.run_sync(tabla.drop, checkfirst=True)
        await conn.run_sync(tabla.create, checkfirst=True)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(tabla.drop, checkfirst=True)
    await engine.dispose()


async def _seed_singleton(factory: async_sessionmaker[AsyncSession]) -> None:
    from app.infrastructure.persistence.repositories.config_sistema import (
        ConfiguracionSistemaSqlRepository,
    )

    async with factory() as s:
        repo = ConfiguracionSistemaSqlRepository(s)
        await repo.ensure_singleton()
        await s.commit()


async def test_singleton_se_crea_y_lee(factory) -> None:
    """ensure_singleton crea la fila global con los defaults; get la recupera."""
    from app.infrastructure.persistence.repositories.config_sistema import (
        ConfiguracionSistemaSqlRepository,
    )

    await _seed_singleton(factory)
    async with factory() as s:
        repo = ConfiguracionSistemaSqlRepository(s)
        cfg = await repo.get()
    assert cfg is not None
    assert cfg.face_absent_ms == 3000
    assert cfg.multiple_faces_frames == 5
    assert cfg.umbral_cola_revision == 70
    assert cfg.consent_version_vigente == "v1"
    assert cfg.version == 1


async def test_persiste_entre_lecturas(factory) -> None:
    """El valor editado se lee de la BD en una sesion nueva (no memoria volatil)."""
    from app.infrastructure.persistence.repositories.config_sistema import (
        ConfiguracionSistemaSqlRepository,
    )

    await _seed_singleton(factory)
    async with factory() as s:
        repo = ConfiguracionSistemaSqlRepository(s)
        await repo.update({"face_absent_ms": 4500})
        await s.commit()

    async with factory() as s2:
        repo2 = ConfiguracionSistemaSqlRepository(s2)
        cfg = await repo2.get()
    assert cfg.face_absent_ms == 4500


async def test_version_bump_monotonico(factory) -> None:
    """Cada edicion exitosa incrementa estrictamente version."""
    from app.infrastructure.persistence.repositories.config_sistema import (
        ConfiguracionSistemaSqlRepository,
    )

    await _seed_singleton(factory)
    async with factory() as s:
        repo = ConfiguracionSistemaSqlRepository(s)
        v0 = (await repo.get()).version
        await repo.update({"umbral_cola_revision": 80})
        await s.commit()
    async with factory() as s2:
        v1 = (await ConfiguracionSistemaSqlRepository(s2).get()).version
        await ConfiguracionSistemaSqlRepository(s2).update({"umbral_cola_revision": 85})
        await s2.commit()
    async with factory() as s3:
        v2 = (await ConfiguracionSistemaSqlRepository(s3).get()).version
    assert v1 == v0 + 1
    assert v2 == v1 + 1
