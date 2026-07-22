"""Auditoría de las mutaciones de examen + sync a Moodle (C-73 / cierre C-20).

Cierra el gap detectado en la prueba E2E: fijar destino Moodle, actualizar config,
fijar selección de preguntas y sincronizar a Moodle NO dejaban rastro en la cadena
de custodia. Acá se fija el contrato: cada uno escribe una fila en ``audit_log``.

DB real (DATABASE_URL) — sin mocks de DB. Fixture aislado que crea las tablas de
exam_content + moodle_writeback + audit_log (con pgcrypto + trigger de cadena).
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.audit_log import AuditLogModel
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
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_AUDIT_DDL = [
    "CREATE EXTENSION IF NOT EXISTS pgcrypto",
    # audit_log SIN la FK a evidencia (aislado), igual que test_c20_audit.
    """
    CREATE TABLE audit_log (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        actor varchar(255) NOT NULL,
        timestamp timestamptz NOT NULL DEFAULT now(),
        ip inet,
        user_agent text,
        accion varchar(255) NOT NULL,
        evidencia_id uuid,
        proposito text,
        hash_prev varchar(64) NOT NULL DEFAULT '',
        hash_self varchar(64)
    )
    """,
    """
    CREATE OR REPLACE FUNCTION audit_log_encadenar() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE v_prev text; v_genesis constant text := repeat('0', 64);
    BEGIN
        SELECT hash_self INTO v_prev FROM audit_log ORDER BY timestamp DESC, id DESC LIMIT 1;
        IF v_prev IS NULL THEN v_prev := v_genesis; END IF;
        NEW.hash_prev := v_prev;
        NEW.hash_self := encode(digest(concat_ws('|',
            NEW.actor,
            to_char(NEW.timestamp AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
            host(NEW.ip), coalesce(NEW.user_agent, ''), NEW.accion,
            coalesce(NEW.evidencia_id::text, ''), coalesce(NEW.proposito, ''), NEW.hash_prev
        ), 'sha256'), 'hex');
        RETURN NEW;
    END; $$
    """,
    "DROP TRIGGER IF EXISTS trg_audit_log_encadenar ON audit_log",
    "CREATE TRIGGER trg_audit_log_encadenar BEFORE INSERT ON audit_log "
    "FOR EACH ROW EXECUTE FUNCTION audit_log_encadenar()",
]

_TABLES = [
    ProctoringSessionModel.__table__,
    ExamenContenidoModel.__table__,
    PreguntaExamenModel.__table__,
    OpcionRespuestaModel.__table__,
    RespuestaAlumnoModel.__table__,
    MoodleWritebackEstadoModel.__table__,
    MoodleWritebackAuditModel.__table__,
]
_DROP = [
    "moodle_writeback_audit", "moodle_writeback_estado", "respuesta_alumno",
    "opcion_respuesta", "pregunta_examen", "examen_contenido",
    "proctoring_event", "proctoring_biometria", "proctoring_session", "audit_log",
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
        for t in _DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
        await conn.run_sync(Base.metadata.create_all, tables=_TABLES)
        for stmt in _AUDIT_DDL:
            await conn.execute(text(stmt))
    yield eng
    async with eng.begin() as conn:
        for t in _DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def factory(engine):
    f = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with f() as s:
        await s.execute(text("TRUNCATE audit_log"))
        await s.commit()
    return f


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
        headers=auth_headers(["admin_examenes"]),
    )


async def _crear_examen(factory) -> str:
    async with factory() as s:
        examen = ExamenContenidoModel(titulo=f"Parcial {uuid.uuid4().hex[:6]}")
        s.add(examen)
        await s.flush()
        eid = examen.id
        await s.commit()
    return eid


async def _acciones_audit(factory) -> list[str]:
    async with factory() as s:
        rows = (await s.execute(select(AuditLogModel.accion))).scalars().all()
    return list(rows)


@pytest.mark.asyncio
async def test_fijar_moodle_target_audita(app, factory):
    eid = await _crear_examen(factory)
    async with _admin_client(app) as c:
        resp = await c.post(
            f"/api/v1/exam-content/{eid}/moodle-target",
            json={"moodle_courseid": 2, "moodle_cmid": 4},
        )
    assert resp.status_code == 200, resp.text
    assert "examen.moodle_target" in await _acciones_audit(factory)


@pytest.mark.asyncio
async def test_sincronizar_moodle_sin_token_audita_el_intento(app, factory):
    eid = await _crear_examen(factory)
    async with _admin_client(app) as c:
        resp = await c.post(f"/api/v1/exam-content/{eid}/sincronizar-moodle")
    assert resp.status_code == 200, resp.text
    assert resp.json()["sin_token"] == 0  # sin notas pendientes, pero igual audita
    assert "moodle.sync" in await _acciones_audit(factory)
