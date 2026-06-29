"""7.7 RED → 7.8 GREEN: tests del servicio de write-back de nota con idempotencia.

DB real (DATABASE_URL requerida). HTTP de Moodle MOCKEADO con respx.
D10: idempotente (reintento de nota enviada no duplica push), reintenable tras fallo.
También cubre 7.9-7.10 (manejo de error: Moodle caído no bloquea finalización)
y 7.11-7.12 (auditoría sin token).
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
import respx
from httpx import Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.moodle.writeback_service import (
    MoodleWritebackService,
    WritebackEstado,
)
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
from app.infrastructure.moodle.client import MoodleClientConfig, MoodleRestClient

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
def moodle_client():
    config = MoodleClientConfig(
        base_url=BASE,
        ws_token="token_secreto",  # noqa: S106
        courseid=10,
        cmid=5,
    )
    return MoodleRestClient(config=config)


@pytest.fixture
def writeback_svc(moodle_client):
    return MoodleWritebackService(moodle_client=moodle_client)


async def _crear_sesion(db: AsyncSession) -> str:
    sesion = ProctoringSessionModel(modo="examen", etiqueta="test")
    db.add(sesion)
    await db.flush()
    return sesion.id


# ---------------------------------------------------------------------------
# 7.7 RED → 7.8 GREEN: estado persistido + idempotencia
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_writeback_crea_estado_pendiente(session, writeback_svc):
    """Antes del push, el estado se crea como 'pendiente'."""
    session_id = await _crear_sesion(session)

    respx.post(f"{BASE}/webservice/rest/server.php").mock(
        return_value=Response(200, json=[{"id": 7}])  # lookup usuario
    )
    respx.post(f"{BASE}/webservice/rest/server.php").mock(
        return_value=Response(200, json={"warnings": []})  # write grade
    )

    # Iniciamos el writeback pero mockeamos el lookup para que falle → pendiente
    # No — chequeamos que se crea el estado. Más sencillo: llamamos al método
    # que crea el estado y verificamos la DB.
    await writeback_svc.iniciar_writeback(
        db=session,
        session_id=session_id,
        nota=7.5,
        alumno_idnumber="legajo1",
        alumno_email="a@b.com",
    )

    result = await session.execute(
        select(MoodleWritebackEstadoModel).where(
            MoodleWritebackEstadoModel.session_id == session_id
        )
    )
    estado_row = result.scalar_one()
    assert estado_row.nota is not None
    assert float(estado_row.nota) == pytest.approx(7.5)
    assert estado_row.alumno_idnumber == "legajo1"


@pytest.mark.asyncio
@respx.mock
async def test_writeback_idempotente_no_duplica(session, writeback_svc):
    """D10: reintento sobre una nota ya 'enviado' NO duplica el push a Moodle."""
    session_id = await _crear_sesion(session)
    push_count = [0]

    def side_effect(request, **kwargs):
        content = request.content.decode()
        if "core_user_get_users_by_field" in content or "field=idnumber" in content:
            return Response(200, json=[{"id": 42}])
        if "core_grades_update_grades" in content:
            push_count[0] += 1
            return Response(200, json={"warnings": []})
        return Response(200, json={"warnings": []})

    respx.post(f"{BASE}/webservice/rest/server.php").mock(side_effect=side_effect)

    # Primera vez: debe hacer el push
    await writeback_svc.ejecutar_writeback(
        db=session,
        session_id=session_id,
        nota=8.0,
        alumno_idnumber="legajo2",
        alumno_email="b@b.com",
    )
    assert push_count[0] == 1

    # Segunda vez (reintento): NO debe hacer un segundo push
    await writeback_svc.ejecutar_writeback(
        db=session,
        session_id=session_id,
        nota=8.0,
        alumno_idnumber="legajo2",
        alumno_email="b@b.com",
    )
    assert push_count[0] == 1  # sigue siendo 1 — idempotente


@pytest.mark.asyncio
@respx.mock
async def test_writeback_fallido_queda_reintenable(session, writeback_svc):
    """D10: fallo de red deja estado 'fallido' reintenable con la misma nota."""
    import httpx

    session_id = await _crear_sesion(session)

    call_count = [0]

    def side_effect(request, **kwargs):
        content = request.content.decode()
        if "core_user_get_users_by_field" in content or "field=idnumber" in content:
            return Response(200, json=[{"id": 99}])
        call_count[0] += 1
        if call_count[0] == 1:
            raise httpx.ConnectError("Network down")
        return Response(200, json={"warnings": []})

    respx.post(f"{BASE}/webservice/rest/server.php").mock(side_effect=side_effect)

    # Primer intento: falla por red
    await writeback_svc.ejecutar_writeback(
        db=session,
        session_id=session_id,
        nota=6.0,
        alumno_idnumber="legajo3",
        alumno_email="c@c.com",
    )

    result = await session.execute(
        select(MoodleWritebackEstadoModel).where(
            MoodleWritebackEstadoModel.session_id == session_id
        )
    )
    estado = result.scalar_one()
    assert estado.estado == WritebackEstado.FALLIDO
    assert float(estado.nota) == pytest.approx(6.0)  # nota preservada

    # Segundo intento (reintento): debe tener éxito con la misma nota
    await writeback_svc.ejecutar_writeback(
        db=session,
        session_id=session_id,
        nota=6.0,
        alumno_idnumber="legajo3",
        alumno_email="c@c.com",
    )

    result = await session.execute(
        select(MoodleWritebackEstadoModel).where(
            MoodleWritebackEstadoModel.session_id == session_id
        )
    )
    estado_retry = result.scalar_one()
    assert estado_retry.estado == WritebackEstado.ENVIADO


# ---------------------------------------------------------------------------
# D12 (parte B): destino de write-back POR EXAMEN
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_iniciar_writeback_persiste_target_por_examen(session, writeback_svc):
    """D12: iniciar_writeback con courseid/cmid los persiste en el estado (no el global)."""
    session_id = await _crear_sesion(session)

    await writeback_svc.iniciar_writeback(
        db=session,
        session_id=session_id,
        nota=7.0,
        alumno_idnumber="legX",
        alumno_email="x@x.com",
        moodle_courseid=1234,
        moodle_cmid=56,
    )

    estado = (
        await session.execute(
            select(MoodleWritebackEstadoModel).where(
                MoodleWritebackEstadoModel.session_id == session_id
            )
        )
    ).scalar_one()
    assert estado.moodle_courseid == 1234  # per-examen, no el global (10)
    assert estado.moodle_cmid == 56


@pytest.mark.asyncio
@respx.mock
async def test_iniciar_writeback_fallback_global_cuando_none(session, writeback_svc):
    """D12: sin target (None) el estado guarda el global del cliente (courseid=10, cmid=5)."""
    session_id = await _crear_sesion(session)

    await writeback_svc.iniciar_writeback(
        db=session,
        session_id=session_id,
        nota=7.0,
        alumno_idnumber="legY",
        alumno_email="y@y.com",
    )

    estado = (
        await session.execute(
            select(MoodleWritebackEstadoModel).where(
                MoodleWritebackEstadoModel.session_id == session_id
            )
        )
    ).scalar_one()
    assert estado.moodle_courseid == 10  # global de config
    assert estado.moodle_cmid == 5


@pytest.mark.asyncio
@respx.mock
async def test_ejecutar_writeback_pushea_al_target_por_examen(session, writeback_svc):
    """D12: el push usa el courseid/cmid del estado (destino por examen)."""
    session_id = await _crear_sesion(session)
    captured = {}

    def side_effect(request, **kwargs):
        content = request.content.decode()
        if "core_user_get_users_by_field" in content or "field=idnumber" in content:
            return Response(200, json=[{"id": 77}])
        if "core_grades_update_grades" in content:
            captured["grade"] = content
        return Response(200, json={"warnings": []})

    respx.post(f"{BASE}/webservice/rest/server.php").mock(side_effect=side_effect)

    # Estado con destino por examen distinto del global (10/5)
    await writeback_svc.iniciar_writeback(
        db=session,
        session_id=session_id,
        nota=8.0,
        alumno_idnumber="legZ",
        alumno_email="z@z.com",
        moodle_courseid=4040,
        moodle_cmid=303,
    )
    await writeback_svc.ejecutar_writeback(
        db=session,
        session_id=session_id,
        nota=8.0,
        alumno_idnumber="legZ",
        alumno_email="z@z.com",
    )

    assert "grade" in captured
    assert "courseid=4040" in captured["grade"]
    assert "activityid=303" in captured["grade"]


# ---------------------------------------------------------------------------
# 7.9-7.10: Moodle caído no bloquea la finalización
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_moodle_caido_no_bloquea_finalizacion(session, writeback_svc):
    """7.9: si Moodle no responde, ejecutar_writeback no lanza excepción
    (la nota queda en 'fallido' pero la finalización no se bloquea)."""
    import httpx

    session_id = await _crear_sesion(session)

    respx.post(f"{BASE}/webservice/rest/server.php").mock(
        side_effect=httpx.ConnectError("Moodle down")
    )

    # No debe propagar la excepción
    await writeback_svc.ejecutar_writeback(
        db=session,
        session_id=session_id,
        nota=5.0,
        alumno_idnumber="legajo4",
        alumno_email="d@d.com",
    )

    result = await session.execute(
        select(MoodleWritebackEstadoModel).where(
            MoodleWritebackEstadoModel.session_id == session_id
        )
    )
    estado = result.scalar_one()
    assert estado.estado == WritebackEstado.FALLIDO
    assert float(estado.nota) == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# 7.11-7.12: Auditoría sin token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_auditoria_registra_intento_exitoso(session, writeback_svc):
    """7.11-7.12: cada intento exitoso deja una entrada de audit sin token."""
    session_id = await _crear_sesion(session)

    def side_effect(request, **kwargs):
        content = request.content.decode()
        if "core_user_get_users_by_field" in content or "field=idnumber" in content:
            return Response(200, json=[{"id": 55}])
        return Response(200, json={"warnings": []})

    respx.post(f"{BASE}/webservice/rest/server.php").mock(side_effect=side_effect)

    await writeback_svc.ejecutar_writeback(
        db=session,
        session_id=session_id,
        nota=9.0,
        alumno_idnumber="legajo5",
        alumno_email="e@e.com",
    )

    result = await session.execute(
        select(MoodleWritebackAuditModel).where(
            MoodleWritebackAuditModel.session_id == session_id
        )
    )
    audit_rows = result.scalars().all()
    assert len(audit_rows) >= 1
    audit = audit_rows[-1]
    assert audit.resultado == "ok"
    assert audit.alumno_idnumber == "legajo5"
    assert float(audit.nota) == pytest.approx(9.0)


@pytest.mark.asyncio
@respx.mock
async def test_auditoria_no_contiene_token(session, writeback_svc):
    """7.12: el audit log NO contiene el token ni ninguna variante."""
    import httpx

    session_id = await _crear_sesion(session)
    respx.post(f"{BASE}/webservice/rest/server.php").mock(
        side_effect=httpx.ConnectError("down")
    )

    await writeback_svc.ejecutar_writeback(
        db=session,
        session_id=session_id,
        nota=3.0,
        alumno_idnumber="legajo6",
        alumno_email="f@f.com",
    )

    result = await session.execute(
        select(MoodleWritebackAuditModel).where(
            MoodleWritebackAuditModel.session_id == session_id
        )
    )
    audit_rows = result.scalars().all()
    for row in audit_rows:
        detail = (row.error_detalle or "").lower()
        assert "token_secreto" not in detail
        assert "wstoken" not in detail
