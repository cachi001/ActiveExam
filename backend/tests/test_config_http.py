"""Tests HTTP del router de Configuracion del Sistema.

Cubre el contrato (exam-config-access-control + system-configuration):
- GET /api/v1/config/effective: cualquier autenticado (200).
- PATCH /api/v1/config: solo admin_sistema con MFA (403 si no-admin, 403 si sin MFA,
  422 si campo extra / fuera de rango).
- edicion exitosa persiste + bump de version + fila config_update inmutable en audit_log.

DB real para la persistencia/auditoria; RBAC/422 no requieren datos previos. Si
DATABASE_URL no esta seteada, los tests se SALTAN (sin mocks de DB).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio

_SECRET = b"config-http-secret"
_ISSUER = "http://keycloak:8080/realms/proctoring"
_AUD = "proctoring-api"


def _db_url() -> str | None:
    return os.environ.get("DATABASE_URL")


@pytest_asyncio.fixture
async def app_y_factory() -> AsyncIterator[tuple]:
    url = _db_url()
    if not url:
        pytest.skip("DATABASE_URL no seteada; test de integracion (DB real).")

    from fastapi import FastAPI
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.domain.auth.token import TokenPolicy
    from app.infrastructure.auth.jwks_cache import JwksCache
    from app.infrastructure.auth.jwt_validator import JwtValidator
    from app.infrastructure.auth.verifiers import build_hs256_verify
    from app.infrastructure.persistence.models.transactional import (
        ConfiguracionSistemaModel,
    )
    from app.presentation.api.v1.config.router import router as config_router

    engine = create_async_engine(url, pool_pre_ping=True, future=True, poolclass=NullPool)
    cfg_tbl = ConfiguracionSistemaModel.__table__
    async with engine.begin() as conn:
        await conn.run_sync(cfg_tbl.drop, checkfirst=True)
        await conn.run_sync(cfg_tbl.create, checkfirst=True)
        # audit_log ya existe en la DB activeexam (migracion 0012). Es APPEND-ONLY (el
        # trigger rechaza DELETE), asi que NO se limpia: el test cuenta el delta.
    factory = async_sessionmaker(engine, expire_on_commit=False)

    app = FastAPI()
    cache = JwksCache(lambda: {"keys": [{"kid": "test-key"}]}, ttl_seconds=3600)
    policy = TokenPolicy(issuers_aceptados=frozenset({_ISSUER}), audience=_AUD)
    app.state.jwt_validator = JwtValidator(
        jwks_cache=cache, policy=policy, verify_fn=build_hs256_verify(_SECRET)
    )
    app.state.session_factory = factory
    app.include_router(config_router, prefix="/api/v1/config")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, factory
    async with engine.begin() as conn:
        await conn.run_sync(cfg_tbl.drop, checkfirst=True)
    await engine.dispose()


def _token(roles, mfa=True) -> str:
    from app.infrastructure.auth.verifiers import encode_hs256

    claims = {
        "iss": _ISSUER,
        "aud": _AUD,
        "sub": "s",
        "preferred_username": "admin1",
        "email": "admin1@uni.edu",
        "exp": 9999999999,
        "realm_access": {"roles": roles},
    }
    if mfa:
        claims["amr"] = ["otp"]
    return encode_hs256(claims, _SECRET)


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- RBAC -------------------------------------------------------------------


async def test_effective_cualquier_autenticado(app_y_factory) -> None:
    client, _ = app_y_factory
    resp = await client.get("/api/v1/config/effective", headers=_h(_token(["estudiante"], mfa=False)))
    assert resp.status_code == 200
    body = resp.json()
    assert "version" in body
    assert "scoring_weights" in body
    assert "umbral_cola_revision" in body


async def test_effective_sin_token_401(app_y_factory) -> None:
    client, _ = app_y_factory
    resp = await client.get("/api/v1/config/effective")
    assert resp.status_code == 401


async def test_editar_no_admin_403(app_y_factory) -> None:
    client, _ = app_y_factory
    resp = await client.patch(
        "/api/v1/config",
        json={"umbral_cola_revision": 80},
        headers=_h(_token(["tutor"])),
    )
    assert resp.status_code == 403


async def test_editar_admin_sin_mfa_ok(app_y_factory) -> None:
    # C-68 (decisión del dueño): edición restringida a admin_sistema por ROL, sin
    # exigir MFA (el JWT propio del activeexam no emite MFA → exigirlo haría la config
    # ineditable en activeexam/Railway). Admin sin MFA DEBE poder editar.
    client, _ = app_y_factory
    resp = await client.patch(
        "/api/v1/config",
        json={"umbral_cola_revision": 80},
        headers=_h(_token(["admin_sistema"], mfa=False)),
    )
    assert resp.status_code == 200


# --- Validacion -------------------------------------------------------------


async def test_campo_extra_422(app_y_factory) -> None:
    client, _ = app_y_factory
    resp = await client.patch(
        "/api/v1/config",
        json={"campo_raro": 1},
        headers=_h(_token(["admin_sistema"])),
    )
    assert resp.status_code == 422  # extra='forbid'


async def test_umbral_fuera_de_rango_422(app_y_factory) -> None:
    client, _ = app_y_factory
    resp = await client.patch(
        "/api/v1/config",
        json={"umbral_cola_revision": 150},
        headers=_h(_token(["admin_sistema"])),
    )
    assert resp.status_code == 422


# --- Edicion exitosa: persistencia + version + auditoria --------------------


async def test_admin_con_mfa_edita_persiste_y_versiona(app_y_factory) -> None:
    client, _ = app_y_factory
    # Lee la version inicial.
    inicial = (await client.get("/api/v1/config/effective", headers=_h(_token(["admin_sistema"])))).json()
    v0 = inicial["version"]

    resp = await client.patch(
        "/api/v1/config",
        json={"umbral_cola_revision": 85, "face_absent_ms": 4000},
        headers=_h(_token(["admin_sistema"])),
    )
    assert resp.status_code == 200
    cuerpo = resp.json()
    assert cuerpo["umbral_cola_revision"] == 85
    assert cuerpo["face_absent_ms"] == 4000
    assert cuerpo["version"] == v0 + 1

    # Persistio: una lectura nueva refleja el cambio.
    despues = (await client.get("/api/v1/config/effective", headers=_h(_token(["estudiante"], mfa=False)))).json()
    assert despues["umbral_cola_revision"] == 85
    assert despues["version"] == v0 + 1


async def test_edicion_escribe_audit_log(app_y_factory) -> None:
    from sqlalchemy import text

    client, factory = app_y_factory

    async def _contar() -> int:
        async with factory() as s:
            return (
                await s.execute(
                    text("SELECT count(*) FROM audit_log WHERE accion = 'config_update'")
                )
            ).scalar_one()

    antes = await _contar()
    # Valor unico para verificar el snapshot before/after. Tiene que estar DENTRO
    # del rango valido [70, 100]: con 63 el PATCH devolvia 422, no se escribia
    # ninguna fila y el test fallaba por una razon que no tenia nada que ver con
    # lo que dice medir (que la edicion queda auditada).
    respuesta = await client.patch(
        "/api/v1/config",
        json={"umbral_cola_revision": 73},
        headers=_h(_token(["admin_sistema"])),
    )
    # Se afirma el status: sin esto, cualquier rechazo futuro vuelve a aparecer
    # como "no se escribio la auditoria" en vez de como lo que es.
    assert respuesta.status_code == 200, respuesta.text
    despues = await _contar()
    assert despues == antes + 1

    async with factory() as s:
        actor, accion, proposito = (
            await s.execute(
                text(
                    "SELECT actor, accion, proposito FROM audit_log "
                    "WHERE accion = 'config_update' ORDER BY timestamp DESC, id DESC LIMIT 1"
                )
            )
        ).all()[0]
    assert accion == "config_update"
    # El proposito guarda un snapshot before/after demostrable.
    assert "before" in proposito and "after" in proposito
    assert "73" in proposito
