"""C-74 §9 RED -> GREEN -> TRIANGULATE: sync del banco desde Moodle.

Cubre:
  9.3 sync_banco_desde_moodle: upsert de categorías por (nombre, padre).
  9.5 Jerarquía anidada: sync con padres e hijos → jerarquía correcta en DB.
  9.5 Idempotencia: segunda sync del mismo curso → 0 duplicados.

Los tests MOCKEAN la llamada HTTP a Moodle (no hay campus real en CI).
Se usa ``unittest.mock.patch`` sobre ``httpx.AsyncClient.post``.
La DB sí es real (proctoring_test) — sin mocks de DB (regla dura #4).
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.exam_content.moodle_sync_service import (
    MoodleSyncError,
    sync_banco_desde_moodle,
)
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    CategoriaPreguntaModel,
    MateriaModel,
)

_TABLES = [
    "pregunta_examen",
    "examen_contenido",
    "categoria_pregunta",
    "materia",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
        for name in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                MateriaModel.__table__,
                CategoriaPreguntaModel.__table__,
            ],
        )
    yield eng
    async with eng.begin() as conn:
        for name in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
        await s.rollback()


@pytest_asyncio.fixture
async def materia_id(session: AsyncSession) -> str:
    mid = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, :n)"),
        {"id": mid, "c": f"SY-{mid[:8]}", "n": "Sync Test Materia"},
    )
    await session.commit()
    return mid


def _mock_response(data) -> MagicMock:
    """Crea un mock de respuesta httpx que devuelve ``data`` como JSON."""
    resp = MagicMock()
    resp.status_code = 200
    resp.content = b'[{"id":1}]'  # no vacío
    resp.json.return_value = data
    return resp


def _mock_http(data) -> AsyncMock:
    """Context manager mock de AsyncClient que responde ``data`` en ``.post()``."""
    client_mock = AsyncMock()
    client_mock.post = AsyncMock(return_value=_mock_response(data))
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=client_mock)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


# ---------------------------------------------------------------------------
# Tests puros (sin DB) — parser de categorías
# ---------------------------------------------------------------------------


def test_9_3_categorias_lista_plana():
    """9.3 RED: sync_banco_desde_moodle existe y acepta los parámetros correctos."""
    import inspect
    sig = inspect.signature(sync_banco_desde_moodle)
    params = set(sig.parameters.keys())
    assert "db" in params
    assert "courseid" in params
    assert "materia_id" in params
    assert "token" in params
    assert "base_url" in params


# ---------------------------------------------------------------------------
# 9.5 Test: jerarquía con padre e hijo → correcta en DB
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_9_5_sync_jerarquia_categorias(session: AsyncSession, materia_id: str):
    """9.5 GREEN: sync con 2 categorías (1 raíz + 1 hija) → jerarquía en DB."""
    # Moodle devuelve: padre (id=1) y hijo (id=2, parent=1)
    categorias_moodle = [
        {"id": 1, "name": "Algebra", "parent": 0},
        {"id": 2, "name": "Polinomios", "parent": 1},
    ]

    with patch("httpx.AsyncClient", return_value=_mock_http(categorias_moodle)):
        resultado = await sync_banco_desde_moodle(
            db=session,
            courseid=42,
            materia_id=materia_id,
            token="tok_test",
            base_url="https://campus.test",
        )
        await session.commit()

    assert resultado["categorias_creadas"] == 2

    # Verificar la jerarquía en DB
    rows = (
        await session.execute(
            select(CategoriaPreguntaModel).where(
                CategoriaPreguntaModel.materia_id == materia_id
            )
        )
    ).scalars().all()

    by_nombre = {r.nombre: r for r in rows}
    assert "Algebra" in by_nombre
    assert "Polinomios" in by_nombre

    padre = by_nombre["Algebra"]
    hijo = by_nombre["Polinomios"]
    assert padre.categoria_padre_id is None, "Algebra debe ser raíz"
    assert hijo.categoria_padre_id == padre.id, "Polinomios debe tener a Algebra como padre"


@pytest.mark.asyncio
async def test_9_5b_sync_tres_niveles(session: AsyncSession, materia_id: str):
    """9.5 TRIANGULATE: 3 niveles de jerarquía (abuelo → padre → hijo)."""
    categorias_moodle = [
        {"id": 10, "name": "Matematica", "parent": 0},
        {"id": 11, "name": "Calculo", "parent": 10},
        {"id": 12, "name": "Limites", "parent": 11},
    ]

    with patch("httpx.AsyncClient", return_value=_mock_http(categorias_moodle)):
        resultado = await sync_banco_desde_moodle(
            db=session,
            courseid=99,
            materia_id=materia_id,
            token="tok_test",
            base_url="https://campus.test",
        )
        await session.commit()

    assert resultado["categorias_creadas"] == 3

    rows = (
        await session.execute(
            select(CategoriaPreguntaModel).where(
                CategoriaPreguntaModel.materia_id == materia_id
            )
        )
    ).scalars().all()

    by_nombre = {r.nombre: r for r in rows}
    assert "Matematica" in by_nombre
    assert "Calculo" in by_nombre
    assert "Limites" in by_nombre

    abuelo = by_nombre["Matematica"]
    padre = by_nombre["Calculo"]
    hijo = by_nombre["Limites"]

    assert abuelo.categoria_padre_id is None
    assert padre.categoria_padre_id == abuelo.id
    assert hijo.categoria_padre_id == padre.id


# ---------------------------------------------------------------------------
# 9.5 Idempotencia: segunda sync → 0 duplicados
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_9_5c_segunda_sync_es_idempotente(session: AsyncSession, materia_id: str):
    """9.5 GREEN: segunda sync del mismo curso → 0 nuevas categorías, sin duplicados."""
    categorias_moodle = [
        {"id": 20, "name": "Fisica", "parent": 0},
        {"id": 21, "name": "Mecanica", "parent": 20},
    ]

    # Primera sincronización
    with patch("httpx.AsyncClient", return_value=_mock_http(categorias_moodle)):
        r1 = await sync_banco_desde_moodle(
            db=session,
            courseid=77,
            materia_id=materia_id,
            token="tok_test",
            base_url="https://campus.test",
        )
        await session.commit()

    assert r1["categorias_creadas"] == 2

    # Segunda sincronización con las mismas categorías
    with patch("httpx.AsyncClient", return_value=_mock_http(categorias_moodle)):
        r2 = await sync_banco_desde_moodle(
            db=session,
            courseid=77,
            materia_id=materia_id,
            token="tok_test",
            base_url="https://campus.test",
        )
        await session.commit()

    # No se deben haber creado nuevas categorías
    assert r2["categorias_creadas"] == 0, (
        f"Segunda sync debería crear 0 categorías, creó {r2['categorias_creadas']}"
    )

    # Verificar que no hay duplicados en DB
    rows = (
        await session.execute(
            select(CategoriaPreguntaModel).where(
                CategoriaPreguntaModel.materia_id == materia_id,
                CategoriaPreguntaModel.nombre.in_(["Fisica", "Mecanica"]),
            )
        )
    ).scalars().all()

    nombres = [r.nombre for r in rows]
    assert nombres.count("Fisica") == 1, "Fisica duplicada"
    assert nombres.count("Mecanica") == 1, "Mecanica duplicada"


@pytest.mark.asyncio
async def test_9_5d_sync_vacia_no_crea_nada(session: AsyncSession, materia_id: str):
    """9.5 TRIANGULATE: Moodle devuelve lista vacía → 0 categorías creadas."""
    with patch("httpx.AsyncClient", return_value=_mock_http([])):
        resultado = await sync_banco_desde_moodle(
            db=session,
            courseid=555,
            materia_id=materia_id,
            token="tok_test",
            base_url="https://campus.test",
        )
        await session.commit()

    assert resultado["categorias_creadas"] == 0
    assert resultado["preguntas_nuevas"] == 0
    assert resultado["preguntas_actualizadas"] == 0


@pytest.mark.asyncio
async def test_9_5e_moodle_error_eleva_excepcion(session: AsyncSession, materia_id: str):
    """9.5 TRIANGULATE: Moodle devuelve error → se eleva MoodleSyncError."""
    error_body = {"exception": "moodle_exception", "errorcode": "invalidtoken", "message": "Token inválido"}
    with patch("httpx.AsyncClient", return_value=_mock_http(error_body)):
        with pytest.raises(MoodleSyncError, match="invalidtoken"):
            await sync_banco_desde_moodle(
                db=session,
                courseid=1,
                materia_id=materia_id,
                token="bad_token",
                base_url="https://campus.test",
            )
