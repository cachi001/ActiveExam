"""Auto-finalización lazy al leer Resultados del docente (C-72 §4 extendido, gap C-73).

Antes, el lazy-finalize (`auto_finalizar_si_vencida`) SOLO se disparaba desde el
lado alumno (crear/reanudar sesión). Si el alumno abandonaba y nadie más tocaba
la sesión, quedaba `finalizada_en = NULL` para siempre: invisible en "Sesiones
finalizadas" pero seguía contando en "Sesiones iniciadas". Este test prueba que
`listar_resultados_examen` (el read-model que alimenta Resultados del docente)
detecta y cierra esas sesiones ANTES de armar la respuesta, reusando
EXACTAMENTE el mismo camino de finalización + write-back que la finalización
manual (`finalizar_sesion_con_writeback`), contra DB real (sin mocks, regla #4).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.moodle.resultados_query import listar_resultados_examen
from app.infrastructure.persistence.models.exam_content import ExamenContenidoModel
from app.infrastructure.persistence.models.moodle_writeback import (
    RespuestaAlumnoModel,
)
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
from app.infrastructure.persistence.session_activeexam import (
    create_activeexam_engine,
    create_activeexam_session_factory,
)


def _factory() -> async_sessionmaker[AsyncSession]:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://proctoring:dev-only-change-me@postgres:5432/proctoring",
    )
    return create_activeexam_session_factory(create_activeexam_engine(url))


def _suf() -> str:
    return uuid.uuid4().hex[:8]


async def _crear_examen(factory, *, tiempo_limite_min: int, cierre) -> str:
    async with factory() as s:
        ex = ExamenContenidoModel(
            titulo=f"c73-autofin-{_suf()}",
            tiempo_limite_min=tiempo_limite_min,
            cierre=cierre,
            nota_maxima=10,
        )
        s.add(ex)
        await s.flush()
        eid = ex.id
        await s.commit()
        return eid


async def _crear_sesion_vencida_sin_finalizar(
    factory, examen_id: str, *, creada_hace_min: int
) -> str:
    async with factory() as s:
        sesion = ProctoringSessionModel(
            modo="examen",
            examen_contenido_id=examen_id,
            etiqueta=f"autofin-{_suf()}",
            alumno_idnumber=f"leg-{_suf()}",
            alumno_email=f"{_suf()}@u.edu",
        )
        s.add(sesion)
        await s.flush()
        sid = sesion.id
        # creada_en tiene server_default; se pisa server-side para simular abandono.
        from sqlalchemy import update

        await s.execute(
            update(ProctoringSessionModel)
            .where(ProctoringSessionModel.id == sid)
            .values(
                creada_en=datetime.now(timezone.utc)
                - timedelta(minutes=creada_hace_min)
            )
        )
        await s.commit()
        return sid


async def _cleanup(factory, examen_id: str, sids: list[str]) -> None:
    async with factory() as s:
        await s.execute(
            delete(RespuestaAlumnoModel).where(
                RespuestaAlumnoModel.session_id.in_(sids)
            )
        )
        for sid in sids:
            await s.execute(
                delete(ProctoringSessionModel).where(
                    ProctoringSessionModel.id == sid
                )
            )
        await s.execute(
            delete(ExamenContenidoModel).where(ExamenContenidoModel.id == examen_id)
        )
        await s.commit()


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_sesion_vencida_sin_finalizar_aparece_finalizada_en_resultados() -> None:
    """Sesión abandonada (deadline hace rato, finalizada_en NULL) -> el docente que
    consulta Resultados la ve YA finalizada, con nota calculada."""
    factory = _factory()
    ahora = datetime.now(timezone.utc)
    # tiempo_limite_min=5, creada hace 60' -> vencida hace rato. cierre lejano
    # para que el límite individual sea el que decide (no el cierre de ventana).
    eid = await _crear_examen(
        factory, tiempo_limite_min=5, cierre=ahora + timedelta(days=1)
    )
    sid = await _crear_sesion_vencida_sin_finalizar(factory, eid, creada_hace_min=60)
    try:
        async with factory() as s:
            items, total = await listar_resultados_examen(db=s, examen_id=eid)

        assert total == 1
        assert len(items) == 1
        assert items[0].session_id == sid
        # Nota calculada (sin respuestas = 0.0), no None: la sesión se cerró y
        # se puntuó, no quedó fantasma.
        assert items[0].nota == 0.0

        # Persistido: finalizada_en ya no es NULL en la DB.
        async with factory() as s:
            sesion = await s.get(ProctoringSessionModel, sid)
            assert sesion.finalizada_en is not None
    finally:
        await _cleanup(factory, eid, [sid])


@pytest.mark.requires_stack
@pytest.mark.asyncio
async def test_sesion_no_vencida_sin_finalizar_no_aparece() -> None:
    """Sesión en curso (deadline lejano, finalizada_en NULL) -> NO se toca ni
    aparece en Resultados (que solo lista finalizadas)."""
    factory = _factory()
    ahora = datetime.now(timezone.utc)
    eid = await _crear_examen(
        factory, tiempo_limite_min=120, cierre=ahora + timedelta(days=1)
    )
    sid = await _crear_sesion_vencida_sin_finalizar(factory, eid, creada_hace_min=5)
    try:
        async with factory() as s:
            items, total = await listar_resultados_examen(db=s, examen_id=eid)

        assert total == 0
        assert items == []

        async with factory() as s:
            sesion = await s.get(ProctoringSessionModel, sid)
            assert sesion.finalizada_en is None
    finally:
        await _cleanup(factory, eid, [sid])
