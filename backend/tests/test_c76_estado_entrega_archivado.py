"""C-76 tarea 14 — estado de entrega derivado + archivado + filtros de fecha.

`estado_entrega` (backend/app/application/moodle/resultados_query.py) es una
funcion PURA que deriva el estado de la entrega (no_finalizada/en_revision/
revisada/finalizada) a partir de finalizada_en/en_cola_revision/decision — NUNCA
se persiste (evita duplicar fuente de verdad, ver tasks.md §14).

`archivado` es un flag propio nuevo en `proctoring_session` (migration 0081):
soft-hide administrativo del panel de resultados, no disciplinario.

DB real (DATABASE_URL). Sin mocks de DB (regla dura #4).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.moodle.resultados_query import (
    ESTADO_ENTREGA_EN_REVISION,
    ESTADO_ENTREGA_FINALIZADA,
    ESTADO_ENTREGA_NO_FINALIZADA,
    ESTADO_ENTREGA_REVISADA,
    estado_entrega,
)
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
from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: F401
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

# ===========================================================================
# Bloque A — funcion pura `estado_entrega` (sin DB)
# ===========================================================================


def test_estado_entrega_no_finalizada_cuando_finalizada_en_es_none():
    assert (
        estado_entrega(finalizada_en=None, en_cola_revision=False, decision=None)
        == ESTADO_ENTREGA_NO_FINALIZADA
    )


def test_estado_entrega_no_finalizada_ignora_en_cola_revision():
    """Triangulacion: aunque en_cola_revision viniera True, sin finalizar pesa mas."""
    assert (
        estado_entrega(finalizada_en=None, en_cola_revision=True, decision=None)
        == ESTADO_ENTREGA_NO_FINALIZADA
    )


def test_estado_entrega_en_revision_cuando_flaggeada_y_sin_decision():
    ahora = datetime.now(timezone.utc)
    assert (
        estado_entrega(finalizada_en=ahora, en_cola_revision=True, decision=None)
        == ESTADO_ENTREGA_EN_REVISION
    )


def test_estado_entrega_revisada_cuando_hay_decision_aprobado():
    ahora = datetime.now(timezone.utc)
    assert (
        estado_entrega(finalizada_en=ahora, en_cola_revision=True, decision="aprobado")
        == ESTADO_ENTREGA_REVISADA
    )


def test_estado_entrega_revisada_cuando_hay_decision_anulado():
    """Triangulacion: cualquier decision no nula, no solo 'aprobado', es 'revisada'."""
    ahora = datetime.now(timezone.utc)
    assert (
        estado_entrega(finalizada_en=ahora, en_cola_revision=False, decision="anulado")
        == ESTADO_ENTREGA_REVISADA
    )


def test_estado_entrega_finalizada_caso_base():
    ahora = datetime.now(timezone.utc)
    assert (
        estado_entrega(finalizada_en=ahora, en_cola_revision=False, decision=None)
        == ESTADO_ENTREGA_FINALIZADA
    )


# ===========================================================================
# Bloque B/C — endpoint (DB real)
# ===========================================================================

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
    "usuario",
]
_TABLES_TO_CREATE = [
    UsuarioModel.__table__,
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


@pytest_asyncio.fixture
async def app(factory):
    application = FastAPI()
    application.state.jwt_validator = _build_test_jwt_validator()
    application.include_router(
        create_exam_content_router(session_factory=factory, writeback_svc=None),
        prefix="/api/v1/exam-content",
    )
    return application


def _admin_client(app):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["admin_sistema"]),
    )


async def _crear_docente(factory, legajo: str) -> str:
    async with factory() as s:
        u = UsuarioModel(
            username=legajo, email=f"{legajo.lower()}@uni.edu",
            nombre="Docente", apellido=legajo,
        )
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
    return uid


async def _crear_examen(factory, *, docente_id: str | None = None) -> str:
    sufijo = uuid.uuid4().hex[:6]
    async with factory() as s:
        materia = MateriaModel(codigo=f"MAT-{sufijo}", nombre=f"Materia {sufijo}")
        s.add(materia)
        await s.flush()
        comision = ComisionModel(
            materia_id=materia.id, codigo=f"C-{sufijo}", nombre=f"Comisión {sufijo}",
            codigo_matriculacion=f"K-{sufijo}", docente_id=docente_id,
        )
        s.add(comision)
        await s.flush()
        examen = ExamenContenidoModel(titulo=f"Parcial {sufijo}", comision_id=comision.id)
        s.add(examen)
        await s.flush()
        examen_id = examen.id
        await s.commit()
    return examen_id


async def _crear_sesion(
    factory, examen_id: str, *,
    idnumber: str,
    finalizada: bool = True,
    finalizada_en: datetime | None = None,
    decision: str | None = None,
    archivado: bool = False,
) -> str:
    async with factory() as s:
        sesion = ProctoringSessionModel(
            modo="examen",
            examen_contenido_id=examen_id,
            alumno_idnumber=idnumber,
            alumno_email=f"{idnumber.lower()}@u.edu",
            decision=decision,
            archivado=archivado,
        )
        if finalizada:
            sesion.finalizada_en = finalizada_en or datetime.now(timezone.utc)
        s.add(sesion)
        await s.commit()
        await s.refresh(sesion)
        return sesion.id


@pytest.mark.asyncio
async def test_filtro_estado_entrega_no_finalizada(app, factory):
    examen_id = await _crear_examen(factory)
    sid_pendiente = await _crear_sesion(factory, examen_id, idnumber="NF-1", finalizada=False)
    await _crear_sesion(factory, examen_id, idnumber="NF-2", finalizada=True)

    async with _admin_client(app) as c:
        r = await c.get(f"/api/v1/exam-content/{examen_id}/resultados?estado_entrega=no_finalizada")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["session_id"] == sid_pendiente
    assert body["items"][0]["estado_entrega"] == "no_finalizada"


@pytest.mark.asyncio
async def test_filtro_estado_entrega_revisada(app, factory):
    examen_id = await _crear_examen(factory)
    sid_revisada = await _crear_sesion(
        factory, examen_id, idnumber="RV-1", decision="aprobado",
    )
    await _crear_sesion(factory, examen_id, idnumber="RV-2")  # sin decision -> finalizada

    async with _admin_client(app) as c:
        r = await c.get(f"/api/v1/exam-content/{examen_id}/resultados?estado_entrega=revisada")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["session_id"] == sid_revisada


@pytest.mark.asyncio
async def test_archivado_false_por_defecto_excluye_archivadas(app, factory):
    examen_id = await _crear_examen(factory)
    sid_visible = await _crear_sesion(factory, examen_id, idnumber="AR-1", archivado=False)
    await _crear_sesion(factory, examen_id, idnumber="AR-2", archivado=True)

    async with _admin_client(app) as c:
        r = await c.get(f"/api/v1/exam-content/{examen_id}/resultados")
    assert r.status_code == 200, r.text
    body = r.json()
    ids = [it["session_id"] for it in body["items"]]
    assert sid_visible in ids
    assert len(ids) == 1


@pytest.mark.asyncio
async def test_archivado_true_muestra_solo_archivadas(app, factory):
    """Triangulacion: pedir archivado=true invierte el default."""
    examen_id = await _crear_examen(factory)
    await _crear_sesion(factory, examen_id, idnumber="AR-3", archivado=False)
    sid_archivada = await _crear_sesion(factory, examen_id, idnumber="AR-4", archivado=True)

    async with _admin_client(app) as c:
        r = await c.get(f"/api/v1/exam-content/{examen_id}/resultados?archivado=true")
    assert r.status_code == 200, r.text
    body = r.json()
    ids = [it["session_id"] for it in body["items"]]
    assert ids == [sid_archivada]


@pytest.mark.asyncio
async def test_filtro_fecha_incluye_y_excluye_por_rango(app, factory):
    examen_id = await _crear_examen(factory)
    ahora = datetime.now(timezone.utc)
    sid_dentro = await _crear_sesion(
        factory, examen_id, idnumber="FE-1", finalizada_en=ahora,
    )
    await _crear_sesion(
        factory, examen_id, idnumber="FE-2", finalizada_en=ahora - timedelta(days=30),
    )

    desde = (ahora - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
    hasta = (ahora + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")

    async with _admin_client(app) as c:
        r = await c.get(
            f"/api/v1/exam-content/{examen_id}/resultados"
            f"?fecha_desde={desde}&fecha_hasta={hasta}"
        )
    assert r.status_code == 200, r.text
    body = r.json()
    ids = [it["session_id"] for it in body["items"]]
    assert ids == [sid_dentro]


@pytest.mark.asyncio
async def test_archivar_persiste_y_refleja_en_listado(app, factory):
    examen_id = await _crear_examen(factory)
    sid = await _crear_sesion(factory, examen_id, idnumber="PATCH-1")

    async with _admin_client(app) as c:
        r = await c.patch(
            f"/api/v1/exam-content/{examen_id}/resultados/{sid}/archivar",
            json={"archivado": True},
        )
    assert r.status_code == 200, r.text
    assert r.json()["archivado"] is True

    async with factory() as s:
        row = (
            await s.execute(
                select(ProctoringSessionModel.archivado).where(ProctoringSessionModel.id == sid)
            )
        ).scalar_one()
        assert row is True


@pytest.mark.asyncio
async def test_archivar_desarchivar(app, factory):
    """Triangulacion: el mismo endpoint desarchiva con archivado=false."""
    examen_id = await _crear_examen(factory)
    sid = await _crear_sesion(factory, examen_id, idnumber="PATCH-2", archivado=True)

    async with _admin_client(app) as c:
        r = await c.patch(
            f"/api/v1/exam-content/{examen_id}/resultados/{sid}/archivar",
            json={"archivado": False},
        )
    assert r.status_code == 200, r.text
    assert r.json()["archivado"] is False


@pytest.mark.asyncio
async def test_archivar_403_fuera_de_la_comision_del_tutor(app, factory):
    dueno = await _crear_docente(factory, f"DOC-A-{uuid.uuid4().hex[:4]}")
    ajeno = await _crear_docente(factory, f"DOC-B-{uuid.uuid4().hex[:4]}")
    examen_id = await _crear_examen(factory, docente_id=dueno)
    sid = await _crear_sesion(factory, examen_id, idnumber="SCOPE-1")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
        headers=auth_headers(["tutor"], subject=ajeno),
    ) as c:
        r = await c.patch(
            f"/api/v1/exam-content/{examen_id}/resultados/{sid}/archivar",
            json={"archivado": True},
        )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_archivar_200_para_el_tutor_dueno_de_la_comision(app, factory):
    """Triangulacion: el tutor DUEÑO de la comisión sí puede archivar."""
    dueno = await _crear_docente(factory, f"DOC-C-{uuid.uuid4().hex[:4]}")
    examen_id = await _crear_examen(factory, docente_id=dueno)
    sid = await _crear_sesion(factory, examen_id, idnumber="SCOPE-2")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
        headers=auth_headers(["tutor"], subject=dueno),
    ) as c:
        r = await c.patch(
            f"/api/v1/exam-content/{examen_id}/resultados/{sid}/archivar",
            json={"archivado": True},
        )
    assert r.status_code == 200, r.text
