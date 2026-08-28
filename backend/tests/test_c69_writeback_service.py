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
    )
    return MoodleRestClient(config=config)


class _ServicioConDocenteResuelto(MoodleWritebackService):
    """Servicio de write-back con la identidad del docente YA resuelta.

    POR QUE EXISTE (C-73): desde que la nota sale con la credencial del DOCENTE, si no
    hay docente resoluble el servicio RETIENE la nota (motivo `sin_credencial_docente`)
    y nunca llega a Moodle. Eso es correcto y deliberado — pero deja a estos tests sin
    poder ejercitar lo que vinieron a verificar, que es la MECANICA del write-back:
    idempotencia, reintento, auditoria y destino por examen.

    Resolver al docente de verdad exigiria sembrar la cadena
    sesion -> examen_contenido -> comision -> usuario, o sea traer las tablas `comision`
    y `usuario` (con sus FKs) a un fixture que hoy solo crea las de proctoring. Seria
    montar media base para probar algo ortogonal.

    El gate de credencial NO queda sin cobertura: lo prueba
    `tests/test_c73_credencial_en_writeback.py`, que es su lugar.

    Se sobreescribe el resolvedor, NUNCA la base de datos (regla dura de codigo #4).
    """

    async def _credencial_para(self, db, session_id):
        # CINCO valores, no cuatro: la firma real devuelve tambien la base_url de
        # la credencial del docente (C-73). El doble se quedo en la firma vieja y
        # el desempaquetado explotaba con "expected 5, got 4" en cada test que lo
        # usa — un error que no dice nada del comportamiento que se prueba.
        return (
            "token_del_docente",  # noqa: S106
            "docente-test-1",
            "Laura Fernández",
            None,
            None,
        )


@pytest.fixture
def writeback_svc(moodle_client):
    return _ServicioConDocenteResuelto(moodle_client=moodle_client)


# cmids que usan los tests de este archivo. `mod_assign_get_assignments` devuelve
# TODAS las tareas del curso y el filtrado por cmid lo hace el cliente, asi que
# alcanza con publicarlas juntas en una sola respuesta.
_CMIDS_DE_PRUEBA = (5, 56, 303)


def _assignment_id_de(cmid: int) -> int:
    """assign.id simulado para un cmid. A proposito NO es igual al cmid.

    Si el mock devolviera el mismo numero, un bug que usara el cmid donde va el
    instance id pasaria los tests sin que nadie se enterara.
    """
    return 900 + cmid


def _respuesta_assignments() -> Response:
    """Respuesta de `mod_assign_get_assignments`: tareas numericas sobre 100.

    Hace falta desde C-73 Fase 1: el camino por defecto (`mod_assign`) resuelve
    cmid -> assign.id ANTES de escribir. Un mock que solo contestaba
    `core_grades_update_grades` dejaba esa resolucion sin respuesta util y el
    write-back fallaba con "no es una tarea del curso".
    """
    return Response(
        200,
        json={
            "courses": [
                {
                    "id": 10,
                    "assignments": [
                        {"cmid": c, "id": _assignment_id_de(c), "grade": 100}
                        for c in _CMIDS_DE_PRUEBA
                    ],
                }
            ]
        },
    )


# Identidades que usan los tests de este archivo, con el userid de Moodle que cada uno
# espera. Desde C-73 Fase 2 el mapeo de identidad se hace entre los MATRICULADOS del
# curso (`core_enrol_get_enrolled_users`) con el token del docente, en vez de
# `core_user_get_users_by_field` con el institucional. Como el matcheo es por idnumber
# exacto, alcanza con publicar todas juntas en una respuesta.
_MATRICULADOS_DE_PRUEBA = (
    (7, "legajo1", "a@b.com"),
    (42, "legajo2", "b@b.com"),
    (99, "legajo3", "c@c.com"),
    (55, "legajo5", "e@e.com"),
    (77, "legZ", "z@z.com"),
)


def _respuesta_matriculados() -> Response:
    """Respuesta de `core_enrol_get_enrolled_users` con los alumnos de los tests."""
    return Response(
        200,
        json=[
            {"id": uid, "idnumber": idn, "email": mail}
            for uid, idn, mail in _MATRICULADOS_DE_PRUEBA
        ],
    )


