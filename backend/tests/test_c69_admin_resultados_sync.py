"""Resultados del examen + sincronización manual a Moodle por el admin (C-69 admin-sync).

Endpoints (admin-only, SIN MFA — guard a nivel router, igual que el import):
- GET  /api/v1/exam-content/{examen_id}/resultados      → lista paginada de alumnos
       que rindieron (idnumber/email, nota, estado_moodle, actualizado_en).
       Query: q (alumno), estado, page, page_size.
- POST /api/v1/exam-content/{examen_id}/sincronizar-moodle → dispara el write-back de
       las notas 'pendiente'/'fallido' reusando MoodleWritebackService (idempotente).
       { enviadas, fallidas, sin_token, total }. Sin token → todo 'sin_token', no crashea.

DB real (DATABASE_URL). HTTP de Moodle con respx. NO expone es_correcta.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
import respx
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.moodle.writeback_service import (
    MoodleWritebackService,
    WritebackEstado,
)
from app.infrastructure.moodle.client import MoodleClientConfig, MoodleRestClient
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.models.moodle_writeback import (  # noqa: F401
    MoodleWritebackAuditModel,
    MoodleWritebackEstadoModel,
    RespuestaAlumnoModel,
)
from app.infrastructure.persistence.models.proctoring import (  # noqa: F401
    ProctoringEventModel,
    ProctoringSessionModel,
)
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

BASE = "https://moodle.test"
_TABLES_TO_DROP = [
    "moodle_writeback_audit",
    "moodle_writeback_estado",
    "respuesta_alumno",
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "comision",
    "materia",
    "proctoring_event",
    "proctoring_biometria",
    "proctoring_session",
]
_TABLES_TO_CREATE = [
    MateriaModel.__table__,
    ComisionModel.__table__,
    ExamenContenidoModel.__table__,
    PreguntaExamenModel.__table__,
    OpcionRespuestaModel.__table__,
    ProctoringSessionModel.__table__,
    ProctoringEventModel.__table__,
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
async def factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _moodle_svc() -> MoodleWritebackService:
    config = MoodleClientConfig(
        base_url=BASE, ws_token="token_secreto"  # noqa: S106
    )
    return MoodleWritebackService(moodle_client=MoodleRestClient(config=config))


def _build_app(factory, *, writeback_svc):
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    app.include_router(
        create_exam_content_router(session_factory=factory, writeback_svc=writeback_svc),
        prefix="/api/v1/exam-content",
    )
    return app


@pytest_asyncio.fixture
async def app_con_moodle(factory):
    return _build_app(factory, writeback_svc=_moodle_svc())


@pytest_asyncio.fixture
async def app_sin_moodle(factory):
    return _build_app(factory, writeback_svc=None)


def _admin_client(app):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["admin_examenes"]),
    )


async def _crear_examen(factory, *, courseid: int | None = 10, cmid: int | None = 5) -> str:
    """Examen CON destino en el campus por defecto.

    Desde que se elimino el destino global, un examen sin `moodle_courseid`/`cmid` no
    sincroniza: la nota queda retenida como "sin_destino". Los tests del camino feliz
    necesitan por tanto un examen configurado — que es la situacion real de cualquier
    examen que se vaya a sincronizar. Pasar courseid=None sirve para ejercitar
    justamente el caso sin destino."""
    async with factory() as s:
        examen = ExamenContenidoModel(
            titulo=f"Parcial {uuid.uuid4().hex[:6]}",
            moodle_courseid=courseid,
            moodle_cmid=cmid,
        )
        s.add(examen)
        await s.flush()
        examen_id = examen.id
        await s.commit()
    return examen_id


async def _crear_sesion_con_nota(
    factory,
    examen_id: str,
    *,
    idnumber: str,
    email: str,
    nota: float,
    estado: str = WritebackEstado.PENDIENTE,
    finalizada: bool = True,
    courseid: int | None = 10,
    cmid: int | None = 5,
) -> str:
    """Sesion finalizada con su fila de write-back.

    El destino viaja en la fila de estado (se fija al finalizar el examen y se
    preserva despues). Sin destino la nota no sale: ya no hay global al que caer."""
    from datetime import datetime, timezone

    async with factory() as s:
        sesion = ProctoringSessionModel(modo="examen", examen_contenido_id=examen_id)
        if finalizada:
            sesion.finalizada_en = datetime.now(timezone.utc)
        s.add(sesion)
        await s.flush()
        session_id = sesion.id
        fila = MoodleWritebackEstadoModel(
            session_id=session_id,
            alumno_idnumber=idnumber,
            alumno_email=email,
            nota=nota,
            estado=estado,
            intento=0,
            moodle_courseid=courseid,
            moodle_cmid=cmid,
        )
        s.add(fila)
        await s.commit()
    return session_id


# ===========================================================================
# Task 2: GET /{examen_id}/resultados
# ===========================================================================


@pytest.mark.asyncio
async def test_resultados_lista_alumnos_con_nota_y_estado(app_con_moodle, factory):
    examen_id = await _crear_examen(factory)
    await _crear_sesion_con_nota(
        factory, examen_id, idnumber="leg-A", email="a@u.edu", nota=7.5
    )
    await _crear_sesion_con_nota(
        factory, examen_id, idnumber="leg-B", email="b@u.edu", nota=4.0,
        estado=WritebackEstado.ENVIADO,
    )

    async with _admin_client(app_con_moodle) as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/resultados")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size"}
    assert body["total"] == 2
    by_id = {it["alumno_idnumber"]: it for it in body["items"]}
    assert float(by_id["leg-A"]["nota"]) == pytest.approx(7.5)
    assert by_id["leg-A"]["estado_moodle"] == "pendiente"
    assert by_id["leg-B"]["estado_moodle"] == "enviado"
    # No expone es_correcta ni respuestas
    for it in body["items"]:
        assert "es_correcta" not in it
        assert "alumno_email" in it
        assert "actualizado_en" in it


@pytest.mark.asyncio
async def test_resultados_sin_moodle_estado_sin_token(app_sin_moodle, factory):
    examen_id = await _crear_examen(factory)
    await _crear_sesion_con_nota(
        factory, examen_id, idnumber="leg-C", email="c@u.edu", nota=6.0
    )
    async with _admin_client(app_sin_moodle) as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/resultados")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["items"][0]["estado_moodle"] == "sin_token"


@pytest.mark.asyncio
async def test_resultados_busqueda_y_paginacion(app_con_moodle, factory):
    examen_id = await _crear_examen(factory)
    for i in range(5):
        await _crear_sesion_con_nota(
            factory, examen_id, idnumber=f"BUSCA-{i}", email=f"x{i}@u.edu", nota=float(i)
        )
    await _crear_sesion_con_nota(
        factory, examen_id, idnumber="OTRO-99", email="otro@u.edu", nota=2.0
    )

    async with _admin_client(app_con_moodle) as c:
        # búsqueda por alumno
        r = await c.get(f"/api/v1/exam-content/{examen_id}/resultados?q=BUSCA")
        assert r.status_code == 200, r.text
        assert r.json()["total"] == 5

        # paginación: page_size 2
        r2 = await c.get(
            f"/api/v1/exam-content/{examen_id}/resultados?q=BUSCA&page=1&page_size=2"
        )
        b2 = r2.json()
        assert b2["total"] == 5
        assert len(b2["items"]) == 2
        assert b2["page_size"] == 2


@pytest.mark.asyncio
async def test_resultados_filtra_por_estado(app_con_moodle, factory):
    examen_id = await _crear_examen(factory)
    await _crear_sesion_con_nota(
        factory, examen_id, idnumber="EST-P", email="p@u.edu", nota=3.0,
        estado=WritebackEstado.PENDIENTE,
    )
    await _crear_sesion_con_nota(
        factory, examen_id, idnumber="EST-E", email="e@u.edu", nota=8.0,
        estado=WritebackEstado.ENVIADO,
    )
    async with _admin_client(app_con_moodle) as c:
        r = await c.get(f"/api/v1/exam-content/{examen_id}/resultados?estado=enviado")
        body = r.json()
    assert all(it["estado_moodle"] == "enviado" for it in body["items"])
    assert any(it["alumno_idnumber"] == "EST-E" for it in body["items"])
    assert not any(it["alumno_idnumber"] == "EST-P" for it in body["items"])


@pytest.mark.asyncio
async def test_resultados_admin_only(app_con_moodle, factory):
    examen_id = await _crear_examen(factory)
    async with AsyncClient(
        transport=ASGITransport(app=app_con_moodle),
        base_url="http://test",
        headers=auth_headers(["estudiante"]),
    ) as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/resultados")
    assert resp.status_code == 403


# ===========================================================================
# Task 3: POST /{examen_id}/sincronizar-moodle
# ===========================================================================


@pytest.mark.asyncio
@respx.mock
async def test_sincronizar_envia_pendientes(app_con_moodle, factory):
    examen_id = await _crear_examen(factory)
    await _crear_sesion_con_nota(
        factory, examen_id, idnumber="SYNC-1", email="s1@u.edu", nota=7.0
    )
    await _crear_sesion_con_nota(
        factory, examen_id, idnumber="SYNC-2", email="s2@u.edu", nota=5.0,
        estado=WritebackEstado.FALLIDO,
    )
    # ya enviada → no se re-manda
    sid_enviada = await _crear_sesion_con_nota(
        factory, examen_id, idnumber="SYNC-3", email="s3@u.edu", nota=9.0,
        estado=WritebackEstado.ENVIADO,
    )

    push_count = [0]

    def side_effect(request, **kwargs):
        content = request.content.decode()
        if "core_user_get_users_by_field" in content or "field=idnumber" in content:
            return Response(200, json=[{"id": 123}])
        # El write-back lee el grademax REAL del item para convertir la escala (un
        # 8/10 no puede irse como 8/100). Sin este item, el cliente no resuelve el
        # destino y la nota queda 'fallido'.
        if "gradereport_user_get_grade_items" in content:
            return Response(
                200,
                json={
                    "usergrades": [
                        {
                            "gradeitems": [
                                {"cmid": 5, "grademax": 10.0},
                                {"cmid": 111, "grademax": 10.0},
                            ]
                        }
                    ]
                },
            )
        if "core_grades_update_grades" in content:
            push_count[0] += 1
        return Response(200, json={"warnings": []})

    respx.post(f"{BASE}/webservice/rest/server.php").mock(side_effect=side_effect)

    async with _admin_client(app_con_moodle) as c:
        resp = await c.post(f"/api/v1/exam-content/{examen_id}/sincronizar-moodle")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2  # pendiente + fallido (la enviada no cuenta)
    assert body["enviadas"] == 2
    assert body["fallidas"] == 0
    assert body["sin_token"] == 0
    assert push_count[0] == 2  # solo las 2 pendientes/fallidas

    # la ya enviada sigue enviada (idempotente)
    async with factory() as s:
        row = (
            await s.execute(
                select(MoodleWritebackEstadoModel).where(
                    MoodleWritebackEstadoModel.session_id == sid_enviada
                )
            )
        ).scalar_one()
        assert row.estado == WritebackEstado.ENVIADO


@pytest.mark.asyncio
@respx.mock
async def test_sincronizar_usa_target_seteado_despues_de_finalizar(app_con_moodle, factory):
    """D12: un admin que fija el target DESPUÉS de finalizar sincroniza al curso correcto."""
    examen_id = await _crear_examen(factory, courseid=None, cmid=None)  # sin destino al crear
    await _crear_sesion_con_nota(
        factory, examen_id, idnumber="LATE-1", email="late@u.edu", nota=7.0
    )

    # El admin fija el destino del examen DESPUÉS de que la nota quedó pendiente.
    async with factory() as s:
        examen = (
            await s.execute(
                select(ExamenContenidoModel).where(
                    ExamenContenidoModel.id == examen_id
                )
            )
        ).scalar_one()
        examen.moodle_courseid = 9999
        examen.moodle_cmid = 111
        await s.commit()

    captured = {}

    def side_effect(request, **kwargs):
        content = request.content.decode()
        if "core_user_get_users_by_field" in content or "field=idnumber" in content:
            return Response(200, json=[{"id": 321}])
        # El write-back lee el grademax REAL del item para convertir la escala (un
        # 8/10 no puede irse como 8/100). Sin este item, el cliente no resuelve el
        # destino y la nota queda 'fallido'.
        if "gradereport_user_get_grade_items" in content:
            return Response(
                200,
                json={
                    "usergrades": [
                        {
                            "gradeitems": [
                                {"cmid": 5, "grademax": 10.0},
                                {"cmid": 111, "grademax": 10.0},
                            ]
                        }
                    ]
                },
            )
        if "core_grades_update_grades" in content:
            captured["grade"] = content
        return Response(200, json={"warnings": []})

    respx.post(f"{BASE}/webservice/rest/server.php").mock(side_effect=side_effect)

    async with _admin_client(app_con_moodle) as c:
        resp = await c.post(f"/api/v1/exam-content/{examen_id}/sincronizar-moodle")
    assert resp.status_code == 200, resp.text
    assert resp.json()["enviadas"] == 1

    assert "grade" in captured
    assert "courseid=9999" in captured["grade"]  # destino fijado tras finalizar
    assert "activityid=111" in captured["grade"]


@pytest.mark.asyncio
async def test_sincronizar_sin_token_no_crashea(app_sin_moodle, factory):
    examen_id = await _crear_examen(factory)
    await _crear_sesion_con_nota(
        factory, examen_id, idnumber="NT-1", email="nt1@u.edu", nota=6.0
    )
    await _crear_sesion_con_nota(
        factory, examen_id, idnumber="NT-2", email="nt2@u.edu", nota=4.0
    )
    async with _admin_client(app_sin_moodle) as c:
        resp = await c.post(f"/api/v1/exam-content/{examen_id}/sincronizar-moodle")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2
    assert body["sin_token"] == 2
    assert body["enviadas"] == 0
    assert body["fallidas"] == 0
    assert "mensaje" in body

    # las notas siguen 'pendiente' (no se tocaron) — comprobación específica del examen
    async with factory() as s:
        estados = (
            await s.execute(
                select(MoodleWritebackEstadoModel.estado)
                .join(ProctoringSessionModel,
                      ProctoringSessionModel.id == MoodleWritebackEstadoModel.session_id)
                .where(ProctoringSessionModel.examen_contenido_id == examen_id)
            )
        ).scalars().all()
        assert all(e == WritebackEstado.PENDIENTE for e in estados)


@pytest.mark.asyncio
async def test_sincronizar_admin_only(app_con_moodle, factory):
    examen_id = await _crear_examen(factory)
    async with AsyncClient(
        transport=ASGITransport(app=app_con_moodle),
        base_url="http://test",
        headers=auth_headers(["estudiante"]),
    ) as c:
        resp = await c.post(f"/api/v1/exam-content/{examen_id}/sincronizar-moodle")
    assert resp.status_code == 403
