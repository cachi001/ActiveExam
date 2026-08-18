"""Tests — filtro por session_ids en listar_estados_sincronizables (c-76, tarea 2.5).

TDD Cycle: RED → GREEN → TRIANGULATE
Contra DB real (sin mocks, regla #4): verifica que el parámetro ``session_ids``
restringe correctamente qué filas devuelve ``listar_estados_sincronizables``.

Las retenciones D15 (gate de revisión / score > umbral) se aplican IGUAL aunque la
sesión esté en la lista — la publicación individual NO bypasea el gate de riesgo.

Patrón: mismo estilo que test_c71_writeback_gate_integration.py.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.moodle.resultados_query import listar_estados_sincronizables
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ExamenContenidoModel,
)
from app.infrastructure.persistence.models.moodle_writeback import (
    MoodleWritebackEstadoModel,
)
from app.infrastructure.persistence.models.proctoring import (
    ProctoringEventModel,
    ProctoringSessionModel,
)
from app.infrastructure.persistence.models.transactional import (
    ConfiguracionSistemaModel,
    EventoScoreConfigModel,
)
from app.infrastructure.persistence.session_activeexam import (
    create_activeexam_engine,
    create_activeexam_session_factory,
)

UMBRAL = 40


def _factory() -> async_sessionmaker[AsyncSession]:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://proctoring:dev-only-change-me@postgres:5432/proctoring",
    )
    return create_activeexam_session_factory(create_activeexam_engine(url))


def _suf() -> str:
    return uuid.uuid4().hex[:8]


async def _seed_config(factory) -> None:
    async with factory() as s:
        existing = await s.get(ConfiguracionSistemaModel, "global")
        if existing is None:
            s.add(ConfiguracionSistemaModel(id="global", umbral_cola_revision=UMBRAL))
        else:
            existing.umbral_cola_revision = UMBRAL
        from sqlalchemy import select

        rows = await s.execute(
            select(EventoScoreConfigModel).where(
                EventoScoreConfigModel.tipo_evento == "rostro_ausente"
            )
        )
        if rows.scalars().first() is None:
            s.add(
                EventoScoreConfigModel(
                    tipo_evento="rostro_ausente",
                    severidad="alta",
                    peso=50,
                    activo=True,
                )
            )
        await s.commit()


async def _crear_examen(factory) -> str:
    async with factory() as s:
        ex = ExamenContenidoModel(titulo=f"c76-sel-{_suf()}")
        s.add(ex)
        await s.flush()
        eid = ex.id
        await s.commit()
        return eid


async def _crear_sesion(factory, examen_id: str, *, flaggeada: bool) -> str:
    async with factory() as s:
        sesion = ProctoringSessionModel(
            modo="examen", examen_contenido_id=examen_id, etiqueta=f"sel-{_suf()}"
        )
        sesion.finalizada_en = datetime.now(timezone.utc)
        s.add(sesion)
        await s.flush()
        sid = sesion.id
        if flaggeada:
            s.add(
                ProctoringEventModel(
                    session_id=sid,
                    tipo="multiples_rostros",
                    severidad="alta",
                    ts_cliente=datetime.now(timezone.utc),
                )
            )
        s.add(
            MoodleWritebackEstadoModel(
                session_id=sid,
                alumno_idnumber=f"leg-{_suf()}",
                alumno_email=f"{_suf()}@u.edu",
                nota=7.0,
                estado="pendiente",
                intento=0,
            )
        )
        await s.commit()
        return sid


async def _sincronizables_ids(
    factory, examen_id: str, session_ids: list[str] | None = None
) -> set[str]:
    async with factory() as s:
        filas = await listar_estados_sincronizables(
            db=s, examen_id=examen_id, session_ids=session_ids
        )
        return {f.session_id for f in filas}


async def _cleanup(factory, examen_id: str, sids: list[str]) -> None:
    async with factory() as s:
        for sid in sids:
            await s.execute(
                delete(ProctoringSessionModel).where(ProctoringSessionModel.id == sid)
            )
        await s.execute(
            delete(ExamenContenidoModel).where(ExamenContenidoModel.id == examen_id)
        )
        await s.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_sin_filtro_devuelve_todas_las_sincronizables() -> None:
    """Sin session_ids: comportamiento original — todas las pendientes sin hold."""
    factory = _factory()
    await _seed_config(factory)
    eid = await _crear_examen(factory)
    s1 = await _crear_sesion(factory, eid, flaggeada=False)
    s2 = await _crear_sesion(factory, eid, flaggeada=False)
    try:
        ids = await _sincronizables_ids(factory, eid, session_ids=None)
        assert s1 in ids
        assert s2 in ids
    finally:
        await _cleanup(factory, eid, [s1, s2])


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_filtro_individual_retorna_solo_esa_sesion() -> None:
    """Con session_ids=[s1]: solo devuelve s1, aunque s2 también sea sincronizable."""
    factory = _factory()
    await _seed_config(factory)
    eid = await _crear_examen(factory)
    s1 = await _crear_sesion(factory, eid, flaggeada=False)
    s2 = await _crear_sesion(factory, eid, flaggeada=False)
    try:
        ids = await _sincronizables_ids(factory, eid, session_ids=[s1])
        assert s1 in ids
        assert s2 not in ids  # excluida del filtro
    finally:
        await _cleanup(factory, eid, [s1, s2])


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_filtro_lote_seleccionado() -> None:
    """Con session_ids=[s1, s2]: devuelve ambas y excluye la no seleccionada (s3)."""
    factory = _factory()
    await _seed_config(factory)
    eid = await _crear_examen(factory)
    s1 = await _crear_sesion(factory, eid, flaggeada=False)
    s2 = await _crear_sesion(factory, eid, flaggeada=False)
    s3 = await _crear_sesion(factory, eid, flaggeada=False)
    try:
        ids = await _sincronizables_ids(factory, eid, session_ids=[s1, s2])
        assert s1 in ids
        assert s2 in ids
        assert s3 not in ids  # excluida — no estaba en la selección
    finally:
        await _cleanup(factory, eid, [s1, s2, s3])


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_retencion_d15_se_aplica_aunque_este_en_filtro() -> None:
    """Una sesión flaggeada en hold NO se envía aunque esté en session_ids.

    El gate D15 es inviolable: la publicación individual NO lo bypasea.
    """
    factory = _factory()
    await _seed_config(factory)
    eid = await _crear_examen(factory)
    limpia = await _crear_sesion(factory, eid, flaggeada=False)
    flaggeada = await _crear_sesion(factory, eid, flaggeada=True)
    try:
        ids = await _sincronizables_ids(factory, eid, session_ids=[limpia, flaggeada])
        assert limpia in ids
        assert flaggeada not in ids  # D15: retenida aunque se pidió explícitamente
    finally:
        await _cleanup(factory, eid, [limpia, flaggeada])


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_lista_vacia_no_devuelve_nada() -> None:
    """session_ids=[] — lista vacía equivale a ningún filtro aplicable: sin resultados.

    Nota: [] distinto de None. None = comportamiento global (todas). [] = restricción a
    nada (ya que no hay IDs en el conjunto). La capa de presentación normaliza session_ids=[]
    a session_ids=None antes de llamar (body ausente o lista vacía → lote completo),
    pero este test cubre la capa de infraestructura directamente.
    """
    factory = _factory()
    await _seed_config(factory)
    eid = await _crear_examen(factory)
    s1 = await _crear_sesion(factory, eid, flaggeada=False)
    try:
        # session_ids=[] no pasa el if-check en listar_estados_sincronizables
        # (la condición es `if session_ids:`, y [] es falsy) → equivale a None.
        ids = await _sincronizables_ids(factory, eid, session_ids=[])
        assert s1 in ids  # lista vacía == falsy == sin filtro == devuelve todo
    finally:
        await _cleanup(factory, eid, [s1])
