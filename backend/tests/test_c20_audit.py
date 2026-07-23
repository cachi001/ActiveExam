"""Servicio de auditoría (C-20): registro de actividad + lectura paginada/filtrada.

DB real (DATABASE_URL) — sin mocks de DB (regla dura). El fixture crea la tabla
``audit_log`` + la extensión pgcrypto + el trigger de encadenamiento (replica de
la migración 0012) para probar el append-con-cadena y la lectura extremo a
extremo en una base AISLADA (no el audit_log real, que es append-only).
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.audit.service import (
    AuditFiltros,
    listar_auditoria,
    registrar,
)
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.audit_log import AuditLogModel  # noqa: F401

# DDL compartida (tabla + los 2 triggers de la cadena de hash). Estaba duplicada
# aca y en test_c73_examen_audit_wiring.py; ahora vive en un solo lugar.
from tests._audit_schema import DDL_TRIGGERS as _DDL_STMTS


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
        # audit_log tiene FK a evidencia; para aislar, la creamos sin esa FK.
        await conn.execute(text('DROP TABLE IF EXISTS "audit_log" CASCADE'))
        await conn.execute(
            text(
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
                """
            )
        )
        for stmt in _DDL_STMTS:
            await conn.execute(text(stmt))
    yield eng
    # NO se dropea audit_log al terminar: este modulo la re-crea CON sus dos
    # triggers en el setup, pero los modulos que corren despues la necesitan y no
    # la crean. Dropearla los dejaba sin tabla, y recrearla desde el modelo daria
    # una audit_log SIN la cadena de hash (hash_self lo materializa el trigger),
    # o sea tests de auditoria pasando contra una tabla que no encadena nada.
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncSession:
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await s.execute(text("TRUNCATE audit_log"))
        await s.commit()
        yield s
        await s.rollback()


async def _sembrar(s: AsyncSession) -> None:
    # Commit por entrada: now() es hora de transacción, así cada una queda con un
    # timestamp distinto y el orden "más reciente primero" es determinístico
    # (además de encadenar el hash contra la entrada realmente anterior).
    await registrar(s, actor="admin@x", accion="auth.login", ip="10.0.0.1", proposito="Inicio de sesión")
    await s.commit()
    await registrar(s, actor="admin@x", accion="user.create", ip="10.0.0.1", proposito="Alta de usuario")
    await s.commit()
    await registrar(s, actor="coord@x", accion="stats.export.pdf", ip="10.0.0.2", proposito="Exportó PDF")
    await s.commit()


@pytest.mark.asyncio
async def test_registrar_y_listar_mas_reciente_primero(session):
    await _sembrar(session)
    pag = await listar_auditoria(session)
    assert pag.total == 3
    assert [i.accion for i in pag.items] == ["stats.export.pdf", "user.create", "auth.login"]
    # La cadena de custodia quedó íntegra (el trigger encadenó los hashes).
    assert pag.cadena_valida is True


@pytest.mark.asyncio
async def test_filtro_por_accion(session):
    await _sembrar(session)
    pag = await listar_auditoria(session, AuditFiltros(accion="export"))
    assert pag.total == 1
    assert pag.items[0].accion == "stats.export.pdf"


@pytest.mark.asyncio
async def test_filtro_por_accion_multi_patron_or(session):
    # Una "entidad" del filtro de la UI puede agrupar varios tipos de acción
    # (p. ej. "Evidencia" = acceso + depósito + …). El filtro acepta varios
    # patrones separados por coma y los combina con OR.
    await _sembrar(session)  # auth.login, user.create, stats.export.pdf
    pag = await listar_auditoria(session, AuditFiltros(accion="user.create,stats.export"))
    assert pag.total == 2
    assert {i.accion for i in pag.items} == {"user.create", "stats.export.pdf"}


@pytest.mark.asyncio
async def test_filtro_por_actor(session):
    await _sembrar(session)
    pag = await listar_auditoria(session, AuditFiltros(actor="coord"))
    assert pag.total == 1
    assert pag.items[0].actor == "coord@x"


@pytest.mark.asyncio
async def test_paginacion(session):
    await _sembrar(session)
    pag = await listar_auditoria(session, limit=2, offset=0)
    assert pag.total == 3  # total ignora la paginación
    assert len(pag.items) == 2
    pag2 = await listar_auditoria(session, limit=2, offset=2)
    assert len(pag2.items) == 1


# ---------------------------------------------------------------------------
# Endpoint GET /api/v1/admin/audit-log (RBAC admin_sistema)
# ---------------------------------------------------------------------------

from fastapi import FastAPI  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.infrastructure.auth.verifiers import encode_hs256  # noqa: E402
from app.presentation.api.v1.admin.audit_router import create_audit_router  # noqa: E402
from tests.proctoring.conftest import (  # noqa: E402
    _TEST_JWT_AUDIENCE,
    _TEST_JWT_ISSUER,
    _TEST_JWT_SECRET,
    _build_test_jwt_validator,
)


def _token(roles) -> str:
    claims = {
        "iss": _TEST_JWT_ISSUER,
        "aud": _TEST_JWT_AUDIENCE,
        "sub": "sub-audit",
        "preferred_username": "u-audit",
        "email": "a@u.edu",
        "exp": 9999999999,
        "amr": ["otp"],
        "realm_access": {"roles": list(roles)},
    }
    return encode_hs256(claims, _TEST_JWT_SECRET)


@pytest_asyncio.fixture
async def app_audit(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await s.execute(text("TRUNCATE audit_log"))
        await s.commit()
        await _sembrar(s)
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    app.include_router(create_audit_router(session_factory=factory), prefix="/api/v1/admin")
    return app


@pytest.mark.asyncio
async def test_endpoint_audit_log_admin_200(app_audit):
    async with AsyncClient(
        transport=ASGITransport(app=app_audit),
        base_url="http://test",
        headers={"Authorization": f"Bearer {_token(['admin_sistema'])}"},
    ) as c:
        resp = await c.get("/api/v1/admin/audit-log?limit=2")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["cadena_valida"] is True
    assert body["items"][0]["accion"] == "stats.export.pdf"


@pytest.mark.asyncio
async def test_endpoint_audit_log_estudiante_403(app_audit):
    async with AsyncClient(
        transport=ASGITransport(app=app_audit),
        base_url="http://test",
        headers={"Authorization": f"Bearer {_token(['estudiante'])}"},
    ) as c:
        resp = await c.get("/api/v1/admin/audit-log")
    assert resp.status_code == 403, resp.text
