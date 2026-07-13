"""C-71 slice 1 — consultas base del gate de inscripción (DB real, sin mocks).

Verifica la resolución identidad→inscripción por `id_institucional`:
- `esta_inscripto_institucional(id_institucional, comision_id)` → bool.
- `comision_ids_inscriptas(id_institucional)` → ids de comisiones inscriptas.

Correr:
    DATABASE_URL=postgresql+asyncpg://... RUN_STACK_TESTS=1 \
      pytest tests/test_c71_inscripcion_gate_queries.py -v
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


async def _crear_alumno_y_comision(factory) -> tuple[str, str]:
    """Crea un alumno y una comisión; devuelve (id_institucional, comision_id)."""
    suf = uuid.uuid4().hex[:8]
    async with factory() as s:
        u = UsuarioModel(
            id_institucional=f"gate-{suf}",
            email=f"gate-{suf}@test.local",
            roles=["estudiante"],
            auth_provider="jwt",
        )
        m = MateriaModel(codigo=f"MAT{suf}", nombre="Materia Gate")
        s.add_all([u, m])
        await s.flush()
        c = ComisionModel(
            materia_id=m.id,
            codigo="C1",
            nombre="Comisión Gate",
            periodo="1C",
            anio=2026,
            codigo_matriculacion=f"GATE-{suf}",
        )
        s.add(c)
        await s.commit()
        return u.id_institucional, c.id


async def test_esta_inscripto_true_solo_si_hay_inscripcion(factory) -> None:
    idn, comision_id = await _crear_alumno_y_comision(factory)
    async with factory() as s:
        repo = InscripcionSqlRepository(s)
        # Sin inscripción → False
        assert await repo.esta_inscripto_institucional(idn, comision_id) is False
        # Inscribir y verificar True
        usuario_id = await repo.obtener_usuario_id_por_institucional(idn)
        await repo.inscribir(usuario_id, comision_id)
        await s.commit()
    async with factory() as s:
        repo = InscripcionSqlRepository(s)
        assert await repo.esta_inscripto_institucional(idn, comision_id) is True


async def test_esta_inscripto_false_si_id_institucional_no_existe(factory) -> None:
    _, comision_id = await _crear_alumno_y_comision(factory)
    async with factory() as s:
        repo = InscripcionSqlRepository(s)
        assert await repo.esta_inscripto_institucional("no-existe-xyz", comision_id) is False


async def test_comision_ids_inscriptas(factory) -> None:
    idn, comision_id = await _crear_alumno_y_comision(factory)
    async with factory() as s:
        repo = InscripcionSqlRepository(s)
        # Sin inscripciones → vacío
        assert await repo.comision_ids_inscriptas(idn) == []
        usuario_id = await repo.obtener_usuario_id_por_institucional(idn)
        await repo.inscribir(usuario_id, comision_id)
        await s.commit()
    async with factory() as s:
        repo = InscripcionSqlRepository(s)
        ids = await repo.comision_ids_inscriptas(idn)
        assert ids == [comision_id]
