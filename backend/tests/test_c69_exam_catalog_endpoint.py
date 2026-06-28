"""RED → GREEN → TRIANGULATE: tests del endpoint GET /api/v1/exam-content/ (catálogo).

Endpoint: GET /api/v1/exam-content/
Guard:    cualquier principal autenticado (get_current_principal, sin admin, sin MFA).
Contrato: devuelve [{id, titulo, cantidad_preguntas}] en orden alfabético.
D3:       es_correcta NUNCA en la respuesta.

TDD Cycle:
  RED:         tests escritos primero (endpoint aún no existe → falla).
  GREEN:       se agrega GET "" al create_exam_taking_router.
  TRIANGULATE: múltiples escenarios y variantes.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.repositories.exam_content import (
    ExamenContenidoSqlRepository,
)
from app.domain.exam_content.entities import ExamenContenido, OpcionRespuesta, Pregunta
from app.presentation.api.v1.exam_content.router import create_exam_taking_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

# El handler GET "" hace LEFT JOIN a comision/materia (D11): deben existir.
_NEW_TABLES = (
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "comision",
    "materia",
)


# ---------------------------------------------------------------------------
# Fixtures: app sin DB para tests de 401
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app_noauth():
    """App mínima con el taking router pero sin DB — para tests 401."""
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    router = create_exam_taking_router(session_factory=None)
    app.include_router(router, prefix="/api/v1/exam-content")
    return app


@pytest_asyncio.fixture
async def client_noauth(app_noauth):
    async with AsyncClient(
        transport=ASGITransport(app=app_noauth), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Fixtures: app con DB real
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada — tests de integración omitidos")
    return url


@pytest_asyncio.fixture(scope="module")
async def db_engine(db_url):
    eng = create_async_engine(db_url, pool_pre_ping=True, future=True, poolclass=NullPool)
    async with eng.begin() as conn:
        for name in _NEW_TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                MateriaModel.__table__,
                ComisionModel.__table__,
                ExamenContenidoModel.__table__,
                PreguntaExamenModel.__table__,
                OpcionRespuestaModel.__table__,
            ],
        )
    yield eng
    async with eng.begin() as conn:
        for name in _NEW_TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def app_student(db_engine):
    """App con taking router + DB real + JWT de test."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    router = create_exam_taking_router(session_factory=factory)
    app.include_router(router, prefix="/api/v1/exam-content")
    return app, factory


@pytest_asyncio.fixture
async def client_student(app_student):
    app, _ = app_student
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["estudiante"]),
    ) as c:
        yield c


@pytest_asyncio.fixture
async def factory(app_student):
    _, fac = app_student
    return fac


# ---------------------------------------------------------------------------
# Helper para insertar exámenes de prueba
# ---------------------------------------------------------------------------


def _examen_con_preguntas(titulo: str, n: int) -> ExamenContenido:
    return ExamenContenido(
        titulo=titulo,
        preguntas=tuple(
            Pregunta(
                enunciado=f"P{i}",
                tipo="multichoice",
                orden=i,
                opciones=(
                    OpcionRespuesta(texto="A", es_correcta=True, orden=0),
                    OpcionRespuesta(texto="B", es_correcta=False, orden=1),
                ),
            )
            for i in range(n)
        ),
        comision_id=None,
    )


# ---------------------------------------------------------------------------
# RED: test de 401 sin auth (sin DB — verifica que el endpoint requiere auth)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listar_sin_auth_devuelve_401(client_noauth):
    """GET /api/v1/exam-content/ sin Authorization → 401."""
    resp = await client_noauth.get("/api/v1/exam-content/")
    assert resp.status_code in (401, 403), (
        f"Se esperaba 401/403 sin auth, se obtuvo {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# GREEN: tests funcionales (requieren DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listar_vacio_devuelve_lista_vacia(client_student):
    """GET /api/v1/exam-content/ con BD vacía → 200 + lista vacía."""
    resp = await client_student.get("/api/v1/exam-content/")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert data == [], f"Se esperaba [] en BD vacía, se obtuvo {data}"


@pytest.mark.asyncio
async def test_listar_devuelve_examen_importado(client_student, factory):
    """GET /api/v1/exam-content/ devuelve los exámenes importados con id, titulo, cantidad_preguntas."""
    async with factory() as session:
        repo = ExamenContenidoSqlRepository(session)
        guardado = await repo.guardar(_examen_con_preguntas("Parcial de Prueba", 3))
        await session.commit()

    resp = await client_student.get("/api/v1/exam-content/")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)

    item = next((x for x in data if x["id"] == guardado.id), None)
    assert item is not None, f"El examen {guardado.id!r} no está en la respuesta: {data}"
    assert item["titulo"] == "Parcial de Prueba"
    assert item["cantidad_preguntas"] == 3


# ---------------------------------------------------------------------------
# TRIANGULATE: shape de la respuesta, es_correcta ausente, orden
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listar_shape_tiene_solo_campos_permitidos(client_student, factory):
    """Cada item del catálogo tiene solo {id, titulo, cantidad_preguntas}.

    D3: es_correcta NUNCA presente. Pydantic extra='forbid' garantiza
    que campos adicionales del backend tampoco pasen al cliente.
    """
    async with factory() as session:
        repo = ExamenContenidoSqlRepository(session)
        await repo.guardar(_examen_con_preguntas("Examen Shape Test", 2))
        await session.commit()

    resp = await client_student.get("/api/v1/exam-content/")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    for item in data:
        assert "id" in item
        assert "titulo" in item
        assert "cantidad_preguntas" in item
        # D3: campos prohibidos
        assert "es_correcta" not in item, "es_correcta NO debe estar en el catálogo"
        assert "preguntas" not in item, "preguntas NO debe estar en el catálogo"
        assert "opciones" not in item, "opciones NO debe estar en el catálogo"


@pytest.mark.asyncio
async def test_listar_orden_alfabetico(client_student, factory):
    """GET /api/v1/exam-content/ devuelve exámenes ordenados alfabéticamente por titulo."""
    async with factory() as session:
        repo = ExamenContenidoSqlRepository(session)
        await repo.guardar(_examen_con_preguntas("Zoología Aplicada", 1))
        await repo.guardar(_examen_con_preguntas("Análisis de Sistemas", 2))
        await repo.guardar(_examen_con_preguntas("Matemáticas Discretas", 1))
        await session.commit()

    resp = await client_student.get("/api/v1/exam-content/")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    titulos = [item["titulo"] for item in data]
    assert "Zoología Aplicada" in titulos
    assert "Análisis de Sistemas" in titulos
    assert "Matemáticas Discretas" in titulos

    idx_analisis = titulos.index("Análisis de Sistemas")
    idx_mate = titulos.index("Matemáticas Discretas")
    idx_zoo = titulos.index("Zoología Aplicada")
    assert idx_analisis < idx_mate < idx_zoo, (
        f"Orden incorrecto: Análisis={idx_analisis}, Mate={idx_mate}, Zoo={idx_zoo}"
    )


@pytest.mark.asyncio
async def test_listar_dos_requests_orden_idempotente(client_student):
    """Dos requests al listado devuelven el mismo orden (idempotencia)."""
    r1 = await client_student.get("/api/v1/exam-content/")
    r2 = await client_student.get("/api/v1/exam-content/")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json() == r2.json(), "El listado debe ser determinístico entre requests"
