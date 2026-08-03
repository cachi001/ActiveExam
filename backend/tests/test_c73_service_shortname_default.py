"""Default de `service_shortname` para el canje contraseña→token del docente
(C-73 §10.2 — fix de bug post-cierre).

Bug: `guardar_mi_credencial_moodle` leía el `service_shortname` de la fila
institucional `moodle_credencial` (id=1). Esa fila queda vacía en todos los
ambientes porque la UI de admin que la cargaba quedó desconectada del árbol de
componentes — resultado: NINGÚN docente podía conectar su cuenta por password,
siempre con 422 "Falta el nombre del servicio externo del campus".

Fix: `moodle_mobile_app` es el nombre ESTÁNDAR del web service que expone la
app móvil de Moodle (no es secreto, es el único que usa este sistema) y pasa a
ser una constante (`SERVICE_SHORTNAME_MOODLE_MOBILE` en
`app.application.moodle.token_exchange`), sin depender de configuración de
admin ni de una fila en base. Si el admin SÍ cargó un `service_shortname`
distinto en la fila institucional, ese valor gana sobre la constante (permite
apuntar a un campus con un servicio externo distinto sin re-deploy).

Ejercita el endpoint real (`PUT /config/moodle/mi-credencial`) contra DB real;
solo se mockea el transporte HTTP hacia Moodle (httpx vía respx), nunca la DB.
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest
import pytest_asyncio
import respx
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.moodle.credencial_docente_service import CredencialDocenteService
from app.application.moodle.credencial_service import MoodleCredencialResolver
from app.application.moodle.intentos_fallidos_tracker import IntentosFallidosTracker
from app.application.moodle.token_exchange import SERVICE_SHORTNAME_MOODLE_MOBILE
from app.infrastructure.crypto.secret_encryption import SecretCipher
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: F401
from app.presentation.api.v1.config.router import router as config_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_KEY = "VXqRzW9ksjWE2eCa752juwQdOtAPCrYVnratlmHj7b0="
_BASE = "https://campus.test"


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
        await conn.run_sync(Base.metadata.create_all, tables=[UsuarioModel.__table__])
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def app(factory):
    application = FastAPI()
    application.state.jwt_validator = _build_test_jwt_validator()
    application.state.session_factory = factory
    application.state.credencial_docente = CredencialDocenteService(
        session_factory=factory, cipher=SecretCipher(key=_KEY)
    )
    application.state.moodle_credenciales = MoodleCredencialResolver(
        session_factory=factory,
        cipher=SecretCipher(key=_KEY),
        env_base_url=_BASE,
        env_token="institucional",  # noqa: S106
    )
    application.state.moodle_intentos_fallidos = IntentosFallidosTracker(umbral=5)
    application.include_router(config_router, prefix="/api/v1/config")
    return application


@pytest_asyncio.fixture
async def docente_id(factory):
    legajo = f"D-{uuid.uuid4().hex[:8]}"
    async with factory() as s:
        u = UsuarioModel(id_institucional=legajo, email=f"{legajo.lower()}@uni.edu")
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
    yield uid
    async with factory() as s:
        await s.execute(text("DELETE FROM usuario WHERE id = :i"), {"i": uid})
        await s.commit()


def _client(app, subject: str):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["docente"], subject=subject),
    )


async def _asegurar_sin_fila_institucional(factory) -> None:
    async with factory() as s:
        await s.execute(text("DELETE FROM moodle_credencial WHERE id = 1"))
        await s.commit()


async def _cargar_fila_institucional(factory, service_shortname: str) -> None:
    async with factory() as s:
        await s.execute(
            text(
                "INSERT INTO moodle_credencial (id, base_url, component, service_shortname) "
                "VALUES (1, :base_url, 'mod_assign', :service_shortname) "
                "ON CONFLICT (id) DO UPDATE SET service_shortname = :service_shortname"
            ),
            {"base_url": _BASE, "service_shortname": service_shortname},
        )
        await s.commit()


@pytest.mark.asyncio
@respx.mock
async def test_conectar_por_password_funciona_sin_fila_institucional(
    app, factory, docente_id
):
    """RED del bug: sin fila institucional de `moodle_credencial` (o con
    `service_shortname` vacío en ella), conectar por password debía fallar hoy
    con 422 'Falta el nombre del servicio...'. Después del fix, usa la
    constante `moodle_mobile_app` y funciona."""
    await _asegurar_sin_fila_institucional(factory)

    capturado = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["body"] = request.content.decode()
        return httpx.Response(200, json={"token": "token-de-moodle-1234"})

    respx.post(f"{_BASE}/login/token.php").mock(side_effect=handler)

    async with _client(app, subject=docente_id) as c:
        resp = await c.put(
            "/api/v1/config/moodle/mi-credencial",
            json={"moodle_username": "jperez", "password": "clave-correcta"},
        )

    assert resp.status_code == 200, resp.text
    assert f"service={SERVICE_SHORTNAME_MOODLE_MOBILE}" in capturado["body"]


@pytest.mark.asyncio
@respx.mock
async def test_service_shortname_institucional_pisa_la_constante(
    app, factory, docente_id
):
    """Triangulación: si el admin SÍ cargó un `service_shortname` propio en la
    fila institucional, ese gana sobre la constante — permite apuntar a un
    servicio externo distinto sin tocar código."""
    await _cargar_fila_institucional(factory, "servicio_institucional_custom")

    capturado = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["body"] = request.content.decode()
        return httpx.Response(200, json={"token": "token-de-moodle-5678"})

    respx.post(f"{_BASE}/login/token.php").mock(side_effect=handler)

    async with _client(app, subject=docente_id) as c:
        resp = await c.put(
            "/api/v1/config/moodle/mi-credencial",
            json={"moodle_username": "jperez", "password": "clave-correcta"},
        )

    assert resp.status_code == 200, resp.text
    assert "service=servicio_institucional_custom" in capturado["body"]
    assert f"service={SERVICE_SHORTNAME_MOODLE_MOBILE}" not in capturado["body"]

    await _asegurar_sin_fila_institucional(factory)
