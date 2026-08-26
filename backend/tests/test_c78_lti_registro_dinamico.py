"""c-78 §10.1/§10.2 (E-12, D15) — registro dinámico LTI y salud de la allowlist.

Cubre contra DB REAL:
- el handshake completo persiste la fila con el `client_id`/`deployment_id` que
  devolvió el Platform, y la crea INACTIVA;
- un launch desde ese deployment se rechaza mientras siga inactivo, y pasa el gate
  cuando un admin lo habilita;
- volver a registrarse NO reactiva la fila (un re-registro no es una auto-aprobación);
- `GET /admin/lti/salud` avisa cuando no queda ninguna fila activa.

El único doble es el HTTP contra Moodle (servicio externo), inyectado por el
parámetro `registro_http_cliente` del router. La base es real (regla dura #4).
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.lti import (  # noqa: F401
    LtiDeploymentConfiableModel,
    LtiNonceModel,
    LtiToolKeyModel,
)
from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: F401
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

pytestmark = pytest.mark.asyncio

_TABLAS = [
    "lti_nonce",
    "lti_tool_key",
    "lti_deployment_confiable",
]

_ISS_PLATFORM = "https://campus.test.local"
_CLIENT_ID = "CLIENT-REAL-123"
_DEPLOYMENT_ID = "1"
_JWKS_PLATFORM = f"{_ISS_PLATFORM}/mod/lti/certs.php"
_OPENID_CONFIG_URL = f"{_ISS_PLATFORM}/.well-known/openid-configuration?lti=1"
_REGISTRATION_ENDPOINT = f"{_ISS_PLATFORM}/mod/lti/openid-registration.php"


class _MoodleFalso:
    """Doble del Platform: devuelve la config y acepta el registro.

    Registra lo recibido para poder afirmar que el Tool mandó su configuración
    real y el `registration_token` en el header.
    """

    def __init__(self) -> None:
        self.registros_recibidos: list[dict[str, Any]] = []
        self.tokens_recibidos: list[str | None] = []

    def get_json(self, url: str) -> dict[str, Any]:
        assert url == _OPENID_CONFIG_URL
        return {
            "issuer": _ISS_PLATFORM,
            "registration_endpoint": _REGISTRATION_ENDPOINT,
            "jwks_uri": _JWKS_PLATFORM,
        }

    def post_json(
        self, url: str, *, payload: dict[str, Any], token: str | None
    ) -> dict[str, Any]:
        assert url == _REGISTRATION_ENDPOINT
        self.registros_recibidos.append(payload)
        self.tokens_recibidos.append(token)
        return {
            "client_id": _CLIENT_ID,
            "https://purl.imsglobal.org/spec/lti-tool-configuration": {
                "deployment_id": _DEPLOYMENT_ID,
            },
        }


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
        for t in _TABLAS:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                LtiDeploymentConfiableModel.__table__,
                LtiNonceModel.__table__,
                LtiToolKeyModel.__table__,
            ],
        )
    yield eng
    async with eng.begin() as conn:
        for t in _TABLAS:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def moodle():
    return _MoodleFalso()


@pytest_asyncio.fixture
async def app(factory, moodle):
    from cryptography.fernet import Fernet

    from app.infrastructure.crypto.secret_encryption import SecretCipher
    from app.presentation.api.v1.admin import create_lti_admin_router
    from app.presentation.api.v1.lti import create_lti_router

    application = FastAPI()
    application.state.jwt_validator = _build_test_jwt_validator()
    application.state.session_factory = factory
    application.include_router(
        create_lti_router(
            session_factory=factory,
            cipher=SecretCipher(key=Fernet.generate_key().decode()),
            registro_http_cliente=moodle,
        ),
        prefix="/api/v1/lti",
    )
    application.include_router(
        create_lti_admin_router(session_factory=factory),
        prefix="/api/v1/admin",
    )
    return application


def _cliente(app, roles: list[str] | None = None):
    headers = auth_headers(roles or ["admin_sistema"], subject=str(uuid.uuid4()))
    return AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=headers
    )


async def _limpiar_allowlist(factory) -> None:
    async with factory() as s:
        await s.execute(text("DELETE FROM lti_deployment_confiable"))
        await s.commit()


async def _registrar(app) -> dict:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        resp = await c.get(
            "/api/v1/lti/dynamic-registration",
            params={
                "openid_configuration": _OPENID_CONFIG_URL,
                "registration_token": "tok-de-registro",
            },
        )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# §10.1 — el registro dinámico crea la fila con los datos reales
# ---------------------------------------------------------------------------


async def test_sin_openid_configuration_sigue_devolviendo_la_config_del_tool(app):
    """Retrocompatible: el modo "publicar la config" no se rompió."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        resp = await c.get("/api/v1/lti/dynamic-registration")

    assert resp.status_code == 200, resp.text
    cuerpo = resp.json()
    assert cuerpo["client_name"] == "ActiveExam"
    assert cuerpo["token_endpoint_auth_method"] == "private_key_jwt"
    assert "jwks_uri" in cuerpo


