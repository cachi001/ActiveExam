"""C-75 sección 6: administración admin-only del allowlist `lti_deployment_confiable`.

CRUD de la allowlist de deployments Moodle confiables. Sólo `admin_sistema` puede
gestionarlo (spec lti-trust-config §"Administración del allowlist").

DB real (regla dura #4). Se usa `TestClient` (sync) como el resto de los tests de
endpoints; setup/asserts de DB por `asyncio.run` con NullPool.

Cubre:
  6.1 tabla vacía → login/launch rechazado (falla cerrado).
  6.2 admin_sistema puede crear / listar / editar / borrar filas.
  6.3 usuario sin rol admin_sistema → 403; sin token → 401.
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.auth.token import TokenPolicy
from app.infrastructure.auth.jwks_cache import JwksCache
from app.infrastructure.auth.jwt_validator import JwtValidator
from app.infrastructure.auth.verifiers import build_hs256_verify, encode_hs256
from app.infrastructure.crypto.secret_encryption import SecretCipher
from app.infrastructure.persistence.models.lti import LtiDeploymentConfiableModel
from app.infrastructure.persistence.models.transactional import UsuarioModel
from app.presentation.api.v1.admin.lti_router import create_lti_admin_router
from app.presentation.api.v1.lti import create_lti_router

_SECRET = b"test-secret-admin-lti-c75-allowlist-long"
_ISSUER = "http://test-issuer.local"
_AUD = "proctoring-api"


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


def _token(uid: str, roles: list[str]) -> str:
    return encode_hs256(
        {
            "iss": _ISSUER,
            "aud": _AUD,
            "sub": uid,
            "preferred_username": uid,
            "email": f"{uid}@test.local",
            "exp": 9999999999,
            "realm_access": {"roles": roles},
        },
        _SECRET,
    )


async def _limpiar(session_factory) -> None:
    async with session_factory() as s:
        await s.execute(text("DELETE FROM lti_nonce"))
        await s.execute(text("DELETE FROM lti_deployment_confiable"))
        await s.execute(text("DELETE FROM usuario WHERE username LIKE 'admin-lti-%'"))
        await s.commit()


async def _seed_usuarios(session_factory) -> dict[str, str]:
    suffix = uuid.uuid4().hex[:8]
    admin_iid = f"admin-lti-adm-{suffix}"
    est_iid = f"admin-lti-est-{suffix}"
    async with session_factory() as s:
        admin = UsuarioModel(
            username=admin_iid,
            email=f"{admin_iid}@test.local",
            roles=["admin_sistema"],
            auth_provider="local",
            attrs_federados={},
        )
        est = UsuarioModel(
            username=est_iid,
            email=f"{est_iid}@test.local",
            roles=["estudiante"],
            auth_provider="local",
            attrs_federados={},
        )
        s.add(admin)
        s.add(est)
        await s.commit()
        await s.refresh(admin)
        await s.refresh(est)
        return {"admin": str(admin.id), "est": str(est.id)}


async def _contar_deployments(session_factory) -> int:
    async with session_factory() as s:
        filas = (await s.execute(select(LtiDeploymentConfiableModel))).scalars().all()
        return len(filas)


async def _deployment(session_factory, dep_id: str):
    async with session_factory() as s:
        return await s.get(LtiDeploymentConfiableModel, dep_id)


@pytest.fixture
def ctx(session_factory):
    asyncio.run(_limpiar(session_factory))
    ids = asyncio.run(_seed_usuarios(session_factory))
    cipher = SecretCipher(key=Fernet.generate_key().decode())

    app = FastAPI()
    app.state.session_factory = session_factory
    cache = JwksCache(lambda: {"keys": [{"kid": "test-key"}]}, ttl_seconds=3600)
    policy = TokenPolicy(issuers_aceptados=frozenset({_ISSUER}), audience=_AUD)
    app.state.jwt_validator = JwtValidator(
        jwks_cache=cache, policy=policy, verify_fn=build_hs256_verify(_SECRET)
    )
    app.include_router(
        create_lti_admin_router(session_factory=session_factory),
        prefix="/api/v1/admin",
    )
    # También el router LTI público para el test de "tabla vacía → falla cerrado".
    app.include_router(
        create_lti_router(session_factory=session_factory, cipher=cipher),
        prefix="/api/v1/lti",
    )
    client = TestClient(app)
    return {
        "client": client,
        "admin_token": _token(ids["admin"], ["admin_sistema"]),
        "est_token": _token(ids["est"], ["estudiante"]),
        "session_factory": session_factory,
    }


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


_NUEVO = {
    "iss": "https://campustest.frm.utn.edu.ar",
    "deployment_id": "7",
    "client_id": "CLIENT-XYZ",
    "jwks_uri": "https://campustest.frm.utn.edu.ar/mod/lti/certs.php",
}


# --- 6.2 admin CRUD --------------------------------------------------------


def test_admin_crea_deployment(ctx):
    r = ctx["client"].post(
        "/api/v1/admin/lti/deployments", json=_NUEVO, headers=_auth(ctx["admin_token"])
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["iss"] == _NUEVO["iss"]
    assert body["activo"] is True
    assert body["id"]
    assert asyncio.run(_contar_deployments(ctx["session_factory"])) == 1


def test_admin_lista_deployments(ctx):
    ctx["client"].post(
        "/api/v1/admin/lti/deployments", json=_NUEVO, headers=_auth(ctx["admin_token"])
    )
    r = ctx["client"].get(
        "/api/v1/admin/lti/deployments", headers=_auth(ctx["admin_token"])
    )
    assert r.status_code == 200
    filas = r.json()
    assert isinstance(filas, list)
    assert len(filas) == 1
    assert filas[0]["deployment_id"] == "7"


def test_admin_edita_deployment(ctx):
    dep_id = ctx["client"].post(
        "/api/v1/admin/lti/deployments", json=_NUEVO, headers=_auth(ctx["admin_token"])
    ).json()["id"]

    r = ctx["client"].patch(
        f"/api/v1/admin/lti/deployments/{dep_id}",
        json={"activo": False},
        headers=_auth(ctx["admin_token"]),
    )
    assert r.status_code == 200
    assert r.json()["activo"] is False
    fila = asyncio.run(_deployment(ctx["session_factory"], dep_id))
    assert fila.activo is False


def test_admin_borra_deployment(ctx):
    dep_id = ctx["client"].post(
        "/api/v1/admin/lti/deployments", json=_NUEVO, headers=_auth(ctx["admin_token"])
    ).json()["id"]

    r = ctx["client"].delete(
        f"/api/v1/admin/lti/deployments/{dep_id}", headers=_auth(ctx["admin_token"])
    )
    assert r.status_code == 204
    assert asyncio.run(_contar_deployments(ctx["session_factory"])) == 0


def test_editar_inexistente_404(ctx):
    r = ctx["client"].patch(
        f"/api/v1/admin/lti/deployments/{uuid.uuid4()}",
        json={"activo": False},
        headers=_auth(ctx["admin_token"]),
    )
    assert r.status_code == 404


# --- 6.3 autorización ------------------------------------------------------


def test_estudiante_no_puede_gestionar_403(ctx):
    tok = _auth(ctx["est_token"])
    assert ctx["client"].post(
        "/api/v1/admin/lti/deployments", json=_NUEVO, headers=tok
    ).status_code == 403
    assert ctx["client"].get(
        "/api/v1/admin/lti/deployments", headers=tok
    ).status_code == 403
    assert ctx["client"].delete(
        f"/api/v1/admin/lti/deployments/{uuid.uuid4()}", headers=tok
    ).status_code == 403


def test_sin_token_401(ctx):
    assert ctx["client"].get("/api/v1/admin/lti/deployments").status_code == 401


# --- 6.1 falla cerrado -----------------------------------------------------


def test_tabla_vacia_login_rechaza(ctx):
    """Con la allowlist vacía, todo login LTI se rechaza (falla cerrado)."""
    r = ctx["client"].get(
        "/api/v1/lti/login",
        params={
            "iss": "https://campustest.frm.utn.edu.ar",
            "login_hint": "1",
            "target_link_uri": "x",
            "client_id": "CLIENT-XYZ",
        },
        follow_redirects=False,
    )
    assert r.status_code == 403


def test_tras_alta_login_procede(ctx):
    """Tras dar de alta el deployment, el login del mismo iss ya no falla cerrado."""
    ctx["client"].post(
        "/api/v1/admin/lti/deployments", json=_NUEVO, headers=_auth(ctx["admin_token"])
    )
    r = ctx["client"].get(
        "/api/v1/lti/login",
        params={
            "iss": _NUEVO["iss"],
            "login_hint": "1",
            "target_link_uri": "x",
            "client_id": _NUEVO["client_id"],
            "lti_deployment_id": _NUEVO["deployment_id"],
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
