"""Entrar no depende de cómo se escribieron las mayúsculas.

Por qué existe
--------------
El username se compara EXACTO, y quien entra por el campus lo elige a mano en su
primer ingreso. Dos consecuencias, las dos molestas justo el día del examen:

1. Quien eligió ``JuanPerez`` y escribe ``juanperez`` no entra, y lo que ve es
   "Credenciales inválidas": va a pensar que le fallan la clave o la cuenta.
2. Dos personas pueden quedarse con ``juan_perez`` y ``Juan_Perez``, que a
   simple vista son el mismo nombre. Nadie lo nota hasta que hay que averiguar
   quién es quién.

Lo que se sostiene acá:

- al ELEGIR el username, una variante que solo cambia en mayúsculas se rechaza
  como ya está en uso (evita que el problema 2 se cree)
- al ENTRAR, si no hay coincidencia exacta se prueba sin distinguir mayúsculas
  (resuelve el problema 1 sin tocar lo que ya funcionaba)
- si esa búsqueda encuentra MÁS DE UNA cuenta — datos viejos, anteriores a esta
  guarda — se rechaza el login con el mismo mensaje genérico de siempre, en vez
  de elegir una al azar

Contra DB REAL, sin mocks (regla dura de código).
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.auth.hashing import hashear_password
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.transactional import UsuarioModel
from app.presentation.api.v1.auth.router import router as auth_router

pytestmark = pytest.mark.asyncio

_PASSWORD = "LaClaveDeJuan1"


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada")
    return url


@pytest_asyncio.fixture(scope="module")
async def engine(db_url):
    eng = create_async_engine(db_url, pool_pre_ping=True, future=True, poolclass=NullPool)
    async with eng.begin() as conn:
        await conn.execute(text('DROP TABLE IF EXISTS "usuario" CASCADE'))
        await conn.run_sync(Base.metadata.create_all, tables=[UsuarioModel.__table__])
    yield eng
    async with eng.begin() as conn:
        await conn.execute(text('DROP TABLE IF EXISTS "usuario" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def app(factory):
    application = FastAPI()
    application.state.session_factory = factory

    class _Settings:
        jwt_own_secret = "secreto-de-test-para-el-login-largo"
        jwt_own_issuer = "http://test-issuer.local"
        jwt_audience = "activeexam"
        access_token_ttl_seconds = 900
        refresh_token_ttl_seconds = 3600

    application.state.settings = _Settings()
    application.include_router(auth_router, prefix="/api/v1/auth")
    return application


async def _crear(factory, *, username: str) -> str:
    async with factory() as s:
        u = UsuarioModel(
            username=username,
            email=f"{username.lower()}-{uuid.uuid4().hex[:6]}@uni.edu",
            roles=["estudiante"],
            password_hash=hashear_password(_PASSWORD),
            auth_provider="local",
        )
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
    return uid


async def _login(app, usuario: str) -> int:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        resp = await c.post(
            "/api/v1/auth/login", json={"username": usuario, "password": _PASSWORD}
        )
    return resp.status_code


async def test_entra_escribiendo_el_username_en_otra_caja(app, factory):
    """Eligió `JuanPerez` y escribe `juanperez`: entra."""
    sufijo = uuid.uuid4().hex[:6]
    await _crear(factory, username=f"JuanPerez{sufijo}")

    assert await _login(app, f"juanperez{sufijo}") == 200


async def test_el_username_exacto_sigue_entrando(app, factory):
    """Triangulación: lo que ya funcionaba no se toca."""
    sufijo = uuid.uuid4().hex[:6]
    usuario = f"MariaGomez{sufijo}"
    await _crear(factory, username=usuario)

    assert await _login(app, usuario) == 200


async def test_una_clave_incorrecta_sigue_siendo_401(app, factory):
    """Triangulación: la comparación floja es del USUARIO, no de la contraseña."""
    sufijo = uuid.uuid4().hex[:6]
    await _crear(factory, username=f"Pedro{sufijo}")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        resp = await c.post(
            "/api/v1/auth/login",
            json={"username": f"pedro{sufijo}", "password": "OtraCosa1234"},
        )
    assert resp.status_code == 401


async def test_con_dos_cuentas_que_solo_difieren_en_mayusculas_no_elige_una_al_azar(
    app, factory
):
    """Datos viejos, anteriores a la guarda: entrar sería adivinar quién es quién.

    Se rechaza con el 401 genérico de siempre. Elegir una al azar sería meter a
    alguien en la cuenta de otro.
    """
    sufijo = uuid.uuid4().hex[:6]
    await _crear(factory, username=f"ana{sufijo}")
    await _crear(factory, username=f"Ana{sufijo}")

    assert await _login(app, f"ANA{sufijo}") == 401


async def test_el_exacto_gana_aunque_haya_una_variante(app, factory):
    """Con coincidencia exacta no hace falta desempatar: entra la suya."""
    sufijo = uuid.uuid4().hex[:6]
    await _crear(factory, username=f"lucas{sufijo}")
    await _crear(factory, username=f"Lucas{sufijo}")

    assert await _login(app, f"lucas{sufijo}") == 200
