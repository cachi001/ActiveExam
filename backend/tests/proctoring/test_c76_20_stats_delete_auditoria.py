"""C-76 tarea 20 — Registro de sesiones: rework de stats/filtros + sesiones de
test eliminables + fix del modulo SESIONES muerto en Auditoria.

Cubre (ver tasks.md §20):
  - DELETE /proctoring/sessions/{id}: 204 + desaparece + queda en audit_log bajo
    SESIONES si modo='test'; 409 (NO se borra) si modo='examen'; 404 si no existe;
    403 si el actor no es admin_sistema.
  - Filtros materia_id/comision_id en GET /sessions/registro (cascada).
  - Agregado en_cola_revision sobre el TOTAL filtrado, no la pagina.
  - PATCH .../resultados/{session_id}/archivar queda auditado bajo SESIONES.
  - modulo_de_accion resuelve el prefijo "sesion." -> ModuloAuditoria.SESIONES
    (unit, sin DB): antes SESIONES nunca se devolvia (filtro muerto).

DB real (DATABASE_URL). Sin mocks (regla dura #4). Fixtures propias
(module-scoped engine, function-scoped truncate), mismo patron que
test_c76_registro_sesiones.py / test_c73_examen_audit_wiring.py.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.audit.acciones import AccionAuditoria, ModuloAuditoria

# --- integracion: DELETE /sessions/{id} + filtros + en_cola_revision --------
# (Los 3 tests unitarios de `modulo_de_accion`, sin DB y sin asyncio, viven en
# test_c76_20_modulo_de_accion.py — separados para no mezclar `pytestmark =
# pytest.mark.asyncio` con funciones sincronas.)

pytestmark = pytest.mark.asyncio

_TABLAS = (
    "proctoring_event",
    "proctoring_biometria",
    "proctoring_session",
    "comision",
    "materia",
    "examen_contenido",
    "usuario",
    "audit_log",
)

_TEST_JWT_ISSUER = "activeexam-auth"
_TEST_JWT_AUDIENCE = "proctoring-api"


def _db_url() -> str | None:
    return os.environ.get("DATABASE_URL")


def _token(roles: list[str], subject: str) -> str:
    from app.infrastructure.auth.verifiers import encode_hs256
    from tests.proctoring.conftest import _TEST_JWT_SECRET

    claims: dict = {
        "iss": _TEST_JWT_ISSUER,
        "aud": _TEST_JWT_AUDIENCE,
        "sub": subject,
        "preferred_username": "+".join(roles),
        "email": f"{subject}@uni.edu",
        "exp": 9999999999,
        "realm_access": {"roles": roles},
        "amr": ["otp"],
    }
    return encode_hs256(claims, _TEST_JWT_SECRET)


def _h(roles: list[str], subject: str) -> dict:
    return {"Authorization": f"Bearer {_token(roles, subject)}"}


@pytest_asyncio.fixture
async def ctx():
    url = _db_url()
    if not url:
        pytest.skip("DATABASE_URL no esta seteada; test de integracion (DB real).")

    from app.infrastructure.persistence.models.exam_content import (
        ComisionModel,
        ExamenContenidoModel,
        MateriaModel,
    )
    from app.infrastructure.persistence.models.proctoring import (
        ProctoringBiometriaModel,
        ProctoringEventModel,
        ProctoringSessionModel,
    )
    from app.infrastructure.persistence.models.transactional import UsuarioModel
    from app.presentation.api.v1.proctoring.router import create_proctoring_router
    from app.infrastructure.reinferencia.mediapipe_adapter import MediaPipeReinferencia
    from tests._audit_schema import DDL_COMPLETA
    from tests.proctoring.conftest import _build_test_jwt_validator

    engine = create_async_engine(url, pool_pre_ping=True, future=True, poolclass=NullPool)
    async with engine.begin() as conn:
        for name in _TABLAS:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
        await conn.run_sync(UsuarioModel.__table__.create, checkfirst=True)
        await conn.run_sync(MateriaModel.__table__.create, checkfirst=True)
        await conn.run_sync(ComisionModel.__table__.create, checkfirst=True)
        await conn.run_sync(ExamenContenidoModel.__table__.create, checkfirst=True)
        await conn.run_sync(ProctoringSessionModel.__table__.create, checkfirst=True)
        await conn.run_sync(ProctoringEventModel.__table__.create, checkfirst=True)
        await conn.run_sync(ProctoringBiometriaModel.__table__.create, checkfirst=True)
        for stmt in DDL_COMPLETA:
            await conn.execute(text(stmt))

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    router = create_proctoring_router(
        session_factory=factory, reinferencia=MediaPipeReinferencia()
    )
    app.include_router(router, prefix="/api/v1/proctoring")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, factory

    async with engine.begin() as conn:
        for name in _TABLAS:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await engine.dispose()


async def _crear_materia_comision_examen(
    factory, *, materia_nombre: str = "Materia Test", comision_nombre: str = "Comision 1"
) -> tuple[str, str, str]:
    """Crea materia + comision + examen. Devuelve (materia_id, comision_id, examen_contenido_id)."""
    from app.infrastructure.persistence.models.exam_content import (
        ComisionModel,
        ExamenContenidoModel,
        MateriaModel,
    )

    async with factory() as session:
        materia = MateriaModel(codigo=f"MAT-{uuid.uuid4().hex[:8]}", nombre=materia_nombre)
        session.add(materia)
        await session.flush()
        comision = ComisionModel(
            materia_id=materia.id,
            codigo="C1",
            nombre=comision_nombre,
            codigo_matriculacion=f"MAT-C1-{uuid.uuid4().hex[:8]}",
        )
        session.add(comision)
        await session.flush()
        examen = ExamenContenidoModel(titulo="Examen Test", comision_id=comision.id)
        session.add(examen)
        await session.commit()
        return materia.id, comision.id, examen.id


async def _crear_sesion(
    factory,
    *,
    modo: str,
    examen_contenido_id: str | None = None,
    alumno_idnumber: str = "alumno-1",
    finalizada: bool = True,
) -> str:
    from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel

    async with factory() as session:
        s = ProctoringSessionModel(
            modo=modo,
            examen_contenido_id=examen_contenido_id,
            alumno_idnumber=alumno_idnumber,
            finalizada_en=datetime.now(timezone.utc) if finalizada else None,
        )
        session.add(s)
        await session.commit()
        await session.refresh(s)
        return s.id


async def _crear_evento(factory, session_id: str, *, severidad: str = "critica") -> None:
    from app.infrastructure.persistence.models.proctoring import ProctoringEventModel

    async with factory() as session:
        session.add(
            ProctoringEventModel(
                session_id=session_id,
                tipo="cara_ausente",
                severidad=severidad,
                ts_cliente=datetime.now(timezone.utc),
                ts_backend=datetime.now(timezone.utc),
            )
        )
        await session.commit()


async def _audit_rows(factory) -> list:
    from app.infrastructure.persistence.models.audit_log import AuditLogModel

    async with factory() as session:
        rows = (
            await session.execute(
                select(AuditLogModel.accion, AuditLogModel.modulo, AuditLogModel.entidad_id)
            )
        ).all()
    return list(rows)


# --- DELETE modo='test' ------------------------------------------------------


async def test_delete_sesion_modo_test_204_desaparece_y_audita(ctx) -> None:
    client, factory = ctx
    sid = await _crear_sesion(factory, modo="test")

    resp = await client.delete(
        f"/api/v1/proctoring/sessions/{sid}", headers=_h(["admin_sistema"], "admin-1")
    )
    assert resp.status_code == 204, resp.text

    # Desaparece del registro.
    resp_reg = await client.get(
        "/api/v1/proctoring/sessions/registro", headers=_h(["admin_sistema"], "admin-1")
    )
    ids = [i["id"] for i in resp_reg.json()["items"]]
    assert sid not in ids

    # Queda auditado bajo SESIONES.
    filas = await _audit_rows(factory)
    matches = [f for f in filas if f.entidad_id == sid]
    assert len(matches) == 1
    assert matches[0].accion == AccionAuditoria.SESION_TEST_ELIMINADA
    assert matches[0].modulo == ModuloAuditoria.SESIONES


# --- DELETE modo='examen' — rechazado, NUNCA se borra -----------------------


async def test_delete_sesion_modo_examen_409_no_se_borra(ctx) -> None:
    client, factory = ctx
    sid = await _crear_sesion(factory, modo="examen")

    resp = await client.delete(
        f"/api/v1/proctoring/sessions/{sid}", headers=_h(["admin_sistema"], "admin-1")
    )
    assert resp.status_code == 409, resp.text

    # Sigue existiendo.
    resp_get = await client.get(
        f"/api/v1/proctoring/sessions/{sid}", headers=_h(["admin_sistema"], "admin-1")
    )
    assert resp_get.status_code == 200
    assert resp_get.json()["id"] == sid


async def test_delete_sesion_no_encontrada_404(ctx) -> None:
    client, _ = ctx
    fake_id = str(uuid.uuid4())
    resp = await client.delete(
        f"/api/v1/proctoring/sessions/{fake_id}", headers=_h(["admin_sistema"], "admin-1")
    )
    assert resp.status_code == 404, resp.text


async def test_delete_sesion_no_admin_403(ctx) -> None:
    client, factory = ctx
    sid = await _crear_sesion(factory, modo="test")
    resp = await client.delete(
        f"/api/v1/proctoring/sessions/{sid}", headers=_h(["coordinador"], "coord-1")
    )
    assert resp.status_code == 403, resp.text
    # No se borro: sigue existiendo. Se comprueba como admin porque el
    # coordinador solo ve SUS materias (c-79) y este coordinador no tiene ninguna
    # asignada: un 404 aca no diria nada sobre si la sesion se borro o no.
    resp_get = await client.get(
        f"/api/v1/proctoring/sessions/{sid}", headers=_h(["admin_sistema"], "admin-1")
    )
    assert resp_get.status_code == 200


# Desde c-79 el COORDINADOR ve solo las sesiones de SUS materias asignadas
# (materia_coordinador); ya no tiene alcance institucional. Los tests de este
# archivo son sobre las reglas de BORRADO y sobre los FILTROS, no sobre el
# acotamiento por rol — que tiene su propia cobertura. Por eso listan y verifican
# como admin_sistema: con un coordinador sin materias asignadas la respuesta
# venia vacia y el test fallaba por una razon ajena a lo que dice medir.
#
# La unica llamada que SIGUE siendo de coordinador es la que comprueba el 403 al
# borrar: ahi el rol es justamente lo que se prueba.

# --- Filtros materia_id / comision_id (cascada) ------------------------------


async def test_filtro_por_materia_id(ctx) -> None:
    client, factory = ctx
    materia_a, _, examen_a = await _crear_materia_comision_examen(factory, materia_nombre="Álgebra")
    materia_b, _, examen_b = await _crear_materia_comision_examen(factory, materia_nombre="Física")
    await _crear_sesion(factory, modo="examen", examen_contenido_id=examen_a)
    await _crear_sesion(factory, modo="examen", examen_contenido_id=examen_b)

    resp = await client.get(
        "/api/v1/proctoring/sessions/registro",
        params={"materia_id": materia_a},
        headers=_h(["admin_sistema"], "admin-1"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["examen_contenido_id"] == examen_a


async def test_filtro_por_comision_id(ctx) -> None:
    client, factory = ctx
    _, comision_a, examen_a = await _crear_materia_comision_examen(factory, comision_nombre="C1")
    _, comision_b, examen_b = await _crear_materia_comision_examen(factory, comision_nombre="C2")
    await _crear_sesion(factory, modo="examen", examen_contenido_id=examen_a)
    await _crear_sesion(factory, modo="examen", examen_contenido_id=examen_b)

    resp = await client.get(
        "/api/v1/proctoring/sessions/registro",
        params={"comision_id": comision_b},
        headers=_h(["admin_sistema"], "admin-1"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["examen_contenido_id"] == examen_b


# --- Agregado en_cola_revision sobre el TOTAL filtrado -----------------------


async def test_en_cola_revision_refleja_total_filtrado_no_la_pagina(ctx) -> None:
    client, factory = ctx
    _, _, examen_id = await _crear_materia_comision_examen(factory)

    # 3 sesiones "en cola" (score alto, 2 eventos criticos c/u) + 2 sin eventos.
    for i in range(3):
        sid = await _crear_sesion(factory, modo="examen", examen_contenido_id=examen_id, alumno_idnumber=f"alto-{i}")
        await _crear_evento(factory, sid, severidad="critica")
        await _crear_evento(factory, sid, severidad="critica")
    for i in range(2):
        await _crear_sesion(factory, modo="examen", examen_contenido_id=examen_id, alumno_idnumber=f"bajo-{i}")

    resp = await client.get(
        "/api/v1/proctoring/sessions/registro",
        params={"page": 1, "page_size": 2},
        headers=_h(["admin_sistema"], "admin-1"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2  # pagina, no el universo
    assert body["en_cola_revision"] == 3
    assert "total_eventos" not in body
    assert "total_discrepancias" not in body


# --- Archivar resultado queda auditado bajo SESIONES -------------------------


async def test_archivar_resultado_queda_auditado_bajo_sesiones(ctx) -> None:
    from app.presentation.api.v1.exam_content.router import create_exam_content_router
    from tests.proctoring.conftest import _build_test_jwt_validator as build_validator

    client, factory = ctx
    _, _, examen_id = await _crear_materia_comision_examen(factory)
    sid = await _crear_sesion(factory, modo="examen", examen_contenido_id=examen_id)

    app2 = FastAPI()
    app2.state.jwt_validator = build_validator()
    app2.include_router(
        create_exam_content_router(session_factory=factory, writeback_svc=None),
        prefix="/api/v1/exam-content",
    )
    transport2 = ASGITransport(app=app2)
    async with AsyncClient(transport=transport2, base_url="http://test") as client2:
        resp = await client2.patch(
            f"/api/v1/exam-content/{examen_id}/resultados/{sid}/archivar",
            json={"archivado": True},
            headers=_h(["admin_sistema"], "admin-1"),
        )
    assert resp.status_code == 200, resp.text

    filas = await _audit_rows(factory)
    matches = [f for f in filas if f.entidad_id == sid]
    assert len(matches) == 1
    assert matches[0].accion == AccionAuditoria.RESULTADO_ARCHIVAR
    assert matches[0].modulo == ModuloAuditoria.SESIONES
