"""c-78 — Un admin puede resetear la contraseña de un usuario.

Por qué existe
--------------
Encontrado el 26/8/2026: **no había forma de resetear la contraseña de nadie**.
El alta genera una temporal, ``PUT /auth/change-password`` exige la contraseña
actual, el seed no pisa las existentes y no hay "olvidé mi contraseña". La cuenta
``coordinador1`` de producción quedó inaccesible justamente por eso.

El día del examen eso es grave: si un docente olvida su contraseña, nadie puede
ayudarlo desde el sistema y la única salida es entrar a la base a mano.

Es DOMINIO CRÍTICO (auth). Lo que hay que sostener, y es lo que cubre este
módulo:

  - **solo** ``admin_sistema``; cualquier otro rol es 403
  - la contraseña nueva se devuelve UNA vez y queda ``debe_cambiar_password``,
    igual que el alta: el admin no se queda sabiendo la clave de otro
  - la anterior deja de servir en el acto
  - no se puede resetear una cuenta LTI (esa no entra con contraseña; su dueño
    fija la suya desde el dashboard) ni una dada de baja
  - queda registrado en auditoría quién lo hizo

Contra DB REAL, sin mocks (regla dura de código).
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.auth.hashing import (
    HASH_SIN_PASSWORD,
    hashear_password,
    verificar_password,
)
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.transactional import UsuarioModel
from app.presentation.api.v1.users.router import router as users_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_PASSWORD_VIEJA = "LaViejaQueNadieRecuerda1"


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


async def _crear_usuario(
    factory, *, auth_provider: str = "local", eliminado: bool = False
) -> str:
    sufijo = uuid.uuid4().hex[:8]
    async with factory() as s:
        u = UsuarioModel(
            username=f"user-{sufijo}",
            email=f"user-{sufijo}@test.local",
            roles=["coordinador"],
            password_hash=(
                HASH_SIN_PASSWORD
                if auth_provider == "lti"
                else hashear_password(_PASSWORD_VIEJA)
            ),
            auth_provider=auth_provider,
            nombre="Usuario",
            apellido="De Prueba",
        )
        if eliminado:
            from datetime import UTC, datetime

            u.eliminado_en = datetime.now(UTC)
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
    return uid


def _cliente(app, roles: list[str]):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(roles, subject="admin-que-resetea"),
    )


async def _fila(factory, usuario_id: str) -> UsuarioModel:
    async with factory() as s:
        return (
            await s.execute(select(UsuarioModel).where(UsuarioModel.id == usuario_id))
        ).scalar_one()


@pytest.mark.asyncio
async def test_el_admin_resetea_y_recibe_la_clave_una_vez(app, factory):
    uid = await _crear_usuario(factory)

    async with _cliente(app, ["admin_sistema"]) as c:
        resp = await c.post(f"/api/v1/users/{uid}/resetear-password")

    assert resp.status_code == 200, resp.text
    nueva = resp.json()["password_temporal"]
    assert nueva and len(nueva) >= 12, "la temporal tiene que ser larga de verdad"

    fila = await _fila(factory, uid)
    assert verificar_password(nueva, fila.password_hash) is True


@pytest.mark.asyncio
async def test_la_contrasena_anterior_deja_de_servir(app, factory):
    """Si la vieja siguiera andando, resetear no serviría de nada."""
    uid = await _crear_usuario(factory)

    async with _cliente(app, ["admin_sistema"]) as c:
        await c.post(f"/api/v1/users/{uid}/resetear-password")

    fila = await _fila(factory, uid)
    assert verificar_password(_PASSWORD_VIEJA, fila.password_hash) is False


@pytest.mark.asyncio
async def test_queda_obligado_a_cambiarla_al_entrar(app, factory):
    """El admin no se puede quedar sabiendo la contraseña de otra persona."""
    uid = await _crear_usuario(factory)

    async with _cliente(app, ["admin_sistema"]) as c:
        await c.post(f"/api/v1/users/{uid}/resetear-password")

    fila = await _fila(factory, uid)
    assert fila.debe_cambiar_password is True


@pytest.mark.asyncio
async def test_dos_reseteos_seguidos_dan_claves_distintas(app, factory):
    """Triangulación: la temporal es aleatoria, no una constante del código."""
    uid = await _crear_usuario(factory)

    async with _cliente(app, ["admin_sistema"]) as c:
        una = (await c.post(f"/api/v1/users/{uid}/resetear-password")).json()
        otra = (await c.post(f"/api/v1/users/{uid}/resetear-password")).json()

    assert una["password_temporal"] != otra["password_temporal"]


@pytest.mark.asyncio
@pytest.mark.parametrize("rol", ["coordinador", "tutor", "profesor", "estudiante"])
async def test_ningun_otro_rol_puede_resetear(app, factory, rol):
    """La guarda que importa: resetear contraseñas es tomar cuentas ajenas."""
    uid = await _crear_usuario(factory)

    async with _cliente(app, [rol]) as c:
        resp = await c.post(f"/api/v1/users/{uid}/resetear-password")

    assert resp.status_code in (401, 403), f"{rol} pudo resetear: {resp.status_code}"

    fila = await _fila(factory, uid)
    assert verificar_password(_PASSWORD_VIEJA, fila.password_hash) is True, (
        "un rechazo no puede haber cambiado la contraseña"
    )


@pytest.mark.asyncio
async def test_no_se_resetea_una_cuenta_lti(app, factory):
    """Esa cuenta no entra con contraseña: la fija su dueño desde el dashboard.

    Darle una temporal le abriría un camino de entrada que hoy no tiene.
    """
    uid = await _crear_usuario(factory, auth_provider="lti")

    async with _cliente(app, ["admin_sistema"]) as c:
        resp = await c.post(f"/api/v1/users/{uid}/resetear-password")

    assert resp.status_code == 409, resp.text
    fila = await _fila(factory, uid)
    assert fila.password_hash == HASH_SIN_PASSWORD, "no se le puso contraseña"


@pytest.mark.asyncio
async def test_no_se_resetea_una_cuenta_dada_de_baja(app, factory):
    uid = await _crear_usuario(factory, eliminado=True)

    async with _cliente(app, ["admin_sistema"]) as c:
        resp = await c.post(f"/api/v1/users/{uid}/resetear-password")

    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_usuario_inexistente_da_404(app, factory):
    async with _cliente(app, ["admin_sistema"]) as c:
        resp = await c.post(
            "/api/v1/users/00000000-0000-0000-0000-000000000000/resetear-password"
        )

    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Desbloqueo de la cuenta (1/9/2026, antes del examen real del 5/9).
#
# El lockout por intentos fallidos (5 intentos -> 15 min) se chequea ANTES de
# verificar la contraseña, asi que resetearla NO destrababa nada: el admin le
# daba una clave nueva y la persona seguia sin poder entrar. No habia ningun
# endpoint ni pantalla de desbloqueo, con lo cual la unica salida era entrar por
# SQL a la base de produccion con el examen en curso.
#
# El dia del examen esto es exactamente lo que va a pasar: alguien nervioso se
# equivoca cinco veces y pierde quince minutos sin que nadie pueda ayudarlo.
# Resetear la contraseña es la accion que el admin YA tiene a mano, asi que es
# la que tiene que destrabar.
# ---------------------------------------------------------------------------


async def _bloquear(factory, usuario_id: str, *, minutos: int = 15) -> None:
    """Deja la cuenta como la dejan 5 intentos fallidos seguidos."""
    from datetime import UTC, datetime, timedelta

    async with factory() as s:
        u = (
            await s.execute(select(UsuarioModel).where(UsuarioModel.id == usuario_id))
        ).scalar_one()
        u.intentos_fallidos = 5
        u.bloqueado_hasta = datetime.now(UTC) + timedelta(minutes=minutos)
        await s.commit()


@pytest.mark.asyncio
async def test_resetear_destraba_la_cuenta_bloqueada(app, factory):
    """Sin esto, el admin resetea la clave y la persona sigue sin poder entrar."""
    uid = await _crear_usuario(factory)
    await _bloquear(factory, uid)

    async with _cliente(app, ["admin_sistema"]) as c:
        resp = await c.post(f"/api/v1/users/{uid}/resetear-password")

    assert resp.status_code == 200, resp.text
    fila = await _fila(factory, uid)
    assert fila.bloqueado_hasta is None, "la cuenta quedo bloqueada igual"
    assert fila.intentos_fallidos == 0, "el contador de intentos no se limpio"


@pytest.mark.asyncio
async def test_la_clave_nueva_sirve_en_una_cuenta_que_estaba_bloqueada(app, factory):
    """Triangulación: destrabar sin dejar servible la clave nueva no alcanza."""
    uid = await _crear_usuario(factory)
    await _bloquear(factory, uid, minutos=60)

    async with _cliente(app, ["admin_sistema"]) as c:
        resp = await c.post(f"/api/v1/users/{uid}/resetear-password")

    nueva = resp.json()["password_temporal"]
    fila = await _fila(factory, uid)
    assert verificar_password(nueva, fila.password_hash) is True
    assert fila.bloqueado_hasta is None


@pytest.mark.asyncio
async def test_en_una_cuenta_sin_bloqueo_no_cambia_nada(app, factory):
    """Triangulación: el desbloqueo no puede romper el caso normal."""
    uid = await _crear_usuario(factory)

    async with _cliente(app, ["admin_sistema"]) as c:
        resp = await c.post(f"/api/v1/users/{uid}/resetear-password")

    assert resp.status_code == 200, resp.text
    fila = await _fila(factory, uid)
    assert fila.bloqueado_hasta is None
    assert fila.intentos_fallidos == 0
