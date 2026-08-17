"""6.5 RED → 6.6 GREEN: servicio/endpoint admin de asociación examen↔comisión (C-69, D11).

Endpoints (admin-only, SIN MFA — mismo guard que el import):
- POST /api/v1/exam-content/materias-comisiones      → alta inline de materia+comisión
  (opcionalmente asocia un examen ya importado).
- POST /api/v1/exam-content/{examen_id}/comision     → asocia un examen existente a
  una comisión existente.

Reglas verificadas:
- Admin → 201/200; no-admin (estudiante) → 403.
- Alta inline crea materia+comisión y devuelve sus ids.
- Asociar un examen ya importado a una comisión existente lo liga (sin reimportar).
- Un examen que NO se asocia sigue siendo válido y rendible (GET taking).
- Examen/comisión inexistente → 404.
- Schemas extra='forbid' → campo desconocido = 422.

Requieren DATABASE_URL para los tests funcionales; los tests de 403 no necesitan DB.
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

from app.domain.exam_content.entities import (
    ExamenContenido,
    OpcionRespuesta,
    Pregunta,
)
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
from app.presentation.api.v1.exam_content.router import (
    create_exam_content_router,
    create_exam_taking_router,
)
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_NEW_TABLES = (
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "comision",
    "materia",
)
_FK_EXAMEN_COMISION = "fk_examen_contenido_comision"


# ---------------------------------------------------------------------------
# Fixtures sin DB (tests de auth 403)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client_noauth():
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    app.include_router(
        create_exam_content_router(session_factory=None), prefix="/api/v1/exam-content"
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Fixtures con DB
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
        await conn.execute(
            text(
                f'ALTER TABLE examen_contenido ADD CONSTRAINT "{_FK_EXAMEN_COMISION}" '
                "FOREIGN KEY (comision_id) REFERENCES comision(id) ON DELETE SET NULL"
            )
        )
    yield eng
    async with eng.begin() as conn:
        for name in _NEW_TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def app_admin(factory):
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    app.include_router(
        create_exam_content_router(session_factory=factory), prefix="/api/v1/exam-content"
    )
    app.include_router(
        create_exam_taking_router(session_factory=factory), prefix="/api/v1/exam-content"
    )
    return app


@pytest_asyncio.fixture
async def client_admin(app_admin):
    async with AsyncClient(
        transport=ASGITransport(app=app_admin),
        base_url="http://test",
        headers=auth_headers(["admin_sistema"], mfa=False),
    ) as c:
        yield c


async def _crear_examen_sin_comision(factory) -> str:
    examen = ExamenContenido(
        titulo="Parcial sin comisión",
        comision_id=None,
        preguntas=(
            Pregunta(
                enunciado="¿2+2?",
                tipo="multichoice",
                opciones=(
                    OpcionRespuesta(texto="4", es_correcta=True, orden=0),
                    OpcionRespuesta(texto="5", es_correcta=False, orden=1),
                ),
            ),
        ),
    )
    async with factory() as s:
        repo = ExamenContenidoSqlRepository(s)
        guardado = await repo.guardar(examen)
        await s.commit()
        return guardado.id


# ---------------------------------------------------------------------------
# 6.5 RED — auth (sin DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_alta_inline_estudiante_403(client_noauth):
    resp = await client_noauth.post(
        "/api/v1/exam-content/materias-comisiones",
        json={
            "materia": {"codigo": "M1", "nombre": "Mat"},
            "comision": {"codigo": "C1", "nombre": "Com"},
        },
        headers=auth_headers(["estudiante"]),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_asociar_estudiante_403(client_noauth):
    resp = await client_noauth.post(
        "/api/v1/exam-content/some-id/comision",
        json={"comision_id": "x"},
        headers=auth_headers(["estudiante"]),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 6.6 GREEN — funcionales (DB real)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_alta_inline_admin_201(client_admin):
    resp = await client_admin.post(
        "/api/v1/exam-content/materias-comisiones",
        json={
            "materia": {"codigo": "ALG-101", "nombre": "Álgebra"},
            "comision": {"codigo": "C-A", "nombre": "Comisión A", "periodo": "1C", "anio": 2026},
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["materia"]["id"]
    assert data["materia"]["codigo"] == "ALG-101"
    assert data["comision"]["id"]
    assert data["comision"]["materia_id"] == data["materia"]["id"]
    assert data["comision"]["anio"] == 2026
    assert data["examen_id"] is None


@pytest.mark.asyncio
async def test_alta_inline_y_asociar_examen(client_admin, factory):
    examen_id = await _crear_examen_sin_comision(factory)
    resp = await client_admin.post(
        "/api/v1/exam-content/materias-comisiones",
        json={
            "materia": {"codigo": "FIS-201", "nombre": "Física"},
            "comision": {"codigo": "C-F", "nombre": "Comisión F"},
            "examen_id": examen_id,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["examen_id"] == examen_id

    # El examen quedó ligado a la comisión creada.
    async with factory() as s:
        repo = ExamenContenidoSqlRepository(s)
        examen = await repo.obtener(examen_id)
    assert examen is not None
    assert examen.comision_id == data["comision"]["id"]


@pytest.mark.asyncio
async def test_asociar_examen_existente_a_comision_200(client_admin, factory):
    examen_id = await _crear_examen_sin_comision(factory)
    # Crear una comisión vía alta inline.
    alta = await client_admin.post(
        "/api/v1/exam-content/materias-comisiones",
        json={
            "materia": {"codigo": "QUI-301", "nombre": "Química"},
            "comision": {"codigo": "C-Q", "nombre": "Comisión Q"},
        },
    )
    comision_id = alta.json()["comision"]["id"]

    resp = await client_admin.post(
        f"/api/v1/exam-content/{examen_id}/comision",
        json={"comision_id": comision_id},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["examen_id"] == examen_id
    assert data["comision_id"] == comision_id


@pytest.mark.asyncio
async def test_examen_sin_asociar_sigue_rendible(client_admin, factory):
    """D11: un examen que NO se asocia sigue siendo válido y rendible."""
    examen_id = await _crear_examen_sin_comision(factory)
    resp = await client_admin.get(f"/api/v1/exam-content/{examen_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == examen_id
    assert len(data["preguntas"]) == 1
    # D3: ninguna opción expone es_correcta.
    for p in data["preguntas"]:
        for o in p["opciones"]:
            assert "es_correcta" not in o


@pytest.mark.asyncio
async def test_asociar_examen_inexistente_404(client_admin, factory):
    alta = await client_admin.post(
        "/api/v1/exam-content/materias-comisiones",
        json={
            "materia": {"codigo": "INX-1", "nombre": "M"},
            "comision": {"codigo": "C-INX", "nombre": "C"},
        },
    )
    comision_id = alta.json()["comision"]["id"]
    resp = await client_admin.post(
        "/api/v1/exam-content/00000000-0000-0000-0000-000000000000/comision",
        json={"comision_id": comision_id},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_asociar_comision_inexistente_404(client_admin, factory):
    examen_id = await _crear_examen_sin_comision(factory)
    resp = await client_admin.post(
        f"/api/v1/exam-content/{examen_id}/comision",
        json={"comision_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_alta_inline_extra_forbid_422(client_admin):
    resp = await client_admin.post(
        "/api/v1/exam-content/materias-comisiones",
        json={
            "materia": {"codigo": "X", "nombre": "X", "desconocido": 1},
            "comision": {"codigo": "C", "nombre": "C"},
        },
    )
    assert resp.status_code == 422
