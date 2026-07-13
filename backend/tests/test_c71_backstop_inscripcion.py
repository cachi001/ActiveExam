"""C-71 slice 1 — backstop server-side de inscripción al crear la sesión (DB real).

`verificar_inscripcion(db, examen_contenido_id, alumno_idnumber)`:
- alumno NO inscripto en la comisión del examen → NoInscriptoError.
- alumno inscripto → no levanta.
- examen sin comisión → no exige inscripción (edge case).

Correr:
    DATABASE_URL=postgresql+asyncpg://... RUN_STACK_TESTS=1 \
      pytest tests/test_c71_backstop_inscripcion.py -v
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.proctoring.enforcement import (
    NoInscriptoError,
    verificar_inscripcion,
)
from app.infrastructure.persistence.models.exam_content import (
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
)
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


async def _armar(factory, *, con_comision: bool = True) -> tuple[str, str, str]:
    """Crea alumno + (materia/comisión) + examen. Devuelve (id_institucional, examen_id, comision_id|'')."""
    suf = uuid.uuid4().hex[:8]
    async with factory() as s:
        u = UsuarioModel(
            id_institucional=f"bk-{suf}", email=f"bk-{suf}@test.local",
            roles=["estudiante"], auth_provider="jwt",
        )
        s.add(u)
        comision_id = None
        if con_comision:
            m = MateriaModel(codigo=f"M{suf}", nombre="Mat")
            s.add(m)
            await s.flush()
            c = ComisionModel(
                materia_id=m.id, codigo="C1", nombre="Com",
                periodo="1C", anio=2026, codigo_matriculacion=f"BK-{suf}",
            )
            s.add(c)
            await s.flush()
            comision_id = c.id
        ex = ExamenContenidoModel(titulo=f"Examen {suf}", comision_id=comision_id)
        s.add(ex)
        await s.commit()
        return u.id_institucional, ex.id, comision_id or ""


async def test_no_inscripto_levanta(factory) -> None:
    idn, examen_id, _ = await _armar(factory)
    async with factory() as s:
        with pytest.raises(NoInscriptoError):
            await verificar_inscripcion(s, examen_contenido_id=examen_id, alumno_idnumber=idn)


async def test_inscripto_no_levanta(factory) -> None:
    idn, examen_id, comision_id = await _armar(factory)
    async with factory() as s:
        repo = InscripcionSqlRepository(s)
        uid = await repo.obtener_usuario_id_por_institucional(idn)
        await repo.inscribir(uid, comision_id)
        await s.commit()
    async with factory() as s:
        # No debe levantar
        await verificar_inscripcion(s, examen_contenido_id=examen_id, alumno_idnumber=idn)


async def test_examen_sin_comision_no_exige_inscripcion(factory) -> None:
    idn, examen_id, _ = await _armar(factory, con_comision=False)
    async with factory() as s:
        await verificar_inscripcion(s, examen_contenido_id=examen_id, alumno_idnumber=idn)
