"""C-71 slice 1 — catálogo de exámenes filtrado por comisión inscripta (DB real).

`ExamenContenidoSqlRepository.listar_paginado(comision_ids=...)`:
- None  → admin: todo el catálogo.
- [ids] → estudiante: solo exámenes de esas comisiones.
- []    → estudiante sin inscripciones: catálogo vacío.

Correr:
    DATABASE_URL=postgresql+asyncpg://... RUN_STACK_TESTS=1 \
      pytest tests/test_c71_catalogo_filtrado.py -v
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.models.exam_content import (
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
)
from app.infrastructure.persistence.repositories.exam_content import (
    ExamenContenidoSqlRepository,
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


async def _comision(session, suf: str) -> str:
    m = MateriaModel(codigo=f"M{suf}", nombre=f"Materia {suf}")
    session.add(m)
    await session.flush()
    c = ComisionModel(
        materia_id=m.id, codigo="C1", nombre=f"Com {suf}",
        periodo="1C", anio=2026, codigo_matriculacion=f"CAT-{suf}",
    )
    session.add(c)
    await session.flush()
    return c.id


async def test_filtro_por_comision_inscripta(factory) -> None:
    suf = uuid.uuid4().hex[:8]
    async with factory() as s:
        c_mia = await _comision(s, f"mia{suf}")
        c_otra = await _comision(s, f"otra{suf}")
        titulo_mio = f"Examen MIO {suf}"
        titulo_otro = f"Examen OTRO {suf}"
        s.add(ExamenContenidoModel(titulo=titulo_mio, comision_id=c_mia))
        s.add(ExamenContenidoModel(titulo=titulo_otro, comision_id=c_otra))
        await s.commit()

    async with factory() as s:
        repo = ExamenContenidoSqlRepository(s)

        # Estudiante inscripto solo en c_mia → solo ve su examen
        items, _ = await repo.listar_paginado(comision_ids=[c_mia])
        titulos = {i.titulo for i in items}
        assert titulo_mio in titulos
        assert titulo_otro not in titulos

        # Estudiante sin inscripciones → catálogo vacío
        vacio, total = await repo.listar_paginado(comision_ids=[])
        assert vacio == [] and total == 0

        # Admin (None) → ve ambos
        todos, _ = await repo.listar_paginado(comision_ids=None)
        titulos_todos = {i.titulo for i in todos}
        assert titulo_mio in titulos_todos and titulo_otro in titulos_todos
