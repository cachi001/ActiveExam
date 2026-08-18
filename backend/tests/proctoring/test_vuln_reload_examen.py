"""Vulnerabilidad de integridad de examen (CRITICA) — reload durante la rendicion.

Root cause (confirmado leyendo el codigo antes del fix):
  1. `respuestas` en el frontend es solo React state — se pierde al recargar.
  2. `proctoringSessionId` NO se persistia — al recargar quedaba null.
  3. El hook de proctoring creaba sesion `if (!proctoringSessionId)` -> recargar
     creaba una sesion NUEVA.
  4. `crear_sesion` (backend) NUNCA chequeaba si ya habia una sesion ACTIVA
     (`finalizada_en IS NULL`) del alumno para ese examen -> siempre creaba una
     fila nueva; la vieja quedaba "zombie" en vivo para siempre.
  5. El enforcement de intentos cuenta SOLO `finalizada_en IS NOT NULL` -> la
     zombie no consumia intento -> intentos efectivamente infinitos + timer
     reseteado (nueva `creada_en`) + respuestas perdidas.

Este archivo prueba el FIX server-side (anti-zombie idempotente + endpoint de
respuestas del dueño). DB real (DATABASE_URL). Sin mocks de DB (regla dura de
codigo). El finalizar-sesion dispara el calculo de nota (calcular_nota_academica),
que consulta `respuesta_alumno` — por eso el engine de este archivo crea el set
completo de tablas del circuito de rendicion (mismo patron que
`test_c69_sesion_propiedad.py`), no solo las 3 tablas activeexam del conftest base.

Correr:
    DATABASE_URL=postgresql+asyncpg://... pytest tests/proctoring/test_vuln_reload_examen.py -v
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ExamenContenidoModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.models.moodle_writeback import (  # noqa: F401
    MoodleWritebackAuditModel,
    MoodleWritebackEstadoModel,
    RespuestaAlumnoModel,
)
from app.infrastructure.persistence.models.proctoring import (  # noqa: F401
    ProctoringBiometriaModel,
    ProctoringEventModel,
    ProctoringSessionModel,
)
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

pytestmark = pytest.mark.asyncio

_BASE = "/api/v1/proctoring"

_DROP = [
    "moodle_writeback_audit",
    "moodle_writeback_estado",
    "respuesta_alumno",
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
    ProctoringSessionModel.__table__,
    ProctoringEventModel.__table__,
    ProctoringBiometriaModel.__table__,
    RespuestaAlumnoModel.__table__,
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


async def _crear_examen(
    db: AsyncSession,
    *,
    intentos_permitidos: int = 3,
    apertura: datetime | None = None,
    cierre: datetime | None = None,
) -> str:
    examen = ExamenContenidoModel(
        titulo="Examen vuln reload",
        apertura=apertura,
        cierre=cierre,
        intentos_permitidos=intentos_permitidos,
    )
    db.add(examen)
    await db.commit()
    await db.refresh(examen)
    return examen.id


async def _crear_examen_1pregunta(db: AsyncSession) -> tuple[str, str, str]:
    examen = ExamenContenidoModel(titulo="Vuln reload — respuestas", nota_maxima=10)
    db.add(examen)
    await db.flush()
    pregunta = PreguntaExamenModel(
        examen_id=examen.id, enunciado="2+2?", tipo="multichoice", orden=0, seleccionada=True
    )
    db.add(pregunta)
    await db.flush()
    opcion = OpcionRespuestaModel(pregunta_id=pregunta.id, texto="4", es_correcta=True, orden=0)
    db.add(opcion)
    await db.commit()
    return examen.id, pregunta.id, opcion.id


async def _contar_sesiones(db: AsyncSession, examen_id: str) -> int:
    await db.commit()  # ver lo committeado por el request
    result = await db.execute(
        select(func.count())
        .select_from(ProctoringSessionModel)
        .where(ProctoringSessionModel.examen_contenido_id == examen_id)
    )
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Caso feliz: segundo POST del mismo alumno+examen reanuda (no crea zombie)
# ---------------------------------------------------------------------------


async def test_segundo_post_mismo_alumno_examen_devuelve_misma_sesion(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Simula un F5 durante el examen: el 2do POST /sessions NO crea una fila nueva.

    Devuelve la MISMA id y la MISMA `creada_en` (el timer se ancla al original).
    """
    examen_id = await _crear_examen(db)

    r1 = await client.post(
        f"{_BASE}/sessions",
        json={"modo": "examen", "examen_contenido_id": examen_id},
    )
    assert r1.status_code == 201, r1.text
    body1 = r1.json()

    r2 = await client.post(
        f"{_BASE}/sessions",
        json={"modo": "examen", "examen_contenido_id": examen_id},
    )
    assert r2.status_code == 201, r2.text
    body2 = r2.json()

    assert body2["id"] == body1["id"], "el reload debe REANUDAR la misma sesion, no crear otra"
    assert body2["creada_en"] == body1["creada_en"], "el timer debe anclarse a la creada_en ORIGINAL"
    assert await _contar_sesiones(db, examen_id) == 1


