"""Desbloquear una cuenta trabada por intentos fallidos, sin tocarle la contraseña.

Por qué existe
--------------
El login bloquea 15 minutos tras 5 intentos fallidos, y corta por
``bloqueado_hasta`` ANTES de verificar la contraseña. Hasta ahora la única forma
de destrabar a alguien era **resetearle la contraseña**, y eso arrastra dos
efectos que en pleno examen molestan:

  - le cambia la clave, así que la que la persona sabe deja de servir
  - queda ``debe_cambiar_password``, o sea que además tiene que elegir una nueva
    antes de poder rendir

Y, sobre todo, **ninguna pantalla mostraba quién estaba bloqueado**: el admin se
enteraba solo si la persona avisaba. Este módulo cubre las dos mitades:

  - el detalle del usuario dice si está bloqueado y cuánto falta
  - hay un desbloqueo que limpia el bloqueo y NADA más

Es DOMINIO CRÍTICO (auth): solo ``admin_sistema``.

Contra DB REAL, sin mocks (regla dura de código).
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.auth.hashing import hashear_password, verificar_password
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.transactional import UsuarioModel
from app.presentation.api.v1.users.router import router as users_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_PASSWORD = "LaQueLaPersonaSabe1"


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
    application.state.jwt_validator = _build_test_jwt_validator()
    application.state.session_factory = factory
    application.include_router(users_router, prefix="/api/v1/users")
    return application


async def _crear_usuario(factory, *, eliminado: bool = False) -> str:
    sufijo = uuid.uuid4().hex[:8]
    async with factory() as s:
        u = UsuarioModel(
            username=f"user-{sufijo}",
            email=f"user-{sufijo}@test.local",
            roles=["coordinador"],
            password_hash=hashear_password(_PASSWORD),
            auth_provider="local",
            nombre="Usuario",
            apellido="De Prueba",
        )
        if eliminado:
            u.eliminado_en = datetime.now(UTC)
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
    return uid


async def _bloquear(factory, usuario_id: str, *, minutos: float = 15) -> None:
    """Deja la cuenta como la dejan 5 intentos fallidos seguidos."""
    async with factory() as s:
        u = (
            await s.execute(select(UsuarioModel).where(UsuarioModel.id == usuario_id))
        ).scalar_one()
        u.intentos_fallidos = 5
        u.bloqueado_hasta = datetime.now(UTC) + timedelta(minutes=minutos)
        await s.commit()


def _cliente(app, roles: list[str]):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(roles, subject="admin-que-desbloquea"),
    )


async def _fila(factory, usuario_id: str) -> UsuarioModel:
    async with factory() as s:
        return (
            await s.execute(select(UsuarioModel).where(UsuarioModel.id == usuario_id))
        ).scalar_one()


# ---------------------------------------------------------------------------
# El detalle del usuario muestra el bloqueo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_el_detalle_muestra_la_cuenta_bloqueada_y_cuanto_falta(app, factory):
    """Sin esto, el admin no tiene forma de saber quién está trabado."""
    uid = await _crear_usuario(factory)
    await _bloquear(factory, uid, minutos=15)

    async with _cliente(app, ["admin_sistema"]) as c:
        resp = await c.get(f"/api/v1/users/{uid}")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["bloqueado"] is True
    assert body["intentos_fallidos"] == 5
    assert body["bloqueado_hasta"] is not None
    # Margen amplio: lo que importa es que sea el tiempo que falta, no un cero.
    assert 13 * 60 <= body["bloqueo_segundos_restantes"] <= 15 * 60


@pytest.mark.asyncio
async def test_una_cuenta_sin_bloqueo_no_aparece_bloqueada(app, factory):
    """Triangulación: el caso normal no puede quedar marcado."""
    uid = await _crear_usuario(factory)

    async with _cliente(app, ["admin_sistema"]) as c:
        resp = await c.get(f"/api/v1/users/{uid}")

    body = resp.json()
    assert body["bloqueado"] is False
    assert body["bloqueado_hasta"] is None
    assert body["bloqueo_segundos_restantes"] is None
    assert body["intentos_fallidos"] == 0


@pytest.mark.asyncio
async def test_un_bloqueo_ya_vencido_no_se_muestra_como_bloqueo(app, factory):
    """El campo queda con la fecha vieja: leerlo crudo diría 'bloqueado' de más.

    Los ``intentos_fallidos`` SÍ se siguen mostrando aunque el bloqueo haya
    vencido, porque el contador no se limpia solo: con 5 encima, un único error
    más vuelve a bloquear la cuenta otros 15 minutos.
    """
    uid = await _crear_usuario(factory)
    await _bloquear(factory, uid, minutos=-5)

    async with _cliente(app, ["admin_sistema"]) as c:
        resp = await c.get(f"/api/v1/users/{uid}")

    body = resp.json()
    assert body["bloqueado"] is False
    assert body["bloqueado_hasta"] is None
    assert body["bloqueo_segundos_restantes"] is None
    assert body["intentos_fallidos"] == 5


# ---------------------------------------------------------------------------
# POST /{usuario_id}/desbloquear
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_el_admin_desbloquea_la_cuenta(app, factory):
    uid = await _crear_usuario(factory)
    await _bloquear(factory, uid)

    async with _cliente(app, ["admin_sistema"]) as c:
        resp = await c.post(f"/api/v1/users/{uid}/desbloquear")

    assert resp.status_code == 200, resp.text
    assert resp.json()["bloqueado"] is False

    fila = await _fila(factory, uid)
    assert fila.bloqueado_hasta is None
    assert fila.intentos_fallidos == 0


@pytest.mark.asyncio
async def test_desbloquear_no_le_toca_la_contrasena(app, factory):
    """Es toda la diferencia con resetear: la persona entra con la que ya sabe."""
    uid = await _crear_usuario(factory)
    await _bloquear(factory, uid)

    async with _cliente(app, ["admin_sistema"]) as c:
        await c.post(f"/api/v1/users/{uid}/desbloquear")

    fila = await _fila(factory, uid)
    assert verificar_password(_PASSWORD, fila.password_hash) is True
    assert fila.debe_cambiar_password is False, (
        "desbloquear no puede obligar a elegir una clave nueva en pleno examen"
    )


@pytest.mark.asyncio
async def test_desbloquear_una_cuenta_que_no_estaba_bloqueada_no_rompe(app, factory):
    """Triangulación: idempotente. El admin no sabe siempre si está trabada."""
    uid = await _crear_usuario(factory)

    async with _cliente(app, ["admin_sistema"]) as c:
        resp = await c.post(f"/api/v1/users/{uid}/desbloquear")

    assert resp.status_code == 200, resp.text
    fila = await _fila(factory, uid)
    assert fila.bloqueado_hasta is None
    assert fila.intentos_fallidos == 0
    assert verificar_password(_PASSWORD, fila.password_hash) is True


@pytest.mark.asyncio
@pytest.mark.parametrize("rol", ["coordinador", "tutor", "profesor", "estudiante"])
async def test_ningun_otro_rol_puede_desbloquear(app, factory, rol):
    """Desbloquear es levantar la defensa contra fuerza bruta de una cuenta."""
    uid = await _crear_usuario(factory)
    await _bloquear(factory, uid)

    async with _cliente(app, [rol]) as c:
        resp = await c.post(f"/api/v1/users/{uid}/desbloquear")

    assert resp.status_code in (401, 403), f"{rol} pudo desbloquear: {resp.status_code}"

    fila = await _fila(factory, uid)
    assert fila.bloqueado_hasta is not None, "un rechazo no puede haber destrabado"


@pytest.mark.asyncio
async def test_no_se_desbloquea_una_cuenta_dada_de_baja(app, factory):
    uid = await _crear_usuario(factory, eliminado=True)
    await _bloquear(factory, uid)

    async with _cliente(app, ["admin_sistema"]) as c:
        resp = await c.post(f"/api/v1/users/{uid}/desbloquear")

    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_usuario_inexistente_da_404(app, factory):
    async with _cliente(app, ["admin_sistema"]) as c:
        resp = await c.post(
            "/api/v1/users/00000000-0000-0000-0000-000000000000/desbloquear"
        )

    assert resp.status_code == 404, resp.text
