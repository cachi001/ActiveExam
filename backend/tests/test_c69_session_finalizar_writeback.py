"""Desacople del envío al finalizar (C-69, decisión de producto admin-sync).

NUEVO contrato: al finalizar la sesión la nota se CALCULA y PERSISTE como
'pendiente', pero NO se auto-envía a Moodle. El envío es manual por el admin
(endpoint POST /{examen_id}/sincronizar-moodle). Estos tests verifican que:

- La finalización persiste el estado 'pendiente' con la nota.
- NUNCA se contacta a Moodle al finalizar (cero requests HTTP).
- Funciona con writeback habilitado (iniciar_writeback) y deshabilitado
  (persistir_nota_pendiente standalone, sin cliente Moodle).
- La finalización nunca se bloquea ni relanza si la persistencia falla.

DB real (DATABASE_URL). HTTP de Moodle con respx (para ASEGURAR cero llamadas).
"""

from __future__ import annotations

import inspect
import os

import pytest
import pytest_asyncio
import respx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.moodle.writeback_service import (
    MoodleWritebackService,
    WritebackEstado,
    persistir_nota_pendiente,
)
from app.application.proctoring.finalizar_con_writeback import (
    finalizar_sesion_con_writeback,
)
from app.infrastructure.moodle.client import MoodleClientConfig, MoodleRestClient
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
    ProctoringSessionModel,
)

BASE = "https://moodle.test"
_TABLES_TO_DROP = [
    "moodle_writeback_audit",
    "moodle_writeback_estado",
    "respuesta_alumno",
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "proctoring_event",
    "proctoring_biometria",
    "proctoring_session",
]
_TABLES_TO_CREATE = [
    ProctoringSessionModel.__table__,
    ExamenContenidoModel.__table__,
    PreguntaExamenModel.__table__,
    OpcionRespuestaModel.__table__,
    RespuestaAlumnoModel.__table__,
    MoodleWritebackEstadoModel.__table__,
    MoodleWritebackAuditModel.__table__,
]


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada — tests de integración omitidos")
    return url


@pytest_asyncio.fixture(scope="module")
async def engine(db_url):
    eng = create_async_engine(db_url, pool_pre_ping=True, future=True, poolclass=NullPool)
    async with eng.begin() as conn:
        for t in _TABLES_TO_DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
        await conn.run_sync(Base.metadata.create_all, tables=_TABLES_TO_CREATE)
    yield eng
    async with eng.begin() as conn:
        for t in _TABLES_TO_DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncSession:
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
        await s.rollback()


@pytest.fixture
def writeback_svc():
    config = MoodleClientConfig(
        base_url=BASE,
        ws_token="token_secreto",  # noqa: S106
        courseid=10,
        cmid=5,
    )
    return MoodleWritebackService(moodle_client=MoodleRestClient(config=config))


async def _crear_sesion(db: AsyncSession) -> str:
    sesion = ProctoringSessionModel(modo="examen", etiqueta="test")
    db.add(sesion)
    await db.flush()
    return sesion.id


async def _crear_examen(
    db: AsyncSession, *, courseid: int | None = None, cmid: int | None = None
) -> str:
    examen = ExamenContenidoModel(
        titulo="Examen D12", moodle_courseid=courseid, moodle_cmid=cmid
    )
    db.add(examen)
    await db.flush()
    return examen.id


async def _crear_sesion_de_examen(db: AsyncSession, examen_id: str) -> str:
    sesion = ProctoringSessionModel(
        modo="examen", etiqueta="test", examen_contenido_id=examen_id
    )
    db.add(sesion)
    await db.flush()
    return sesion.id