async def test_reload_no_consume_intento(client: AsyncClient, db: AsyncSession) -> None:
    """Con intentos_permitidos=1, tres 'reloads' seguidos NO agotan el intento
    y NO acumulan sesiones zombie de por medio."""
    examen_id = await _crear_examen(db, intentos_permitidos=1)

    ids = []
    for _ in range(3):
        resp = await client.post(
            f"{_BASE}/sessions",
            json={"modo": "examen", "examen_contenido_id": examen_id},
        )
        assert resp.status_code == 201, resp.text
        ids.append(resp.json()["id"])

    assert len(set(ids)) == 1, "los 3 reloads deben resolver a la MISMA sesion"
    assert await _contar_sesiones(db, examen_id) == 1, "no debe quedar ninguna zombie"

    fin = await client.patch(f"{_BASE}/sessions/{ids[0]}/finalizar")
    assert fin.status_code == 200, fin.text

    resp = await client.post(
        f"{_BASE}/sessions",
        json={"modo": "examen", "examen_contenido_id": examen_id},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "intentos_agotados"


async def test_reanudacion_no_aplica_a_otro_alumno(client: AsyncClient, db: AsyncSession) -> None:
    """La reanudacion es por (alumno, examen): otro alumno con el mismo examen
    NO reusa la sesion activa ajena — obtiene la suya propia (edge case IDOR)."""
    examen_id = await _crear_examen(db)

    r1 = await client.post(
        f"{_BASE}/sessions",
        json={"modo": "examen", "examen_contenido_id": examen_id},
    )
    assert r1.status_code == 201
    sid_alumno1 = r1.json()["id"]

    r2 = await client.post(
        f"{_BASE}/sessions",
        json={"modo": "examen", "examen_contenido_id": examen_id},
        headers=auth_headers(["estudiante"], username="otro-alumno", email="otro@uni.edu"),
    )
    assert r2.status_code == 201
    sid_alumno2 = r2.json()["id"]

    assert sid_alumno1 != sid_alumno2
    assert await _contar_sesiones(db, examen_id) == 2


# ---------------------------------------------------------------------------
# GET /sessions/{id}/respuestas — reanudacion de respuestas ya guardadas
# ---------------------------------------------------------------------------


async def test_obtener_respuestas_restaura_lo_ya_guardado(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Tras un 'reload' (reanudar la misma sesion), GET .../respuestas devuelve
    lo que el alumno ya habia contestado antes del F5 — no vuelve en blanco."""
    examen_id, pregunta_id, opcion_id = await _crear_examen_1pregunta(db)

    r1 = await client.post(
        f"{_BASE}/sessions",
        json={"modo": "examen", "examen_contenido_id": examen_id},
    )
    sid = r1.json()["id"]

    await client.post(
        f"{_BASE}/sessions/{sid}/respuestas",
        json={"respuestas": [{"pregunta_id": pregunta_id, "opcion_elegida_id": opcion_id}]},
    )

    resp = await client.get(f"{_BASE}/sessions/{sid}/respuestas")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["session_id"] == sid
    assert body["respuestas"] == [
        {"pregunta_id": pregunta_id, "opcion_elegida_id": opcion_id}
    ]


async def test_obtener_respuestas_de_otro_alumno_404(client: AsyncClient, db: AsyncSession) -> None:
    """IDOR: un alumno no puede leer las respuestas de la sesion de otro."""
    examen_id, pregunta_id, opcion_id = await _crear_examen_1pregunta(db)

    r1 = await client.post(
        f"{_BASE}/sessions",
        json={"modo": "examen", "examen_contenido_id": examen_id},
    )
    sid = r1.json()["id"]
    await client.post(
        f"{_BASE}/sessions/{sid}/respuestas",
        json={"respuestas": [{"pregunta_id": pregunta_id, "opcion_elegida_id": opcion_id}]},
    )

    resp = await client.get(
        f"{_BASE}/sessions/{sid}/respuestas",
        headers=auth_headers(["estudiante"], username="atacante", email="atk@uni.edu"),
    )
    assert resp.status_code == 404, resp.text


async def test_obtener_respuestas_sesion_inexistente_404(client: AsyncClient) -> None:
    resp = await client.get(f"{_BASE}/sessions/00000000-0000-0000-0000-000000000000/respuestas")
    assert resp.status_code == 404