async def test_registro_dinamico_persiste_la_fila_con_datos_reales(
    app, factory, moodle
):
    await _limpiar_allowlist(factory)

    cuerpo = await _registrar(app)

    assert cuerpo["client_id"] == _CLIENT_ID
    assert cuerpo["deployment_id"] == _DEPLOYMENT_ID
    assert cuerpo["iss"] == _ISS_PLATFORM
    assert cuerpo["ya_existia"] is False

    # El Tool mandó SU configuración, autenticada con el token del Platform.
    assert moodle.tokens_recibidos[-1] == "tok-de-registro"
    assert moodle.registros_recibidos[-1]["client_name"] == "ActiveExam"

    async with factory() as s:
        fila = (
            await s.execute(
                select(LtiDeploymentConfiableModel).where(
                    LtiDeploymentConfiableModel.client_id == _CLIENT_ID
                )
            )
        ).scalar_one()
        assert fila.iss == _ISS_PLATFORM
        assert fila.deployment_id == _DEPLOYMENT_ID
        assert fila.jwks_uri == _JWKS_PLATFORM


# ---------------------------------------------------------------------------
# §10.1 — nace inactiva y la habilita una persona
# ---------------------------------------------------------------------------


async def test_la_fila_nace_inactiva_y_el_launch_se_rechaza(app, factory):
    await _limpiar_allowlist(factory)
    cuerpo = await _registrar(app)
    assert cuerpo["activo"] is False, "el registro NO puede auto-aprobarse"

    # Un login OIDC desde ese deployment falla cerrado mientras siga inactivo.
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        login = await c.post(
            "/api/v1/lti/login",
            data={
                "iss": _ISS_PLATFORM,
                "login_hint": "7",
                "target_link_uri": "http://test/api/v1/lti/launch",
                "client_id": _CLIENT_ID,
                "lti_deployment_id": _DEPLOYMENT_ID,
            },
        )
    assert login.status_code == 403, login.text
    assert login.json()["detail"] == "lti_iss_no_confiable"


async def test_admin_habilita_y_el_launch_pasa_el_gate(app, factory):
    await _limpiar_allowlist(factory)
    cuerpo = await _registrar(app)

    async with _cliente(app) as c:
        patch = await c.patch(
            f"/api/v1/admin/lti/deployments/{cuerpo['id']}", json={"activo": True}
        )
    assert patch.status_code == 200, patch.text
    assert patch.json()["activo"] is True

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        login = await c.post(
            "/api/v1/lti/login",
            data={
                "iss": _ISS_PLATFORM,
                "login_hint": "7",
                "target_link_uri": "http://test/api/v1/lti/launch",
                "client_id": _CLIENT_ID,
                "lti_deployment_id": _DEPLOYMENT_ID,
            },
            follow_redirects=False,
        )
    # Pasa el gate de confianza: ya no es 403 (redirige a la autorización de Moodle).
    assert login.status_code != 403, login.text


async def test_re_registrarse_no_reactiva_la_fila(app, factory):
    """Un Moodle no puede auto-aprobarse volviendo a registrarse."""
    await _limpiar_allowlist(factory)
    cuerpo = await _registrar(app)

    async with _cliente(app) as c:
        await c.patch(
            f"/api/v1/admin/lti/deployments/{cuerpo['id']}", json={"activo": False}
        )

    segundo = await _registrar(app)
    assert segundo["ya_existia"] is True
    assert segundo["activo"] is False
    assert segundo["id"] == cuerpo["id"], "no debe duplicar la fila"


# ---------------------------------------------------------------------------
# §10.2 — señal de salud
# ---------------------------------------------------------------------------


async def test_salud_avisa_cuando_no_queda_ninguna_fila_activa(app, factory):
    await _limpiar_allowlist(factory)

    async with _cliente(app) as c:
        vacia = await c.get("/api/v1/admin/lti/salud")
    assert vacia.status_code == 200, vacia.text
    assert vacia.json()["allowlist_vacia"] is True
    assert vacia.json()["deployments_totales"] == 0

    cuerpo = await _registrar(app)

    async with _cliente(app) as c:
        sin_habilitar = await c.get("/api/v1/admin/lti/salud")
    # Hay una fila pero ninguna activa: sigue siendo "nadie puede entrar".
    assert sin_habilitar.json()["allowlist_vacia"] is True
    assert sin_habilitar.json()["deployments_totales"] == 1

    async with _cliente(app) as c:
        await c.patch(
            f"/api/v1/admin/lti/deployments/{cuerpo['id']}", json={"activo": True}
        )
        habilitada = await c.get("/api/v1/admin/lti/salud")

    assert habilitada.json()["allowlist_vacia"] is False
    assert habilitada.json()["deployments_activos"] == 1


async def test_salud_es_admin_only(app, factory):
    async with _cliente(app, ["tutor"]) as c:
        resp = await c.get("/api/v1/admin/lti/salud")
    assert resp.status_code in (401, 403), resp.text
