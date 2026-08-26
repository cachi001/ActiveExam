"""El seed puede REESTABLECER la clave de sus usuarios cuando se le pide.

## El agujero operativo que esto cierra

Encontrado el 26/8/2026 limpiando la base de producción. El seed es idempotente y, si el
usuario ya existe, lo saltea entero: **nunca toca el password**. Eso está bien como
comportamiento por defecto — pisar la clave que una persona cambió sería peor — pero deja
un caso sin salida:

  1. Se pierde u olvida la clave de `admin`.
  2. Cambiar `SEED_ADMIN_PASSWORD` en el entorno **no hace nada**, porque el usuario existe.
  3. No queda ninguna forma de entrar, salvo escribir el hash a mano en la base.

A días de un examen real, "el admin no puede entrar y no hay procedimiento" es un problema
serio. `SEED_RESET_PASSWORDS=1` hace converger las claves de los usuarios del seed a lo que
digan las variables, sin cambiar nada más.

## Por qué NO es el default

Sin la variable, el comportamiento es exactamente el de antes. Un despliegue normal no
puede pisar la clave de nadie por accidente: hay que pedirlo explícitamente.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.auth.hashing import hashear_password, verificar_password
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.transactional import UsuarioModel

pytestmark = pytest.mark.asyncio


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
        await conn.execute(text('DROP TABLE IF EXISTS "usuario" CASCADE'))
        await conn.run_sync(Base.metadata.create_all, tables=[UsuarioModel.__table__])
    yield eng
    async with eng.begin() as conn:
        await conn.execute(text('DROP TABLE IF EXISTS "usuario" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _crear(factory, username: str, password: str) -> None:
    async with factory() as s:
        s.add(
            UsuarioModel(
                username=username,
                email=f"{username}@activeexam.local",
                roles=["admin_sistema"],
                password_hash=hashear_password(password),
                auth_provider="jwt",
                attrs_federados={},
            )
        )
        await s.commit()


async def _usuario(factory, username: str) -> UsuarioModel:
    async with factory() as s:
        return (
            await s.execute(select(UsuarioModel).where(UsuarioModel.username == username))
        ).scalar_one()


async def test_sin_la_variable_la_clave_queda_intacta(factory) -> None:
    """El default no cambia: pisar la clave que una persona eligió sería peor que
    el problema que esto viene a resolver."""
    from scripts.seed_users import reestablecer_passwords

    u = f"admin-{uuid.uuid4().hex[:6]}"
    await _crear(factory, u, "LaQueEligioLaPersona")

    cambiados = await reestablecer_passwords(
        factory, {u: "OtraDistinta"}, habilitado=False
    )

    assert cambiados == 0
    assert verificar_password("LaQueEligioLaPersona", (await _usuario(factory, u)).password_hash)


async def test_con_la_variable_la_clave_converge_a_la_del_entorno(factory) -> None:
    """El caso que motivó esto: la clave de `admin` se perdió y hay que recuperarla
    sin escribir un hash a mano en la base de producción."""
    from scripts.seed_users import reestablecer_passwords

    u = f"admin-{uuid.uuid4().hex[:6]}"
    await _crear(factory, u, "LaVieja")

    cambiados = await reestablecer_passwords(factory, {u: "LaNueva"}, habilitado=True)

    assert cambiados == 1
    fila = await _usuario(factory, u)
    assert verificar_password("LaNueva", fila.password_hash)
    assert not verificar_password("LaVieja", fila.password_hash)


async def test_tambien_destraba_una_cuenta_bloqueada(factory) -> None:
    """El lockout anti-fuerza-bruta (5 intentos) es justo lo que se dispara cuando
    alguien pelea con una clave que no recuerda. Restablecerla y dejar la cuenta
    bloqueada 15 minutos más no resuelve nada."""
    from scripts.seed_users import reestablecer_passwords

    u = f"admin-{uuid.uuid4().hex[:6]}"
    await _crear(factory, u, "LaVieja")
    async with factory() as s:
        fila = (
            await s.execute(select(UsuarioModel).where(UsuarioModel.username == u))
        ).scalar_one()
        fila.intentos_fallidos = 5
        from datetime import datetime, timedelta, timezone

        fila.bloqueado_hasta = datetime.now(timezone.utc) + timedelta(minutes=15)
        await s.commit()

    await reestablecer_passwords(factory, {u: "LaNueva"}, habilitado=True)

    fila = await _usuario(factory, u)
    assert fila.intentos_fallidos == 0
    assert fila.bloqueado_hasta is None


async def test_un_usuario_que_no_existe_no_se_crea_por_este_camino(factory) -> None:
    """Restablecer claves NO es dar de alta: si el usuario no está, se informa y se
    sigue. Crear usuarios es responsabilidad del seed normal."""
    from scripts.seed_users import reestablecer_passwords

    cambiados = await reestablecer_passwords(
        factory, {f"fantasma-{uuid.uuid4().hex[:6]}": "X"}, habilitado=True
    )

    assert cambiados == 0


async def test_no_toca_a_los_usuarios_que_no_estan_en_la_lista(factory) -> None:
    """Triangulación: converge SOLO las cuentas del seed. Un alumno que entró por
    el campus y se armó su clave no puede verse afectado."""
    from scripts.seed_users import reestablecer_passwords

    del_seed = f"admin-{uuid.uuid4().hex[:6]}"
    ajeno = f"alumno-{uuid.uuid4().hex[:6]}"
    await _crear(factory, del_seed, "Vieja")
    await _crear(factory, ajeno, "LaDelAlumno")

    await reestablecer_passwords(factory, {del_seed: "Nueva"}, habilitado=True)

    assert verificar_password("LaDelAlumno", (await _usuario(factory, ajeno)).password_hash)


async def test_dos_corridas_seguidas_dejan_el_mismo_resultado(factory) -> None:
    """Idempotente: correrlo dos veces no rompe nada ni deja la cuenta a medias."""
    from scripts.seed_users import reestablecer_passwords

    u = f"admin-{uuid.uuid4().hex[:6]}"
    await _crear(factory, u, "Vieja")

    await reestablecer_passwords(factory, {u: "Nueva"}, habilitado=True)
    await reestablecer_passwords(factory, {u: "Nueva"}, habilitado=True)

    assert verificar_password("Nueva", (await _usuario(factory, u)).password_hash)