async def _estado(db: AsyncSession, session_id: str) -> MoodleWritebackEstadoModel | None:
    result = await db.execute(
        select(MoodleWritebackEstadoModel).where(
            MoodleWritebackEstadoModel.session_id == session_id
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Desacople: finalizar persiste 'pendiente', NO envía a Moodle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_finalizar_con_writeback_persiste_pendiente_sin_enviar(session, writeback_svc):
    """Con writeback habilitado, finalizar persiste 'pendiente' y NO contacta Moodle."""
    ruta = respx.post(f"{BASE}/webservice/rest/server.php")

    session_id = await _crear_sesion(session)

    sesion = await finalizar_sesion_con_writeback(
        db=session,
        session_id=session_id,
        writeback_svc=writeback_svc,
        nota=7.5,
        alumno_idnumber="legajo1",
        alumno_email="a@b.com",
    )

    assert sesion is not None
    assert sesion.finalizada_en is not None
    # Cero llamadas a Moodle: el envío es manual por el admin
    assert ruta.call_count == 0

    estado = await _estado(session, session_id)
    assert estado is not None
    assert estado.estado == WritebackEstado.PENDIENTE
    assert float(estado.nota) == pytest.approx(7.5)
    assert estado.alumno_idnumber == "legajo1"


@pytest.mark.asyncio
@respx.mock
async def test_finalizar_sin_writeback_persiste_pendiente(session):
    """Sin Moodle configurado (writeback_svc=None), la nota igual se persiste 'pendiente'."""
    ruta = respx.post(f"{BASE}/webservice/rest/server.php")

    session_id = await _crear_sesion(session)

    sesion = await finalizar_sesion_con_writeback(
        db=session,
        session_id=session_id,
        writeback_svc=None,
        nota=6.0,
        alumno_idnumber="legajo2",
        alumno_email="b@b.com",
    )

    assert sesion is not None
    assert ruta.call_count == 0

    estado = await _estado(session, session_id)
    assert estado is not None
    assert estado.estado == WritebackEstado.PENDIENTE
    assert float(estado.nota) == pytest.approx(6.0)
    # Sin cliente Moodle: courseid/cmid quedan NULL
    assert estado.moodle_courseid is None
    assert estado.moodle_cmid is None


@pytest.mark.asyncio
@respx.mock
async def test_finalizar_resuelve_target_por_examen(session, writeback_svc):
    """D12: al finalizar, el estado guarda el destino del examen vinculado (no el global)."""
    respx.post(f"{BASE}/webservice/rest/server.php")

    examen_id = await _crear_examen(session, courseid=8080, cmid=42)
    session_id = await _crear_sesion_de_examen(session, examen_id)

    await finalizar_sesion_con_writeback(
        db=session,
        session_id=session_id,
        writeback_svc=writeback_svc,
        nota=7.0,
        alumno_idnumber="legE",
        alumno_email="e@e.com",
    )

    estado = await _estado(session, session_id)
    assert estado is not None
    assert estado.moodle_courseid == 8080  # del examen, no el global (10)
    assert estado.moodle_cmid == 42


@pytest.mark.asyncio
@respx.mock
async def test_finalizar_examen_sin_target_cae_a_global(session, writeback_svc):
    """D12: si el examen no tiene destino propio (NULL), el estado guarda el global."""
    respx.post(f"{BASE}/webservice/rest/server.php")

    examen_id = await _crear_examen(session)  # sin courseid/cmid
    session_id = await _crear_sesion_de_examen(session, examen_id)

    await finalizar_sesion_con_writeback(
        db=session,
        session_id=session_id,
        writeback_svc=writeback_svc,
        nota=7.0,
        alumno_idnumber="legF",
        alumno_email="f@f.com",
    )

    estado = await _estado(session, session_id)
    assert estado is not None
    assert estado.moodle_courseid == 10  # global de config
    assert estado.moodle_cmid == 5


@pytest.mark.asyncio
async def test_finalizar_sesion_inexistente_devuelve_none(session, writeback_svc):
    """Finalizar una sesión que no existe devuelve None (404 lo maneja el router)."""
    sesion = await finalizar_sesion_con_writeback(
        db=session,
        session_id="00000000-0000-0000-0000-000000000000",
        writeback_svc=writeback_svc,
        nota=5.0,
    )
    assert sesion is None


@pytest.mark.asyncio
async def test_persistir_nota_pendiente_standalone(session):
    """persistir_nota_pendiente crea el estado 'pendiente' sin cliente Moodle."""
    session_id = await _crear_sesion(session)

    estado = await persistir_nota_pendiente(
        db=session,
        session_id=session_id,
        nota=8.25,
        alumno_idnumber="legajo3",
        alumno_email="c@c.com",
    )

    assert estado.estado == WritebackEstado.PENDIENTE
    assert float(estado.nota) == pytest.approx(8.25)


@pytest.mark.asyncio
async def test_persistir_nota_pendiente_idempotente_no_pisa_enviado(session):
    """Si ya está 'enviado', persistir_nota_pendiente NO lo revierte a pendiente."""
    session_id = await _crear_sesion(session)
    fila = MoodleWritebackEstadoModel(
        session_id=session_id,
        alumno_idnumber="legajo4",
        alumno_email="d@d.com",
        nota=9.0,
        estado=WritebackEstado.ENVIADO,
        intento=1,
    )
    session.add(fila)
    await session.flush()

    estado = await persistir_nota_pendiente(
        db=session,
        session_id=session_id,
        nota=3.0,
        alumno_idnumber="legajo4",
        alumno_email="d@d.com",
    )

    assert estado.estado == WritebackEstado.ENVIADO  # no se revierte
    assert float(estado.nota) == pytest.approx(9.0)  # nota enviada preservada


def test_l2_5_nota_no_incluye_proctoring():
    """L2.5: ejecutar_writeback toma la nota académica y NO params de proctoring."""
    sig = inspect.signature(MoodleWritebackService.ejecutar_writeback)
    params = set(sig.parameters.keys())
    assert "nota" in params
    proctoring_params = {"score", "proctoring_score", "flags", "proctoring_flags"}
    assert not (proctoring_params & params)
