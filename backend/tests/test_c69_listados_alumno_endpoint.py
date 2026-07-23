"""RED → GREEN → TRIANGULATE: endpoints de listado del alumno/admin (C-69, datos reales).

Endpoints (cualquier principal autenticado — sin admin, sin MFA):
- GET /api/v1/exam-content/materias
- GET /api/v1/exam-content/materias/{materia_id}/comisiones
- GET /api/v1/exam-content/comisiones/{comision_id}/examenes
- GET /api/v1/exam-content (enriquecido con comision_id/comision_nombre/materia_nombre)

Rutas sin trailing slash (evita el 307 preexistente del catálogo). Requieren DATABASE_URL.
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
    Comision,
    ExamenContenido,
    Materia,
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
# El gate de inscripción (C-71) que aplica el listado consulta inscripcion+usuario:
# sin esas tablas el endpoint revienta con UndefinedTable.
from app.infrastructure.persistence.models.inscripcion import (  # noqa: F401
    InscripcionModel,
)
from app.infrastructure.persistence.models.transactional import (  # noqa: F401
    UsuarioModel,
)
from app.infrastructure.persistence.repositories.exam_content import (
    ComisionSqlRepository,
    ExamenContenidoSqlRepository,
    MateriaSqlRepository,
)
from app.presentation.api.v1.exam_content.router import create_exam_taking_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_NEW_TABLES = (
    "inscripcion",
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "comision",
    "materia",
    "usuario",
)


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
                UsuarioModel.__table__,
                MateriaModel.__table__,
                ComisionModel.__table__,
                ExamenContenidoModel.__table__,
                PreguntaExamenModel.__table__,
                OpcionRespuestaModel.__table__,
                InscripcionModel.__table__,
            ],
        )
    yield eng
    async with eng.begin() as conn:
        for name in _NEW_TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def app_student(db_engine):
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
async def client_staff(app_student):
    """Cliente con rol de gestión: ve TODO el catálogo, sin gate de inscripción.

    Necesario para verificar la FORMA del resumen sobre un examen SIN comisión:
    el gate de C-71 se lo oculta al alumno por diseño (un examen sin comisión no
    pertenece a ninguna de sus comisiones inscriptas).
    """
    app, _ = app_student
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["admin_examenes"]),
    ) as c:
        yield c


@pytest_asyncio.fixture
async def factory(app_student):
    _, fac = app_student
    return fac


@pytest_asyncio.fixture
async def app_noauth():
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


def _examen(titulo: str, comision_id: str | None, n: int = 2) -> ExamenContenido:
    return ExamenContenido(
        titulo=titulo,
        comision_id=comision_id,
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
    )


async def _seed(factory):
    """Crea materia → comisión → examen asociado + un examen suelto. Devuelve ids.

    Usa códigos únicos por invocación: el engine es module-scoped y los commits
    de un test persisten para los siguientes (no hay rollback entre funciones).
    """
    import uuid

    tag = uuid.uuid4().hex[:8]
    async with factory() as session:
        materia_repo = MateriaSqlRepository(session)
        comision_repo = ComisionSqlRepository(session)
        examen_repo = ExamenContenidoSqlRepository(session)
        materia = await materia_repo.guardar(
            Materia(codigo=f"AM-{tag}", nombre="Análisis Matemático")
        )
        comision = await comision_repo.guardar(
            Comision(codigo=f"1A-{tag}", nombre="Comisión 1A", materia_id=materia.id,
                     periodo="1C", anio=2026, codigo_matriculacion=f"AM-{tag}-1A")
        )
        examen = await examen_repo.guardar(_examen(f"Parcial 1 [{tag}]", comision.id, n=3))
        await examen_repo.guardar(_examen(f"Examen Suelto [{tag}]", None, n=1))
        # Gate de inscripción (C-71): el alumno ve SOLO lo de sus comisiones
        # inscriptas. El token de test lleva id_institucional='estudiante', así que
        # hay que materializar ese usuario e inscribirlo — si no, estos listados
        # vuelven vacíos (comportamiento correcto del gate, no un bug).
        alumno_id = await session.scalar(
            text(
                "INSERT INTO usuario (id_institucional, email, roles) "
                "VALUES ('estudiante', 'estudiante@uni.edu', '[\"estudiante\"]'::jsonb) "
                "ON CONFLICT (id_institucional) DO UPDATE SET email = EXCLUDED.email "
                "RETURNING id"
            )
        )
        await session.execute(
            text(
                "INSERT INTO inscripcion (usuario_id, comision_id) "
                "VALUES (:u, :c) ON CONFLICT DO NOTHING"
            ),
            {"u": alumno_id, "c": comision.id},
        )
        await session.commit()
    return {
        "materia_id": materia.id,
        "comision_id": comision.id,
        "examen_id": examen.id,
        "materia_codigo": f"AM-{tag}",
        "titulo_parcial": f"Parcial 1 [{tag}]",
        "titulo_suelto": f"Examen Suelto [{tag}]",
    }


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_materias_sin_auth_devuelve_401(client_noauth):
    resp = await client_noauth.get("/api/v1/exam-content/materias")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /materias
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_materias_lista(client_student, factory):
    ids = await _seed(factory)
    resp = await client_student.get("/api/v1/exam-content/materias")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    item = next(m for m in data if m["id"] == ids["materia_id"])
    assert item["codigo"] == ids["materia_codigo"]
    assert item["nombre"] == "Análisis Matemático"
    # `activa` (C-72 §17): estado de la materia — se agregó al schema después.
    assert set(item.keys()) == {"id", "codigo", "nombre", "activa"}


# ---------------------------------------------------------------------------
# GET /materias/{id}/comisiones
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_comisiones_de_materia(client_student, factory):
    ids = await _seed(factory)
    resp = await client_student.get(
        f"/api/v1/exam-content/materias/{ids['materia_id']}/comisiones"
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    item = next(c for c in data if c["id"] == ids["comision_id"])
    assert item["materia_id"] == ids["materia_id"]
    assert item["nombre"] == "Comisión 1A"
    assert item["periodo"] == "1C"
    assert item["anio"] == 2026


@pytest.mark.asyncio
async def test_comisiones_de_materia_inexistente_vacio(client_student):
    resp = await client_student.get(
        "/api/v1/exam-content/materias/00000000-0000-0000-0000-000000000000/comisiones"
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /comisiones/{id}/examenes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_examenes_de_comision(client_student, factory):
    ids = await _seed(factory)
    resp = await client_student.get(
        f"/api/v1/exam-content/comisiones/{ids['comision_id']}/examenes"
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 1
    item = data[0]
    assert item["id"] == ids["examen_id"]
    assert item["titulo"] == ids["titulo_parcial"]
    assert item["cantidad_preguntas"] == 3
    # D3: no se filtra la opción correcta
    assert "es_correcta" not in item
    assert "preguntas" not in item


# ---------------------------------------------------------------------------
# GET "" enriquecido con comisión + materia
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listado_examenes_incluye_materia_y_comision(client_staff, factory):
    """El resumen del catálogo trae comision/materia derivadas (D11), y las deja en
    None cuando el examen no tiene comisión.

    Va con cliente STAFF a propósito: el examen suelto (sin comisión) no le es
    visible al alumno por el gate de inscripción (C-71) — eso se cubre aparte."""
    ids = await _seed(factory)
    resp = await client_staff.get("/api/v1/exam-content")
    assert resp.status_code == 200, resp.text
    # Contrato paginado (C-69 admin-sync, tarea 4): { items, total, page, page_size }
    data = resp.json()["items"]

    con_com = next(x for x in data if x["id"] == ids["examen_id"])
    assert con_com["comision_id"] == ids["comision_id"]
    assert con_com["comision_nombre"] == "Comisión 1A"
    assert con_com["materia_nombre"] == "Análisis Matemático"

    suelto = next(x for x in data if x["titulo"] == ids["titulo_suelto"])
    assert suelto["comision_id"] is None
    assert suelto["comision_nombre"] is None
    assert suelto["materia_nombre"] is None
    # D3 invariante
    assert "es_correcta" not in suelto