def _es_push_de_nota(content: str) -> bool:
    """True si el request es la ESCRITURA de la nota, por cualquiera de los caminos.

    `mod_assign_save_grade` (tareas, camino nuevo) o `core_grades_update_grades`
    (cuestionarios, camino viejo). Contar solo uno haria que la idempotencia
    pareciera cumplirse cuando en realidad se estaria escribiendo por el otro.
    """
    return "mod_assign_save_grade" in content or "core_grades_update_grades" in content


async def _crear_sesion(db: AsyncSession) -> str:
    sesion = ProctoringSessionModel(modo="examen", etiqueta="test")
    db.add(sesion)
    await db.flush()
    return sesion.id


async def _crear_sesion_con_destino(
    db: AsyncSession, *, courseid: int = 10, cmid: int = 5
) -> str:
    """Sesion cuyo examen YA tiene destino en el campus.

    Los tests que ejercitan el push necesitan un destino explicito: desde que se
    elimino el `courseid`/`cmid` global (que mandaba las notas sin destino a la
    libreta equivocada), sin destino no se escribe nada. Se siembra el estado con el
    destino porque `persistir_nota_pendiente` preserva el destino de la fila ya
    creada — es el mismo camino que usa la finalizacion real del examen.
    """
    session_id = await _crear_sesion(db)
    db.add(
        MoodleWritebackEstadoModel(
            session_id=session_id,
            alumno_idnumber="pendiente",
            alumno_email="pendiente@test.local",
            nota=0.0,
            estado="pendiente",
            intento=0,
            moodle_courseid=courseid,
            moodle_cmid=cmid,
        )
    )
    await db.flush()
    return session_id


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
    session_id = await _crear_sesion_con_destino(session)
    push_count = [0]

    def side_effect(request, **kwargs):
        content = request.content.decode()
        if "core_enrol_get_enrolled_users" in content:
            return _respuesta_matriculados()
        if "core_user_get_users_by_field" in content or "field=idnumber" in content:
            return Response(200, json=[{"id": 42}])
        if "mod_assign_get_assignments" in content:
            return _respuesta_assignments()
        if _es_push_de_nota(content):
            push_count[0] += 1
            return Response(200, text="null")
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


# ---------------------------------------------------------------------------
# C-73: component por examen (mod_assign / mod_quiz) — devolver nota en cuestionarios
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_writeback_persiste_component_por_examen(session, writeback_svc):
    """C-73: el component ('mod_quiz') se persiste en el estado para el envío manual."""
    session_id = await _crear_sesion(session)
    await writeback_svc.iniciar_writeback(
        db=session,
        session_id=session_id,
        nota=77.0,
        alumno_idnumber="legajo1",
        alumno_email="a@b.com",
        moodle_courseid=10,
        moodle_cmid=5,
        moodle_component="mod_quiz",
    )
    row = await session.execute(
        select(MoodleWritebackEstadoModel).where(
            MoodleWritebackEstadoModel.session_id == session_id
        )
    )
    assert row.scalar_one().moodle_component == "mod_quiz"


@pytest.mark.asyncio
@respx.mock
async def test_writeback_component_none_cae_a_global(session, writeback_svc):
    """C-73: sin component explícito, cae al global del cliente (mod_assign)."""
    session_id = await _crear_sesion(session)
    await writeback_svc.iniciar_writeback(
        db=session,
        session_id=session_id,
        nota=5.0,
        alumno_idnumber="legajo1",
        alumno_email="a@b.com",
    )
    row = await session.execute(
        select(MoodleWritebackEstadoModel).where(
            MoodleWritebackEstadoModel.session_id == session_id
        )
    )
    assert row.scalar_one().moodle_component == "mod_assign"


@pytest.mark.asyncio
@respx.mock
async def test_ejecutar_writeback_usa_component_por_examen(session, writeback_svc):
    """C-73: ejecutar_writeback pasa el component persistido (mod_quiz) al write_grade,
    SIN pisarlo con el global al re-llamar iniciar internamente."""
    session_id = await _crear_sesion(session)
    # 1) al finalizar: se persiste el destino con component mod_quiz
    await writeback_svc.iniciar_writeback(
        db=session,
        session_id=session_id,
        nota=77.0,
        alumno_idnumber="legajo1",
        alumno_email="a@b.com",
        moodle_courseid=10,
        moodle_cmid=5,
        moodle_component="mod_quiz",
    )
    captured = {}

    def side_effect(request, **kwargs):
        content = request.content.decode()
        if "core_enrol_get_enrolled_users" in content:
            return _respuesta_matriculados()
        if "core_user_get_users_by_field" in content or "field=idnumber" in content:
            return Response(200, json=[{"id": 7}])
        if "core_grades_update_grades" in content:
            captured["content"] = content
        return Response(200, json={"warnings": []})

    respx.post(f"{BASE}/webservice/rest/server.php").mock(side_effect=side_effect)

    # 2) el admin dispara el sync (sin component) — no debe pisar el mod_quiz
    await writeback_svc.ejecutar_writeback(
        db=session,
        session_id=session_id,
        nota=77.0,
        alumno_idnumber="legajo1",
        alumno_email="a@b.com",
    )
    assert "component=mod_quiz" in captured["content"]
    assert "component=mod_assign" not in captured["content"]


