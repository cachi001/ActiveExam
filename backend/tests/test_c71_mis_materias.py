"""C-71 slice 1 — "Mis materias" filtrado por inscripción (DB real).

`InscripcionSqlRepository.materias_inscriptas` / `comisiones_inscriptas_de_materia`:
el alumno ve solo las materias/comisiones donde está inscripto.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.models.exam_content import ComisionModel, MateriaModel
from app.infrastructure.persistence.models.transactional import UsuarioModel
from app.infrastructure.persistence.repositories.exam_content import (
    InscripcionSqlRepository,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada; test de integración (DB real migrada).")
    engine = create_async_engine(url, pool_pre_ping=True, future=True, poolclass=NullPool)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


async def test_mis_materias_solo_inscriptas(factory) -> None:
    suf = uuid.uuid4().hex[:8]
    async with factory() as s:
        u = UsuarioModel(
            id_institucional=f"mm-{suf}", email=f"mm-{suf}@test.local",
            roles=["estudiante"], auth_provider="jwt",
        )
        m_mia = MateriaModel(codigo=f"MIA{suf}", nombre=f"Materia Mía {suf}")
        m_otra = MateriaModel(codigo=f"OTRA{suf}", nombre=f"Materia Otra {suf}")
        s.add_all([u, m_mia, m_otra])
        await s.flush()
        c_mia = ComisionModel(
            materia_id=m_mia.id, codigo="C1", nombre="Com mía",
            periodo="1C", anio=2026, codigo_matriculacion=f"MM-{suf}",
        )
        c_otra = ComisionModel(
            materia_id=m_otra.id, codigo="C1", nombre="Com otra",
            periodo="1C", anio=2026, codigo_matriculacion=f"MO-{suf}",
        )
        s.add_all([c_mia, c_otra])
        await s.commit()
        uid, mia_id, c_mia_id = u.id, m_mia.id, c_mia.id

    async with factory() as s:
        repo = InscripcionSqlRepository(s)
        # Sin inscripciones → sin materias
        assert await repo.materias_inscriptas(f"mm-{suf}") == []
        await repo.inscribir(uid, c_mia_id)
        await s.commit()

    async with factory() as s:
        repo = InscripcionSqlRepository(s)
        materias = await repo.materias_inscriptas(f"mm-{suf}")
        ids = {m.id for m in materias}
        assert ids == {mia_id}  # solo la materia inscripta, no la otra

        coms = await repo.comisiones_inscriptas_de_materia(f"mm-{suf}", mia_id)
        assert [c.id for c in coms] == [c_mia_id]
