"""Los refresh tokens muertos no pueden acumularse para siempre.

## El defecto

`refresh_tokens` solo crecía: no había NADA que borrara filas. Medido en
desarrollo el 29/8/2026, después de un día de pruebas: `admin` con 85 sesiones,
`estudiante1` con 25, `estudiante2` con 21.

Cada login crea una fila, y cada refresh rota la anterior (marca `rotado_en`) y
crea otra. En un examen de una hora con tokens de 15 minutos, cada alumno rota
unas 4 veces: 100 alumnos son ~500 filas por examen, ninguna de las cuales se
borra nunca.

Mismo patrón que las capturas: algo que crece sin techo.

## Qué se borra y qué no

- **Vencidos** (`expires_at < ahora`): imposibles de usar. Se borran siempre.
- **Rotados hace más de un día**: ya fueron canjeados; `rotate_async` los rechaza
  por `rotado_en != NULL`. Se les deja 24 h de gracia por si hiciera falta mirar
  un reuso reciente.
- **Vigentes**: NO se tocan. Borrar uno cierra la sesión de alguien que está
  usando el sistema — posiblemente rindiendo.

## Por qué borrar los rotados no debilita la detección de reuso

`rotate_async` levanta `RefreshTokenError` cuando el token no está vigente, y lo
resuelve con un `scalar_one_or_none()`: da igual si la fila está marcada como
rotada o si ya no existe, las dos caen en `registro_viejo is None` y producen el
mismo error. La protección se conserva.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.compliance.purga_refresh_tokens import purgar_refresh_tokens_muertos
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.transactional import (
    RefreshTokenModel,
    UsuarioModel,
)

_TABLES = ["refresh_tokens", "usuario"]


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
        for t in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[UsuarioModel.__table__, RefreshTokenModel.__table__],
        )
    yield eng
    async with eng.begin() as conn:
        for t in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture(autouse=True)
async def _limpiar(engine):
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE refresh_tokens, usuario CASCADE"))
    yield


async def _usuario(factory) -> str:
    async with factory() as s:
        u = UsuarioModel(
            username=f"u-{uuid.uuid4().hex[:8]}",
            email=f"{uuid.uuid4().hex[:8]}@test.local",
            password_hash="x",
            roles=["estudiante"],
        )
        s.add(u)
        await s.flush()
        uid = u.id
        await s.commit()
    return uid


async def _token(
    factory, usuario_id: str, *, vence_en_dias: float, rotado_hace_horas: float | None = None
) -> str:
    ahora = datetime.now(timezone.utc)
    async with factory() as s:
        t = RefreshTokenModel(
            jti=uuid.uuid4().hex,
            usuario_id=usuario_id,
            expires_at=ahora + timedelta(days=vence_en_dias),
            rotado_en=(
                ahora - timedelta(hours=rotado_hace_horas)
                if rotado_hace_horas is not None
                else None
            ),
        )
        s.add(t)
        await s.flush()
        jti = t.jti
        await s.commit()
    return jti


async def _quedan(factory) -> int:
    async with factory() as s:
        return (
            await s.execute(select(func.count()).select_from(RefreshTokenModel))
        ).scalar_one()


@pytest.mark.asyncio
async def test_borra_los_vencidos(factory):
    uid = await _usuario(factory)
    await _token(factory, uid, vence_en_dias=-1)

    assert await purgar_refresh_tokens_muertos(factory) == 1
    assert await _quedan(factory) == 0


@pytest.mark.asyncio
async def test_no_toca_una_sesion_vigente(factory):
    """El caso que importa: borrar esto cierra la sesión de alguien rindiendo."""
    uid = await _usuario(factory)
    await _token(factory, uid, vence_en_dias=7)

    assert await purgar_refresh_tokens_muertos(factory) == 0
    assert await _quedan(factory) == 1


@pytest.mark.asyncio
async def test_borra_los_rotados_viejos(factory):
    uid = await _usuario(factory)
    await _token(factory, uid, vence_en_dias=7, rotado_hace_horas=48)

    assert await purgar_refresh_tokens_muertos(factory) == 1


@pytest.mark.asyncio
async def test_le_da_gracia_a_un_rotado_recien(factory):
    """24 h de margen: un reuso reciente sigue encontrando su fila."""
    uid = await _usuario(factory)
    await _token(factory, uid, vence_en_dias=7, rotado_hace_horas=1)

    assert await purgar_refresh_tokens_muertos(factory) == 0


@pytest.mark.asyncio
async def test_deja_la_tabla_acotada_a_lo_util(factory):
    """Triangulación con los cuatro casos juntos."""
    uid = await _usuario(factory)
    await _token(factory, uid, vence_en_dias=-1)  # vencido
    await _token(factory, uid, vence_en_dias=7, rotado_hace_horas=48)  # rotado viejo
    await _token(factory, uid, vence_en_dias=7, rotado_hace_horas=1)  # rotado recién
    await _token(factory, uid, vence_en_dias=7)  # vigente

    assert await purgar_refresh_tokens_muertos(factory) == 2
    assert await _quedan(factory) == 2


@pytest.mark.asyncio
async def test_es_idempotente(factory):
    uid = await _usuario(factory)
    await _token(factory, uid, vence_en_dias=-1)

    assert await purgar_refresh_tokens_muertos(factory) == 1
    assert await purgar_refresh_tokens_muertos(factory) == 0


@pytest.mark.asyncio
async def test_no_rompe_el_arranque_si_la_base_falla():
    """Best-effort: corre en una tarea de fondo y no puede tumbar la app."""

    def _factory_rota():
        raise RuntimeError("base caída")

    assert await purgar_refresh_tokens_muertos(_factory_rota) == 0