@pytest.mark.asyncio
@respx.mock
async def test_writeback_fallido_queda_reintenable(session, writeback_svc):
    """D10: fallo de red deja estado 'fallido' reintenable con la misma nota."""
    import httpx

    session_id = await _crear_sesion_con_destino(session)

    call_count = [0]

    def side_effect(request, **kwargs):
        content = request.content.decode()
        if "core_enrol_get_enrolled_users" in content:
            return _respuesta_matriculados()
        if "core_user_get_users_by_field" in content or "field=idnumber" in content:
            return Response(200, json=[{"id": 99}])
        if "mod_assign_get_assignments" in content:
            # La resolucion del assignment no cuenta como intento de push: lo que
            # este test ejercita es que un fallo de RED al escribir deja la nota
            # reintenable, no que se caiga la resolucion.
            return _respuesta_assignments()
        call_count[0] += 1
        if call_count[0] == 1:
            raise httpx.ConnectError("Network down")
        return Response(200, text="null")

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
async def test_iniciar_writeback_sin_target_queda_sin_destino(session, writeback_svc):
    """Sin target del examen, el estado queda SIN destino — no se inventa uno global.

    Antes se copiaba el courseid/cmid global del cliente, con lo cual la nota salia
    hacia la libreta de otra materia. Ahora la nota se persiste igual (el alumno no
    pierde su calificacion) pero sin destino: queda retenida como "sin_destino" y
    visible en la pantalla de resultados hasta que alguien configure el examen."""
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
    assert estado.moodle_courseid is None
    assert estado.moodle_cmid is None
    # La nota SI se guarda: no se pierde por no tener a donde mandarla.
    assert float(estado.nota) == 7.0


@pytest.mark.asyncio
@respx.mock
async def test_ejecutar_writeback_pushea_al_target_por_examen(session, writeback_svc):
    """D12: el push usa el courseid/cmid del estado (destino por examen)."""
    session_id = await _crear_sesion(session)
    captured = {}

    def side_effect(request, **kwargs):
        content = request.content.decode()
        if "core_enrol_get_enrolled_users" in content:
            return _respuesta_matriculados()
        if "core_user_get_users_by_field" in content or "field=idnumber" in content:
            return Response(200, json=[{"id": 77}])
        if "mod_assign_get_assignments" in content:
            captured["resolve"] = content
            return _respuesta_assignments()
        if _es_push_de_nota(content):
            captured["grade"] = content
            return Response(200, text="null")
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

    # El destino por examen se verifica en los DOS pasos del camino de tareas:
    # la resolucion pregunta por el curso del examen, y la escritura va al
    # assign.id de ESE cmid. Antes se miraba `courseid=`/`activityid=` del payload
    # de `core_grades_update_grades`; `mod_assign_save_grade` no los lleva (el
    # assignment ya identifica curso y actividad), asi que se comprueba donde
    # ahora vive el dato.
    assert "resolve" in captured
    assert "courseids%5B0%5D=4040" in captured["resolve"]

    assert "grade" in captured
    assert f"assignmentid={_assignment_id_de(303)}" in captured["grade"]


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
    session_id = await _crear_sesion_con_destino(session)

    def side_effect(request, **kwargs):
        content = request.content.decode()
        if "core_enrol_get_enrolled_users" in content:
            return _respuesta_matriculados()
        if "core_user_get_users_by_field" in content or "field=idnumber" in content:
            return Response(200, json=[{"id": 55}])
        if "mod_assign_get_assignments" in content:
            return _respuesta_assignments()
        if _es_push_de_nota(content):
            return Response(200, text="null")
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
