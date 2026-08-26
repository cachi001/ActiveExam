"""C-69 seguridad — propiedad de sesión (IDOR) + bloqueo de regrade post-finalización.

Fixes derivados de la auditoría de seguridad del circuito de rendición:

- H1 (IDOR): ``POST /sessions/{id}/respuestas`` y ``PATCH /sessions/{id}/finalizar``
  son endpoints DEL ALUMNO. Verifican que la sesión sea del alumno autenticado
  (identidad persistida al crear la sesión). Un alumno con el ``session_id`` de
  otro recibe 404 (no 403: no se revela la existencia de sesiones ajenas).
- H2 (regrade): no se pueden enviar respuestas a una sesión ya finalizada (409),
  y re-finalizar NO recalcula la nota (idempotente) — así no se puede subir la
  nota re-entregando un intento ya cerrado.
- H4: ``SubmitRespuestasIn`` no acepta identidad del cliente (``extra='forbid'``).

DB real (DATABASE_URL). Sin mocks de DB (regla dura de código). Router montado
con ``create_proctoring_router`` y JWT HS256 de test (mismo mecanismo que prod).

Correr:
    DATABASE_URL=postgresql+asyncpg://... pytest tests/proctoring/test_c69_sesion_propiedad.py -v
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text, update
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

# Dos alumnos DISTINTOS (username = preferred_username del JWT).
_OWNER = auth_headers(["estudiante"], username="alumno-owner", email="owner@uni.edu")
_ATACANTE = auth_headers(["estudiante"], username="alumno-atacante", email="atk@uni.edu")

# Orden de DROP (CASCADE cubre dependencias) y de CREATE (respeta FKs).
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
def reinferencia(activeexam_reinferencia):
    """Delega en la instancia de SESION del conftest — no crea una propia.

    Una instancia por MODULO se queda sin referencias cuando el modulo termina;
    ahi el GC dispara el `__del__` del FaceDetector de MediaPipe, que hace
    `executor.submit(...).result()` contra un dispatcher ya finalizado y **se
    cuelga para siempre**. No falla: cuelga la suite entera, y el stack apunta a
    cualquier linea que estuviera ejecutandose cuando corrio el GC (en la corrida
    del 25/8/2026 apunto a un `include_router`, que no tiene nada que ver).

    La del conftest es `scope="session"`: vive toda la corrida y nunca se
    recolecta en el medio. Es el mismo motivo que ya documenta su docstring.
    """
    return activeexam_reinferencia


@pytest.fixture(scope="module")
def app(engine, reinferencia):
    from fastapi import FastAPI

    from app.infrastructure.persistence.session_activeexam import create_activeexam_session_factory
    from app.presentation.api.v1.proctoring.router import create_proctoring_router

    factory = create_activeexam_session_factory(engine)
    router = create_proctoring_router(
        session_factory=factory,
        reinferencia=reinferencia,
        writeback_svc=None,  # Moodle no configurado: la nota se persiste 'pendiente'
    )
    a = FastAPI()
    a.state.jwt_validator = _build_test_jwt_validator()
    a.include_router(router, prefix="/api/v1/proctoring")
    return a


@pytest_asyncio.fixture(autouse=True)
async def _limpiar(engine):
    """Trunca todas las tablas antes de cada test (aislamiento)."""
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
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _crear_examen_1pregunta(db: AsyncSession) -> tuple[str, str, str, str]:
    """Examen con 1 pregunta seleccionada y 2 opciones (una correcta).

    Devuelve (examen_id, pregunta_id, opcion_correcta_id, opcion_incorrecta_id).
    """
    examen = ExamenContenidoModel(titulo="Parcial seguridad", nota_maxima=10)
    db.add(examen)
    await db.flush()
    pregunta = PreguntaExamenModel(
        examen_id=examen.id, enunciado="2+2?", tipo="multichoice", orden=0, seleccionada=True
    )
    db.add(pregunta)
    await db.flush()
    o_ok = OpcionRespuestaModel(pregunta_id=pregunta.id, texto="4", es_correcta=True, orden=0)
    o_bad = OpcionRespuestaModel(pregunta_id=pregunta.id, texto="3", es_correcta=False, orden=1)
    db.add_all([o_ok, o_bad])
    await db.commit()
    return examen.id, pregunta.id, o_ok.id, o_bad.id


async def _crear_sesion(client: AsyncClient, headers: dict, examen_id: str | None = None) -> str:
    body: dict = {"modo": "examen"}
    if examen_id:
        body["examen_contenido_id"] = examen_id
    resp = await client.post(f"{_BASE}/sessions", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _estado(db: AsyncSession, session_id: str) -> MoodleWritebackEstadoModel | None:
    await db.commit()  # cerrar txn abierta para ver lo committeado por el request
    return (
        await db.execute(
            select(MoodleWritebackEstadoModel).where(
                MoodleWritebackEstadoModel.session_id == session_id
            )
        )
    ).scalar_one_or_none()


async def _respuestas(db: AsyncSession, session_id: str) -> list[RespuestaAlumnoModel]:
    await db.commit()
    return list(
        (
            await db.execute(
                select(RespuestaAlumnoModel).where(
                    RespuestaAlumnoModel.session_id == session_id
                )
            )
        )
        .scalars()
        .all()
    )


# ---------------------------------------------------------------------------
# H1 — IDOR: un alumno no puede operar la sesión de otro
# ---------------------------------------------------------------------------


async def test_submit_respuestas_de_otro_alumno_404(client: AsyncClient, db: AsyncSession) -> None:
    """El atacante intenta enviar respuestas a la sesión del owner → 404, sin escribir."""
    examen_id, pid, o_ok, _o_bad = await _crear_examen_1pregunta(db)
    sid = await _crear_sesion(client, _OWNER, examen_id)

    resp = await client.post(
        f"{_BASE}/sessions/{sid}/respuestas",
        json={"respuestas": [{"pregunta_id": pid, "opcion_elegida_id": o_ok}]},
        headers=_ATACANTE,
    )
    assert resp.status_code == 404, resp.text
    # No se persistió ninguna respuesta en la sesión del owner.
    assert await _respuestas(db, sid) == []


async def test_finalizar_sesion_de_otro_alumno_404(client: AsyncClient, db: AsyncSession) -> None:
    """El atacante intenta finalizar la sesión del owner → 404, sin finalizarla."""
    sid = await _crear_sesion(client, _OWNER)

    resp = await client.patch(f"{_BASE}/sessions/{sid}/finalizar", headers=_ATACANTE)
    assert resp.status_code == 404, resp.text

    row = (
        await db.execute(
            select(ProctoringSessionModel).where(ProctoringSessionModel.id == sid)
        )
    ).scalar_one()
    assert row.finalizada_en is None, "la sesión del owner no debe quedar finalizada"


# ---------------------------------------------------------------------------
# Happy path del dueño (no romper el flujo legítimo)
# ---------------------------------------------------------------------------


async def test_owner_envia_respuestas_y_finaliza_ok(client: AsyncClient, db: AsyncSession) -> None:
    """El dueño envía respuesta correcta y finaliza → nota 10 persistida 'pendiente'."""
    examen_id, pid, o_ok, _o_bad = await _crear_examen_1pregunta(db)
    sid = await _crear_sesion(client, _OWNER, examen_id)

    resp = await client.post(
        f"{_BASE}/sessions/{sid}/respuestas",
        json={"respuestas": [{"pregunta_id": pid, "opcion_elegida_id": o_ok}]},
        headers=_OWNER,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["respuestas_guardadas"] == 1

    fin = await client.patch(f"{_BASE}/sessions/{sid}/finalizar", headers=_OWNER)
    assert fin.status_code == 200, fin.text
    assert fin.json()["finalizada_en"] is not None

    estado = await _estado(db, sid)
    assert estado is not None
    assert float(estado.nota) == pytest.approx(10.0)
    # La nota se atribuye al DUEÑO de la sesión, no al finalizador.
    assert estado.alumno_idnumber == "alumno-owner"


# ---------------------------------------------------------------------------
# H2 — regrade: no modificar tras finalizar, no recalcular al re-finalizar
# ---------------------------------------------------------------------------


async def test_submit_tras_finalizar_409(client: AsyncClient, db: AsyncSession) -> None:
    """Enviar respuestas a una sesión ya finalizada → 409 (intento ya entregado)."""
    examen_id, pid, o_ok, o_bad = await _crear_examen_1pregunta(db)
    sid = await _crear_sesion(client, _OWNER, examen_id)

    await client.post(
        f"{_BASE}/sessions/{sid}/respuestas",
        json={"respuestas": [{"pregunta_id": pid, "opcion_elegida_id": o_bad}]},
        headers=_OWNER,
    )
    fin = await client.patch(f"{_BASE}/sessions/{sid}/finalizar", headers=_OWNER)
    assert fin.status_code == 200, fin.text

    # Reintento de envío POST-finalización → bloqueado.
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/respuestas",
        json={"respuestas": [{"pregunta_id": pid, "opcion_elegida_id": o_ok}]},
        headers=_OWNER,
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"] == "sesion_finalizada"


async def test_refinalizar_no_recalcula_la_nota(client: AsyncClient, db: AsyncSession) -> None:
    """Re-finalizar una sesión ya finalizada NO recalcula la nota (cierra el regrade)."""
    examen_id, pid, o_ok, o_bad = await _crear_examen_1pregunta(db)
    sid = await _crear_sesion(client, _OWNER, examen_id)

    # Respuesta INCORRECTA → nota 0 al finalizar.
    await client.post(
        f"{_BASE}/sessions/{sid}/respuestas",
        json={"respuestas": [{"pregunta_id": pid, "opcion_elegida_id": o_bad}]},
        headers=_OWNER,
    )
    fin1 = await client.patch(f"{_BASE}/sessions/{sid}/finalizar", headers=_OWNER)
    assert fin1.status_code == 200, fin1.text
    finalizada_en_1 = fin1.json()["finalizada_en"]

    estado1 = await _estado(db, sid)
    assert estado1 is not None
    assert float(estado1.nota) == pytest.approx(0.0)

    # Simular manipulación directa de la respuesta a la correcta (saltando el 409
    # del submit) y re-finalizar: la nota NO debe recalcularse a 10.
    await db.execute(
        update(RespuestaAlumnoModel)
        .where(RespuestaAlumnoModel.session_id == sid)
        .values(opcion_elegida_id=o_ok)
    )
    await db.commit()

    fin2 = await client.patch(f"{_BASE}/sessions/{sid}/finalizar", headers=_OWNER)
    assert fin2.status_code == 200, fin2.text
    # Idempotente: mismo finalizada_en.
    assert fin2.json()["finalizada_en"] == finalizada_en_1

    estado2 = await _estado(db, sid)
    assert estado2 is not None
    assert float(estado2.nota) == pytest.approx(0.0), "no debe recalcularse tras finalizar"


# ---------------------------------------------------------------------------
# H4 — el cliente no puede enviar identidad
# ---------------------------------------------------------------------------


async def test_submit_rechaza_identidad_del_cliente(client: AsyncClient, db: AsyncSession) -> None:
    """SubmitRespuestasIn (extra='forbid') rechaza alumno_idnumber/email del cliente → 422."""
    examen_id, pid, o_ok, _o_bad = await _crear_examen_1pregunta(db)
    sid = await _crear_sesion(client, _OWNER, examen_id)

    resp = await client.post(
        f"{_BASE}/sessions/{sid}/respuestas",
        json={
            "respuestas": [{"pregunta_id": pid, "opcion_elegida_id": o_ok}],
            "alumno_idnumber": "spoof-999",
            "alumno_email": "spoof@evil.com",
        },
        headers=_OWNER,
    )
    assert resp.status_code == 422, resp.text
