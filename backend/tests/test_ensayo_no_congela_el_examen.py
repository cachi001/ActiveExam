"""Ensayar el examen no puede congelarlo.

Por qué existe
--------------
El candado post-rendición congela la mecánica y la nota del examen en cuanto hay
UNA sesión finalizada: nota máxima, nota de aprobación, tiempo límite, mezclar
preguntas y apertura. Está bien — cambiar eso después reescribiría la nota de
quien ya rindió.

El problema: contaba **cualquier** sesión finalizada, sin excluir los ENSAYOS.
Y el ensayo del docente (modo prueba, migración 0102/0105) existe justamente para
probar el examen sin ensuciar nada: no cuenta como intento, no genera nota, no va
a Moodle y se puede borrar.

Verificado contra el sistema andando el 2/9/2026: puse el examen en modo prueba,
hice un ensayo, lo finalicé, y el examen quedó `bloqueada: true`. Intentar cambiar
el tiempo límite o la nota máxima devolvía 409. O sea que **ensayar el examen
dejaba al docente sin poder ajustarlo**, que es lo contrario de para qué está el
modo prueba.

La inconsistencia que lo delata: el contador de intentos del sorteo SÍ excluye los
ensayos (mostraba 0), pero este candado no. Dos partes del sistema contando
distinto lo mismo.

Contra DB REAL, sin mocks (regla dura de código).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.exam_content.entities import (
    ExamenContenido,
    OpcionRespuesta,
    Pregunta,
)
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ExamenContenidoModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.models.proctoring import (  # noqa: F401
    ProctoringSessionModel,
)
from app.infrastructure.persistence.repositories.exam_content import (
    ExamenContenidoSqlRepository,
)
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

pytestmark = pytest.mark.asyncio

_TABLAS = ["proctoring_session", "opcion_respuesta", "pregunta_examen", "examen_contenido"]

# Solo lo que el PATCH acepta. `mezclar_preguntas` NO está en ese schema aunque sí
# esté entre los campos congelados: se configura por otro lado.
_CONFIG_VALIDA = {
    "tiempo_limite_min": 60,
    "intentos_permitidos": 2,
    "apertura": "2026-01-01T09:00:00+00:00",
    "cierre": "2026-12-31T20:00:00+00:00",
    "nota_maxima": 10.0,
    "nota_aprobacion": 6.0,
}


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
        for t in _TABLAS:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                ExamenContenidoModel.__table__,
                PreguntaExamenModel.__table__,
                OpcionRespuestaModel.__table__,
                ProctoringSessionModel.__table__,
            ],
        )
    yield eng
    async with eng.begin() as conn:
        for t in _TABLAS:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def app(factory):
    application = FastAPI()
    application.state.jwt_validator = _build_test_jwt_validator()
    application.include_router(
        create_exam_content_router(session_factory=factory, writeback_svc=None),
        prefix="/api/v1/exam-content",
    )
    return application


def _cliente(app):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["admin_sistema"]),
    )


async def _crear_examen(factory) -> str:
    async with factory() as s:
        guardado = await ExamenContenidoSqlRepository(s).guardar(
            ExamenContenido(
                titulo="Examen",
                comision_id=None,
                preguntas=(
                    Pregunta(
                        enunciado="Q0",
                        tipo="multichoice",
                        orden=0,
                        opciones=(
                            OpcionRespuesta(texto="A", es_correcta=True, orden=0),
                            OpcionRespuesta(texto="B", es_correcta=False, orden=1),
                        ),
                    ),
                ),
            )
        )
        await s.commit()
    return guardado.id


async def _sesion_finalizada(factory, examen_id: str, *, es_prueba: bool) -> None:
    async with factory() as s:
        s.add(
            ProctoringSessionModel(
                modo="examen",
                examen_contenido_id=examen_id,
                finalizada_en=datetime.now(tz=timezone.utc),
                es_prueba=es_prueba,
            )
        )
        await s.commit()


async def _bloqueada(app, examen_id: str) -> bool:
    async with _cliente(app) as c:
        r = await c.get(f"/api/v1/exam-content/{examen_id}/config")
    assert r.status_code == 200, r.text
    return r.json()["bloqueada"]


async def test_un_ensayo_finalizado_no_congela_el_examen(app, factory):
    """El caso del bug: el docente ensaya su examen y ya no lo puede ajustar."""
    examen_id = await _crear_examen(factory)
    await _sesion_finalizada(factory, examen_id, es_prueba=True)

    assert await _bloqueada(app, examen_id) is False, (
        "un ENSAYO congeló el examen: es lo contrario de para qué está el modo prueba"
    )


async def test_despues_de_ensayar_todavia_se_puede_ajustar_el_examen(app, factory):
    """Lo que de verdad importa: que el cambio ENTRE, no solo que el flag diga no."""
    examen_id = await _crear_examen(factory)
    await _sesion_finalizada(factory, examen_id, es_prueba=True)

    async with _cliente(app) as c:
        r = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config",
            json={**_CONFIG_VALIDA, "tiempo_limite_min": 90, "nota_maxima": 20.0},
        )

    assert r.status_code == 200, r.text
    assert r.json()["tiempo_limite_min"] == 90
    assert r.json()["nota_maxima"] == 20.0


async def test_una_rendicion_de_verdad_SI_lo_congela(app, factory):
    """Triangulación: la protección que existe no se puede perder.

    Cambiar la nota máxima con alguien que ya rindió le reescribe la nota a esa
    persona. Eso se sigue bloqueando.
    """
    examen_id = await _crear_examen(factory)
    await _sesion_finalizada(factory, examen_id, es_prueba=False)

    assert await _bloqueada(app, examen_id) is True

    async with _cliente(app) as c:
        r = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config",
            json={**_CONFIG_VALIDA, "nota_maxima": 20.0},
        )

    assert r.status_code == 409, r.text
    assert r.json()["detail"]["error"] == "config_congelada"


async def test_un_ensayo_no_tapa_una_rendicion_real(app, factory):
    """Triangulación al revés: con las dos, manda la real.

    Si el examen se ensayó Y además alguien lo rindió, tiene que quedar congelado.
    Filtrar mal acá dejaría abierto justo el caso peligroso.
    """
    examen_id = await _crear_examen(factory)
    await _sesion_finalizada(factory, examen_id, es_prueba=True)
    await _sesion_finalizada(factory, examen_id, es_prueba=False)

    assert await _bloqueada(app, examen_id) is True


async def test_un_ensayo_sin_finalizar_tampoco_congela(app, factory):
    """Triangulación: solo cuentan las FINALIZADAS, y el ensayo no cuenta nunca."""
    examen_id = await _crear_examen(factory)
    async with factory() as s:
        s.add(
            ProctoringSessionModel(
                modo="examen", examen_contenido_id=examen_id, es_prueba=True
            )
        )
        await s.commit()

    assert await _bloqueada(app, examen_id) is False
