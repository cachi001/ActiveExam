"""Tests HTTP de los toggles globales chat_habilitado / pausas_habilitadas (C-69).

Config del SISTEMA: el admin puede activar/desactivar (a) el chat proctor↔alumno
y (b) las pausas del alumno. Dos flags expuestos en la config efectiva y editables
por PATCH /api/v1/config.

Cubre:
- defaults: ambos true en GET /effective (compat con comportamiento previo).
- PATCH a false persiste y se refleja en una lectura nueva de GET.
- PATCH parcial (solo uno) no toca el otro.
- valor no-bool → 422 (extra='forbid' + tipado Pydantic).
- sigue siendo singleton ('global'): edición no crea filas nuevas.

DB real (regla dura, sin mocks). Si DATABASE_URL no esta seteada → SKIP.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio

_SECRET = b"config-chat-pausas-secret"
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


# --- Defaults ---------------------------------------------------------------


async def test_defaults_chat_y_pausas_habilitados(app_y_factory) -> None:
    client, _ = app_y_factory
    body = (
        await client.get(
            "/api/v1/config/effective", headers=_h(_token(["estudiante"], mfa=False))
        )
    ).json()
    assert body["chat_habilitado"] is True
    assert body["pausas_habilitadas"] is True


# --- PATCH a false persiste -------------------------------------------------


async def test_patch_desactiva_ambos_persiste(app_y_factory) -> None:
    client, _ = app_y_factory
    resp = await client.patch(
        "/api/v1/config",
        json={"chat_habilitado": False, "pausas_habilitadas": False},
        headers=_h(_token(["admin_sistema"])),
    )
    assert resp.status_code == 200
    cuerpo = resp.json()
    assert cuerpo["chat_habilitado"] is False
    assert cuerpo["pausas_habilitadas"] is False

    # Lectura nueva (otro rol) refleja el cambio persistido.
    despues = (
        await client.get(
            "/api/v1/config/effective", headers=_h(_token(["estudiante"], mfa=False))
        )
    ).json()
    assert despues["chat_habilitado"] is False
    assert despues["pausas_habilitadas"] is False


async def test_patch_parcial_no_toca_el_otro(app_y_factory) -> None:
    client, _ = app_y_factory
    # Solo desactiva el chat; las pausas siguen en su default (true).
    resp = await client.patch(
        "/api/v1/config",
        json={"chat_habilitado": False},
        headers=_h(_token(["admin_sistema"])),
    )
    assert resp.status_code == 200
    cuerpo = resp.json()
    assert cuerpo["chat_habilitado"] is False
    assert cuerpo["pausas_habilitadas"] is True

    # Reactivar el chat sin tocar pausas.
    resp2 = await client.patch(
        "/api/v1/config",
        json={"chat_habilitado": True},
        headers=_h(_token(["admin_sistema"])),
    )
    assert resp2.status_code == 200
    assert resp2.json()["chat_habilitado"] is True
    assert resp2.json()["pausas_habilitadas"] is True


# --- Validacion -------------------------------------------------------------


async def test_chat_no_bool_422(app_y_factory) -> None:
    client, _ = app_y_factory
    resp = await client.patch(
        "/api/v1/config",
        json={"chat_habilitado": "quiza"},
        headers=_h(_token(["admin_sistema"])),
    )
    assert resp.status_code == 422


async def test_pausas_no_bool_422(app_y_factory) -> None:
    client, _ = app_y_factory
    resp = await client.patch(
        "/api/v1/config",
        json={"pausas_habilitadas": 7},
        headers=_h(_token(["admin_sistema"])),
    )
    assert resp.status_code == 422


# --- Singleton ---------------------------------------------------------------


async def test_sigue_siendo_singleton(app_y_factory) -> None:
    from sqlalchemy import text

    client, factory = app_y_factory
    await client.patch(
        "/api/v1/config",
        json={"chat_habilitado": False},
        headers=_h(_token(["admin_sistema"])),
    )
    await client.patch(
        "/api/v1/config",
        json={"pausas_habilitadas": False},
        headers=_h(_token(["admin_sistema"])),
    )
    async with factory() as s:
        filas = (
            await s.execute(text("SELECT count(*) FROM configuracion_sistema"))
        ).scalar_one()
    assert filas == 1
