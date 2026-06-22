"""Tests del ConfigService: config efectiva (scoring + umbrales) + cache por version.

DB real. El ConfigService combina evento_score_config (pesos por tipo) +
configuracion_sistema (umbrales/detectores/version) en un unico objeto autoritativo
``ConfigEfectiva``. Cachea en memoria y invalida por ``version``.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
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
        ConfiguracionSistemaModel,
        EventoScoreConfigModel,
    )

    engine = create_async_engine(url, pool_pre_ping=True, future=True, poolclass=NullPool)
    cfg_tbl = ConfiguracionSistemaModel.__table__
    score_tbl = EventoScoreConfigModel.__table__
    async with engine.begin() as conn:
        await conn.run_sync(cfg_tbl.drop, checkfirst=True)
        await conn.run_sync(cfg_tbl.create, checkfirst=True)
        # evento_score_config ya existe en la DB (migracion 0011); la seedea-mos
        # con pesos conocidos para el test (idempotente).
        await conn.run_sync(score_tbl.create, checkfirst=True)
        await conn.execute(
            text(
                "INSERT INTO evento_score_config (tipo_evento, severidad, peso, activo) "
                "VALUES ('rostro_ausente','media',20,true), "
                "('multiples_rostros','alta',55,true), "
                "('cambio_pestana','media',20,false) "
                "ON CONFLICT (tipo_evento) DO UPDATE SET peso=EXCLUDED.peso, "
                "activo=EXCLUDED.activo, severidad=EXCLUDED.severidad"
            )
        )
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(cfg_tbl.drop, checkfirst=True)
        await conn.execute(
            text(
                "DELETE FROM evento_score_config WHERE tipo_evento IN "
                "('rostro_ausente','multiples_rostros','cambio_pestana')"
            )
        )
    await engine.dispose()


async def test_config_efectiva_combina_scoring_y_umbrales(factory) -> None:
    from app.application.config.service import ConfigService
    from app.infrastructure.persistence.repositories.config_sistema import (
        ConfiguracionSistemaSqlRepository,
    )

    async with factory() as s:
        await ConfiguracionSistemaSqlRepository(s).ensure_singleton()
        await s.commit()

    svc = ConfigService(factory)
    efectiva = await svc.get_efectiva()
    # Umbrales desde configuracion_sistema.
    assert efectiva.face_absent_ms == 3000
    assert efectiva.umbral_cola_revision == 70
    assert efectiva.version == 1
    # Pesos desde evento_score_config (solo activos).
    assert efectiva.scoring_weights["rostro_ausente"] == 20
    assert efectiva.scoring_weights["multiples_rostros"] == 55
    # cambio_pestana esta inactivo -> NO aparece.
    assert "cambio_pestana" not in efectiva.scoring_weights


async def test_cache_invalida_por_version(factory) -> None:
    """Tras editar la config (bump de version), la proxima lectura trae lo nuevo."""
    from app.application.config.service import ConfigService
    from app.infrastructure.persistence.repositories.config_sistema import (
        ConfiguracionSistemaSqlRepository,
    )

    async with factory() as s:
        await ConfiguracionSistemaSqlRepository(s).ensure_singleton()
        await s.commit()

    svc = ConfigService(factory)
    primera = await svc.get_efectiva()
    assert primera.umbral_cola_revision == 70

    # Edita por fuera del servicio y avisa la invalidacion.
    async with factory() as s2:
        await ConfiguracionSistemaSqlRepository(s2).update({"umbral_cola_revision": 90})
        await s2.commit()
    svc.invalidate()

    segunda = await svc.get_efectiva()
    assert segunda.umbral_cola_revision == 90
    assert segunda.version == primera.version + 1
