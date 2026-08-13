"""C-75 secciones 2-3: JWKS + registro dinámico + login OIDC del Tool LTI.

DB real (regla dura #4). Se usa `TestClient` (sync) como el resto de los tests de
endpoints del repo — NO httpx.AsyncClient en fixture async, que rompe el loop
session-scoped de pytest-asyncio cuando corre un segundo módulo async. Las
operaciones de DB (setup/asserts) van por `asyncio.run` con NullPool.

Cubre:
  2.1 GET /lti/jwks devuelve un JWK Set válido (y es idempotente: no duplica clave).
  2.3 GET /lti/dynamic-registration devuelve la config IMS (login/redirect/jwks uris).
  3.1 login desde deployment confiable → 302 a Moodle con state+nonce persistidos.
  3.2 login desde deployment NO confiable → 403 sin persistir state/nonce (falla cerrado).
"""

from __future__ import annotations

import asyncio
import os

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.crypto.secret_encryption import SecretCipher
from app.infrastructure.persistence.models.lti import (
    LtiDeploymentConfiableModel,
    LtiNonceModel,
)
from app.presentation.api.v1.lti import create_lti_router


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada — test de integración omitido")
    return url


@pytest.fixture
def session_factory(db_url):
    engine = create_async_engine(db_url, poolclass=NullPool, future=True)
    return async_sessionmaker(engine, expire_on_commit=False)


async def _limpiar(session_factory) -> None:
    async with session_factory() as s:
        await s.execute(text("DELETE FROM lti_nonce"))
        await s.execute(text("DELETE FROM lti_deployment_confiable"))
        await s.execute(text("DELETE FROM lti_tool_key"))
        await s.commit()


async def _insertar_deployment(session_factory, *, iss, deployment_id, client_id) -> None:
    async with session_factory() as s:
        s.add(
            LtiDeploymentConfiableModel(
                iss=iss,
                deployment_id=deployment_id,
                client_id=client_id,
                jwks_uri=f"{iss}/mod/lti/certs.php",
            )
        )
        await s.commit()


async def _nonces(session_factory) -> list:
    async with session_factory() as s:
        return (await s.execute(select(LtiNonceModel))).scalars().all()


@pytest.fixture
def client(session_factory):
    asyncio.run(_limpiar(session_factory))
    cipher = SecretCipher(key=Fernet.generate_key().decode())
    app = FastAPI()
    app.include_router(
        create_lti_router(session_factory=session_factory, cipher=cipher),
        prefix="/api/v1/lti",
    )
    return TestClient(app)


# --- 2.1 JWKS --------------------------------------------------------------


def test_jwks_devuelve_jwk_set_valido(client):
    r = client.get("/api/v1/lti/jwks")
    assert r.status_code == 200
    jwk = r.json()["keys"][0]
    assert jwk["kty"] == "RSA"
    assert jwk["use"] == "sig"
    assert jwk["alg"] == "RS256"
    assert jwk["kid"]
    assert "d" not in jwk  # la privada NUNCA se expone


def test_jwks_idempotente_no_duplica_clave(client):
    kids1 = {k["kid"] for k in client.get("/api/v1/lti/jwks").json()["keys"]}
    kids2 = {k["kid"] for k in client.get("/api/v1/lti/jwks").json()["keys"]}
    assert kids1 == kids2
    assert len(kids2) == 1, "el JWKS generó una clave nueva en cada request"


# --- 2.3 Registro dinámico -------------------------------------------------


def test_dynamic_registration_config_ims(client):
    body = client.get("/api/v1/lti/dynamic-registration").json()
    assert body["initiate_login_uri"].endswith("/api/v1/lti/login")
    assert body["redirect_uris"][0].endswith("/api/v1/lti/launch")
    assert body["jwks_uri"].endswith("/api/v1/lti/jwks")
    tool = body["https://purl.imsglobal.org/spec/lti-tool-configuration"]
    assert tool["target_link_uri"].endswith("/api/v1/lti/launch")


# --- 3.1 / 3.2 Login OIDC --------------------------------------------------


def test_login_confiable_redirige_y_persiste_state_nonce(client, session_factory):
    iss = "https://campustest.frm.utn.edu.ar"
    asyncio.run(
        _insertar_deployment(
            session_factory, iss=iss, deployment_id="1", client_id="CLIENT123"
        )
    )

    r = client.get(
        "/api/v1/lti/login",
        params={
            "iss": iss,
            "login_hint": "42",
            "target_link_uri": "https://tool.example/api/v1/lti/launch",
            "client_id": "CLIENT123",
            "lti_deployment_id": "1",
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    loc = r.headers["location"]
    assert loc.startswith(f"{iss}/mod/lti/auth.php?")
    assert "response_type=id_token" in loc
    assert "state=" in loc
    assert "nonce=" in loc

    filas = asyncio.run(_nonces(session_factory))
    assert len(filas) == 1
    assert filas[0].iss == iss
    assert filas[0].consumido_en is None


def test_login_post_confiable_redirige_y_persiste(client, session_factory):
    """LTI 1.3 permite el initiate-login por POST (form-encoded). Moodle lo usa así."""
    iss = "https://campustest.frm.utn.edu.ar"
    asyncio.run(
        _insertar_deployment(
            session_factory, iss=iss, deployment_id="1", client_id="CLIENT123"
        )
    )

    r = client.post(
        "/api/v1/lti/login",
        data={
            "iss": iss,
            "login_hint": "42",
            "target_link_uri": "https://tool.example/api/v1/lti/launch",
            "client_id": "CLIENT123",
            "lti_deployment_id": "1",
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    loc = r.headers["location"]
    assert loc.startswith(f"{iss}/mod/lti/auth.php?")
    assert "nonce=" in loc

    filas = asyncio.run(_nonces(session_factory))
    assert len(filas) == 1


def test_login_no_confiable_rechaza_sin_persistir(client, session_factory):
    r = client.get(
        "/api/v1/lti/login",
        params={
            "iss": "https://evil.example.org",
            "login_hint": "1",
            "target_link_uri": "x",
            "client_id": "DESCONOCIDO",
        },
        follow_redirects=False,
    )
    assert r.status_code == 403
    assert asyncio.run(_nonces(session_factory)) == []
