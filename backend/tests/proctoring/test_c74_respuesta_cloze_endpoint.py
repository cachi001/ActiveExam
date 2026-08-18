"""C-74 §6 — respuestas cloze/ddwtos vía la API real de rendición.

El agujero encontrado en vivo: `POST /sessions/{id}/respuestas` solo aceptaba
`opcion_elegida_id` (multichoice/truefalse). `calcular_nota_academica` SÍ sabe
corregir `respuesta_cloze`, pero ningún endpoint lo alimentaba — una pregunta
cloze/ddwtos en un examen real puntuaba 0 SIEMPRE, aunque el alumno la
contestara perfecto (confirmado con un examen real: 2/5 correctas dio 40.00,
no más, con las 3 cloze en blanco por falta de camino en la API).

Este test cubre el camino nuevo: `RespuestaItem.respuesta_cloze`,
`respuesta_alumno_cloze` (migración 0062), y que `finalizar` combine ambas
fuentes (multichoice + cloze) al calcular la nota.

DB real (regla dura #4: nada de mockear la base).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ExamenContenidoModel,
    OpcionClozeBlancoModel,
    OpcionRespuestaModel,
    PreguntaClozeBlankModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.models.moodle_writeback import (  # noqa: F401
    MoodleWritebackAuditModel,
    MoodleWritebackEstadoModel,
    RespuestaAlumnoClozeModel,
    RespuestaAlumnoModel,
)
from app.infrastructure.persistence.models.chat_pausa import (  # noqa: F401
    MensajeChatModel,
    PausaAutorizadaModel,
)
from app.infrastructure.persistence.models.proctoring import (  # noqa: F401
    ProctoringBiometriaModel,
    ProctoringEventModel,
    ProctoringSessionModel,
)
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

pytestmark = pytest.mark.asyncio

_ALUMNO = "estudiante"

_DROP = [
    "moodle_writeback_audit",
    "moodle_writeback_estado",
    "respuesta_alumno_cloze",
    "respuesta_alumno",
    "mensaje_chat",
    "pausa_autorizada",
    "opcion_cloze_blank",
    "pregunta_cloze_blank",
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "proctoring_biometria",
    "proctoring_event",
    "proctoring_session",
]
_CREATE = [
    ExamenContenidoModel.__table__,
    PreguntaExamenModel.__table__,
    OpcionRespuestaModel.__table__,
    PreguntaClozeBlankModel.__table__,
    OpcionClozeBlancoModel.__table__,
    ProctoringSessionModel.__table__,
    ProctoringEventModel.__table__,
    ProctoringBiometriaModel.__table__,
    RespuestaAlumnoModel.__table__,
    RespuestaAlumnoClozeModel.__table__,
    PausaAutorizadaModel.__table__,
    MensajeChatModel.__table__,
    MoodleWritebackEstadoModel.__table__,
    MoodleWritebackAuditModel.__table__,
]


@pytest.fixture(scope="module")
def db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada — tests de integración omitidos")
    return url


@pytest_asyncio.fixture(scope="module")
async def engine(db_url: str):
    eng = create_async_engine(db_url, pool_pre_ping=True, future=True, poolclass=NullPool)
    async with eng.begin() as conn:
        for t in _DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
        await conn.run_sync(Base.metadata.create_all, tables=_CREATE)
    yield eng
    async with eng.begin() as conn:
        for t in _DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
    await eng.dispose()


@pytest.fixture(scope="module")
def reinferencia():
    from app.infrastructure.reinferencia.mediapipe_adapter import MediaPipeReinferencia

    return MediaPipeReinferencia()


@pytest.fixture(scope="module")
def app(engine, reinferencia):
    from fastapi import FastAPI

    from app.infrastructure.persistence.session_activeexam import create_activeexam_session_factory
    from app.presentation.api.v1.proctoring.router import create_proctoring_router

    factory = create_activeexam_session_factory(engine)
    router = create_proctoring_router(
        session_factory=factory,
        reinferencia=reinferencia,
        writeback_svc=None,
    )
    a = FastAPI()
    a.state.jwt_validator = _build_test_jwt_validator()
    a.include_router(router, prefix="/api/v1/proctoring")
    return a


@pytest_asyncio.fixture(autouse=True)
async def _limpiar(engine):
    async with engine.begin() as conn:
        nombres = ", ".join(f'"{t}"' for t in _DROP)
        await conn.execute(text(f"TRUNCATE {nombres} RESTART IDENTITY CASCADE"))
    yield


@pytest_asyncio.fixture
async def db(engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
        await s.rollback()


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["estudiante"], username="estudiante", email="test@uni.edu"),
    ) as c:
        yield c


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _crear_examen_con_cloze(db: AsyncSession) -> dict:
    """Examen con 1 pregunta cloze (2 blanks MULTICHOICE) + 1 multichoice normal.

    Devuelve ids: examen_id, pregunta_cloze_id, blank_ids (2), opcion_correcta_por_blank,
    pregunta_mc_id, opcion_correcta_mc_id.
    """
    examen = ExamenContenidoModel(
        titulo="Examen con cloze",
        apertura=_now() - timedelta(hours=1),
        cierre=_now() + timedelta(hours=4),
        nota_maxima=100,
        nota_aprobacion=60,
    )
    db.add(examen)
    await db.flush()

    pregunta_cloze = PreguntaExamenModel(
        examen_id=examen.id, enunciado="Complete: __ + __", tipo="cloze", orden=0,
        seleccionada=True,
    )
    db.add(pregunta_cloze)
    await db.flush()

    blank_ids = []
    correctas_por_blank = {}
    for orden, (correcta, incorrecta) in enumerate((("uno", "dos"), ("tres", "cuatro"))):
        blank = PreguntaClozeBlankModel(
            pregunta_id=pregunta_cloze.id, orden=orden, tipo="multichoice",
            texto_antes="", texto_despues="",
        )
        db.add(blank)
        await db.flush()
        blank_ids.append(blank.id)
        opcion_correcta = OpcionClozeBlancoModel(
            blank_id=blank.id, texto=correcta, es_correcta=True, peso=100,
        )
        opcion_incorrecta = OpcionClozeBlancoModel(
            blank_id=blank.id, texto=incorrecta, es_correcta=False, peso=0,
        )
        db.add_all([opcion_correcta, opcion_incorrecta])
        await db.flush()
        correctas_por_blank[blank.id] = opcion_correcta.id

    pregunta_mc = PreguntaExamenModel(
        examen_id=examen.id, enunciado="2+2?", tipo="multichoice", orden=1,
        seleccionada=True,
    )
    db.add(pregunta_mc)
    await db.flush()
    opcion_mc = OpcionRespuestaModel(pregunta_id=pregunta_mc.id, texto="4", es_correcta=True, orden=0)
    db.add(opcion_mc)
    await db.commit()

    return {
        "examen_id": examen.id,
        "pregunta_cloze_id": pregunta_cloze.id,
        "blank_ids": blank_ids,
        "correctas_por_blank": correctas_por_blank,
        "pregunta_mc_id": pregunta_mc.id,
        "opcion_mc_id": opcion_mc.id,
    }


async def _crear_sesion(db: AsyncSession, *, examen_contenido_id: str) -> str:
    sesion = ProctoringSessionModel(
        modo="examen",
        examen_contenido_id=examen_contenido_id,
        alumno_idnumber=_ALUMNO,
        alumno_email="test@uni.edu",
    )
    db.add(sesion)
    await db.commit()
    await db.refresh(sesion)
    return sesion.id


@pytest.mark.asyncio
async def test_submit_respuesta_cloze_201(client: AsyncClient, db: AsyncSession):
    """RED→GREEN: enviar respuesta_cloze para una pregunta cloze devuelve 201."""
    datos = await _crear_examen_con_cloze(db)
    session_id = await _crear_sesion(db, examen_contenido_id=datos["examen_id"])
    b0, b1 = datos["blank_ids"]

    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/respuestas",
        json={
            "respuestas": [
                {
                    "pregunta_id": datos["pregunta_cloze_id"],
                    "respuesta_cloze": {
                        b0: datos["correctas_por_blank"][b0],
                        b1: datos["correctas_por_blank"][b1],
                    },
                }
            ]
        },
    )
    assert resp.status_code == 201, resp.text
    # Se aplana a una fila por blank: 1 pregunta con 2 blanks → 2 guardadas.
    assert resp.json()["respuestas_guardadas"] == 2


@pytest.mark.asyncio
async def test_finalizar_calcula_nota_con_cloze_y_multichoice(
    client: AsyncClient, db: AsyncSession
):
    """TRIANGULATE: examen mixto (1 cloze 2/2 blanks + 1 multichoice correcta) → nota 100."""
    datos = await _crear_examen_con_cloze(db)
    session_id = await _crear_sesion(db, examen_contenido_id=datos["examen_id"])
    b0, b1 = datos["blank_ids"]

    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/respuestas",
        json={
            "respuestas": [
                {
                    "pregunta_id": datos["pregunta_cloze_id"],
                    "respuesta_cloze": {
                        b0: datos["correctas_por_blank"][b0],
                        b1: datos["correctas_por_blank"][b1],
                    },
                },
                {
                    "pregunta_id": datos["pregunta_mc_id"],
                    "opcion_elegida_id": datos["opcion_mc_id"],
                },
            ]
        },
    )
    assert resp.status_code == 201, resp.text

    resp = await client.patch(f"/api/v1/proctoring/sessions/{session_id}/finalizar")
    assert resp.status_code == 200, resp.text

    row = await db.execute(
        text("SELECT nota FROM moodle_writeback_estado WHERE session_id = :sid"),
        {"sid": session_id},
    )
    nota = row.scalar_one()
    assert float(nota) == 100.0, f"Esperaba 100.0 (2/2 preguntas), obtuvo {nota}"


@pytest.mark.asyncio
async def test_finalizar_cloze_parcial_da_nota_parcial(client: AsyncClient, db: AsyncSession):
    """TRIANGULATE: 1 de 2 blanks correcto → esa pregunta cuenta 0.5, nota = 50/2preg = ...

    2 preguntas en el examen: cloze (1/2 blanks = 0.5 slots) + multichoice sin
    responder (0). Total: 0.5/2 * 100 = 25.0.
    """
    datos = await _crear_examen_con_cloze(db)
    session_id = await _crear_sesion(db, examen_contenido_id=datos["examen_id"])
    b0, b1 = datos["blank_ids"]

    # b0 correcto, b1 incorrecto (elige la opción no marcada como correcta)
    incorrecta_b1 = await db.execute(
        text(
            "SELECT id FROM opcion_cloze_blank WHERE blank_id = :bid AND es_correcta = false"
        ),
        {"bid": b1},
    )
    incorrecta_b1_id = str(incorrecta_b1.scalar_one())

    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/respuestas",
        json={
            "respuestas": [
                {
                    "pregunta_id": datos["pregunta_cloze_id"],
                    "respuesta_cloze": {
                        b0: datos["correctas_por_blank"][b0],
                        b1: incorrecta_b1_id,
                    },
                }
            ]
        },
    )
    assert resp.status_code == 201, resp.text

    resp = await client.patch(f"/api/v1/proctoring/sessions/{session_id}/finalizar")
    assert resp.status_code == 200, resp.text

    row = await db.execute(
        text("SELECT nota FROM moodle_writeback_estado WHERE session_id = :sid"),
        {"sid": session_id},
    )
    nota = row.scalar_one()
    assert float(nota) == 25.0, f"Esperaba 25.0, obtuvo {nota}"


@pytest.mark.asyncio
async def test_resumir_sesion_trae_respuestas_cloze(client: AsyncClient, db: AsyncSession):
    """TRIANGULATE (vuln reload): GET /respuestas devuelve el dict de blanks completo."""
    datos = await _crear_examen_con_cloze(db)
    session_id = await _crear_sesion(db, examen_contenido_id=datos["examen_id"])
    b0, b1 = datos["blank_ids"]

    await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/respuestas",
        json={
            "respuestas": [
                {
                    "pregunta_id": datos["pregunta_cloze_id"],
                    "respuesta_cloze": {
                        b0: datos["correctas_por_blank"][b0],
                        b1: datos["correctas_por_blank"][b1],
                    },
                }
            ]
        },
    )

    resp = await client.get(f"/api/v1/proctoring/sessions/{session_id}/respuestas")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["respuestas"]) == 1
    item = body["respuestas"][0]
    assert item["pregunta_id"] == datos["pregunta_cloze_id"]
    assert item["respuesta_cloze"] == {
        b0: datos["correctas_por_blank"][b0],
        b1: datos["correctas_por_blank"][b1],
    }


@pytest.mark.asyncio
async def test_respuesta_con_ambos_campos_422(client: AsyncClient, db: AsyncSession):
    """TRIANGULATE borde: mandar opcion_elegida_id Y respuesta_cloze a la vez → 422."""
    datos = await _crear_examen_con_cloze(db)
    session_id = await _crear_sesion(db, examen_contenido_id=datos["examen_id"])

    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/respuestas",
        json={
            "respuestas": [
                {
                    "pregunta_id": datos["pregunta_mc_id"],
                    "opcion_elegida_id": datos["opcion_mc_id"],
                    "respuesta_cloze": {"x": "y"},
                }
            ]
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_respuesta_sin_ningun_campo_422(client: AsyncClient, db: AsyncSession):
    """TRIANGULATE borde: no mandar ninguno de los dos → 422."""
    datos = await _crear_examen_con_cloze(db)
    session_id = await _crear_sesion(db, examen_contenido_id=datos["examen_id"])

    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/respuestas",
        json={"respuestas": [{"pregunta_id": datos["pregunta_mc_id"]}]},
    )
    assert resp.status_code == 422
