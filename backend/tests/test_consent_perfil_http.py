"""Tests HTTP del consentimiento de perfil (profile-consent-persistence).

- POST /api/v1/consent/profile (otorgar): 422 sin accion afirmativa explicita,
  201 con accion afirmativa; persiste atado al usuario.
- GET  /api/v1/consent/profile: estado vigente del usuario autenticado.
- POST /api/v1/consent/profile/revoke: inserta revocado, preserva historico.

DB real (resuelve usuario_id desde usuario por id_institucional). Sin mocks de DB.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio

_SECRET = b"consent-perfil-secret"
_ISSUER = "http://keycloak:8080/realms/proctoring"
_AUD = "proctoring-api"


def _db_url() -> str | None:
    return os.environ.get("DATABASE_URL")


@pytest_asyncio.fixture
async def ctx() -> AsyncIterator[tuple]:
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
        ConsentimientoPerfilModel,
        UsuarioModel,
    )
    from app.presentation.api.v1.consent_perfil.router import (
        router as consent_perfil_router,
    )

    engine = create_async_engine(url, pool_pre_ping=True, future=True, poolclass=NullPool)
    tbl = ConsentimientoPerfilModel.__table__
    async with engine.begin() as conn:
        await conn.run_sync(tbl.drop, checkfirst=True)
        await conn.run_sync(tbl.create, checkfirst=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    # Usuario de prueba (id_institucional unico).
    id_inst = f"cperf-http-{uuid.uuid4().hex[:8]}"
    async with factory() as s:
        u = UsuarioModel(
            id_institucional=id_inst,
            email=f"{id_inst}@test.local",
            roles=["estudiante"],
            auth_provider="local",
        )
        s.add(u)
        await s.commit()

    app = FastAPI()
    cache = JwksCache(lambda: {"keys": [{"kid": "test-key"}]}, ttl_seconds=3600)
    policy = TokenPolicy(issuers_aceptados=frozenset({_ISSUER}), audience=_AUD)
    app.state.jwt_validator = JwtValidator(
        jwks_cache=cache, policy=policy, verify_fn=build_hs256_verify(_SECRET)
    )
    app.state.session_factory = factory
    app.include_router(consent_perfil_router, prefix="/api/v1/consent/profile")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, id_inst
    async with engine.begin() as conn:
        await conn.run_sync(tbl.drop, checkfirst=True)
    async with factory() as s:
        from sqlalchemy import delete

        await s.execute(delete(UsuarioModel).where(UsuarioModel.id_institucional == id_inst))
        await s.commit()
    await engine.dispose()


def _token(id_inst: str) -> str:
    from app.infrastructure.auth.verifiers import encode_hs256

    return encode_hs256(
        {
            "iss": _ISSUER,
            "aud": _AUD,
            "sub": id_inst,
            "preferred_username": id_inst,
            "email": f"{id_inst}@test.local",
            "exp": 9999999999,
            "realm_access": {"roles": ["estudiante"]},
        },
        _SECRET,
    )


def _h(id_inst: str) -> dict:
    return {"Authorization": f"Bearer {_token(id_inst)}"}


async def test_otorgar_sin_accion_afirmativa_422(ctx) -> None:
    client, id_inst = ctx
    resp = await client.post(
        "/api/v1/consent/profile",
        json={"version_texto": "v1", "affirmative_action": False},
        headers=_h(id_inst),
    )
    assert resp.status_code == 422


async def test_campo_extra_422(ctx) -> None:
    client, id_inst = ctx
    resp = await client.post(
        "/api/v1/consent/profile",
        json={"version_texto": "v1", "affirmative_action": True, "raro": 1},
        headers=_h(id_inst),
    )
    assert resp.status_code == 422


async def test_otorgar_persiste_y_consulta_vigente(ctx) -> None:
    client, id_inst = ctx
    resp = await client.post(
        "/api/v1/consent/profile",
        json={"version_texto": "v1", "affirmative_action": True},
        headers=_h(id_inst),
    )
    assert resp.status_code == 201
    assert resp.json()["estado"] == "otorgado"

    estado = await client.get("/api/v1/consent/profile", headers=_h(id_inst))
    assert estado.status_code == 200
    assert estado.json()["estado"] == "otorgado"
    assert estado.json()["version_texto"] == "v1"


async def test_get_sin_consentimiento_inexistente(ctx) -> None:
    client, id_inst = ctx
    estado = await client.get("/api/v1/consent/profile", headers=_h(id_inst))
    assert estado.status_code == 200
    assert estado.json()["estado"] == "inexistente"


async def test_revocar_preserva_historico(ctx) -> None:
    client, id_inst = ctx
    await client.post(
        "/api/v1/consent/profile",
        json={"version_texto": "v1", "affirmative_action": True},
        headers=_h(id_inst),
    )
    rev = await client.post("/api/v1/consent/profile/revoke", headers=_h(id_inst))
    assert rev.status_code == 200
    estado = await client.get("/api/v1/consent/profile", headers=_h(id_inst))
    assert estado.json()["estado"] == "revocado"


async def test_sin_token_401(ctx) -> None:
    client, _ = ctx
    resp = await client.get("/api/v1/consent/profile")
    assert resp.status_code == 401
