"""El contador de preguntas de un examen SORTEADO no puede dar 0.

`cantidad_preguntas` contaba solo las filas con ``seleccionada=true``. En un examen
con ``modo_preguntas='sorteo_por_intento'`` ninguna lo está — el sorteo se resuelve
cuando entra cada alumno — así que el encabezado del detalle y la columna del
listado mostraban **0** para un examen correctamente configurado. Un profesor que
armó "10 de 30" veía 0 y creía que el examen había quedado vacío.

Lo que el docente necesita ver es el largo REAL del examen: cuántas preguntas rinde
cada alumno, o sea la suma de las cantidades de los tramos del sorteo.

DB real (regla dura #4: nada de mockear la base).
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

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    BlankBancoModel,
    CategoriaPreguntaModel,
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionBancoModel,
    OpcionBlankBancoModel,
    OpcionRespuestaModel,
    PreguntaBancoModel,
    PreguntaClozeBlankModel,
    PreguntaExamenModel,
    PreguntaSesionModel,
    TramoSorteoExamenModel,
)
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
from app.presentation.api.v1.exam_content.router import (
    create_exam_content_router,
    create_exam_taking_router,
)
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_TABLES = [
    "pregunta_sesion",
    "tramo_sorteo_examen",
    "proctoring_session",
    "opcion_blank_banco",
    "blank_banco",
    "opcion_banco",
    "opcion_cloze_blank",
    "pregunta_cloze_blank",
    "opcion_respuesta",
    "pregunta_examen",
    "pregunta_banco",
    "examen_contenido",
    "categoria_pregunta",
    "comision",
    "materia",
]


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
        for name in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                MateriaModel.__table__,
                ComisionModel.__table__,
                CategoriaPreguntaModel.__table__,
                ExamenContenidoModel.__table__,
                PreguntaBancoModel.__table__,
                PreguntaExamenModel.__table__,
                OpcionRespuestaModel.__table__,
                OpcionBancoModel.__table__,
                BlankBancoModel.__table__,
                OpcionBlankBancoModel.__table__,
                PreguntaClozeBlankModel.__table__,
                ProctoringSessionModel.__table__,
                TramoSorteoExamenModel.__table__,
                PreguntaSesionModel.__table__,
            ],
        )
    yield eng
    async with eng.begin() as conn:
        for name in _TABLES:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def app_admin(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    app.include_router(
        create_exam_content_router(session_factory=factory), prefix="/api/v1/exam-content"
    )
    # El encabezado del detalle (`/{id}/resumen`) vive en el router de rendición.
    app.include_router(
        create_exam_taking_router(session_factory=factory), prefix="/api/v1/exam-content"
    )
    return app


@pytest_asyncio.fixture
async def client_admin(app_admin):
    async with AsyncClient(
        transport=ASGITransport(app=app_admin),
        base_url="http://test",
        headers=auth_headers(["admin_sistema"], mfa=True),
    ) as c:
        yield c


@pytest_asyncio.fixture
async def session(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
        await s.rollback()


async def _materia_con_banco(
    session: AsyncSession, *, preguntas: int
) -> tuple[str, str, str]:
    mid = str(uuid.uuid4())
    sufijo = mid[:8]
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, 'M')"),
        {"id": mid, "c": f"CNT-{sufijo}"},
    )
    cid = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO comision (id, materia_id, codigo, nombre, codigo_matriculacion)"
            " VALUES (:id, :mid, 'C1', 'C1', :km)"
        ),
        {"id": cid, "mid": mid, "km": f"CNT-{sufijo}-C1"},
    )
    cat_id = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO categoria_pregunta (id, materia_id, nombre)"
            " VALUES (:id, :mid, 'Unidad 1')"
        ),
        {"id": cat_id, "mid": mid},
    )
    for i in range(preguntas):
        await session.execute(
            text(
                "INSERT INTO pregunta_banco (id, materia_id, enunciado, tipo, categoria_id)"
                " VALUES (:id, :mid, :e, 'multichoice', :cid)"
            ),
            {"id": str(uuid.uuid4()), "mid": mid, "e": f"P{i}", "cid": cat_id},
        )
    await session.commit()
    return mid, cid, cat_id


async def _crear_sorteado(
    client: AsyncClient, materia_id: str, comision_id: str, cat_id: str, cantidad: int
) -> str:
    resp = await client.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial sorteado",
            "materia_id": materia_id,
            "comision_id": comision_id,
            "sorteo": [{"categoria_id": cat_id, "cantidad": cantidad}],
            "sorteo_por_intento": True,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["examen_id"]


@pytest.mark.asyncio
async def test_resumen_de_examen_sorteado_cuenta_el_largo_no_las_seleccionadas(
    client_admin: AsyncClient, session: AsyncSession
):
    """El encabezado muestra 10, que es lo que rinde el alumno, no 0."""
    materia_id, comision_id, cat_id = await _materia_con_banco(session, preguntas=30)
    examen_id = await _crear_sorteado(client_admin, materia_id, comision_id, cat_id, 10)

    resp = await client_admin.get(f"/api/v1/exam-content/{examen_id}/resumen")
    assert resp.status_code == 200, resp.text
    assert resp.json()["cantidad_preguntas"] == 10


@pytest.mark.asyncio
async def test_listado_de_examenes_tambien_muestra_el_largo_del_sorteo(
    client_admin: AsyncClient, session: AsyncSession
):
    """Triangulación con otro largo y por el listado, que es otra query."""
    materia_id, comision_id, cat_id = await _materia_con_banco(session, preguntas=30)
    examen_id = await _crear_sorteado(client_admin, materia_id, comision_id, cat_id, 7)

    resp = await client_admin.get("/api/v1/exam-content/")
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    fila = next(x for x in items if x["id"] == examen_id)
    assert fila["cantidad_preguntas"] == 7


@pytest.mark.asyncio
async def test_sorteo_con_varios_tramos_suma_las_cantidades(
    client_admin: AsyncClient, session: AsyncSession
):
    """Triangulación: con dos tramos el largo es la suma, no el de uno solo."""
    materia_id, comision_id, cat_id = await _materia_con_banco(session, preguntas=30)
    otra_cat = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO categoria_pregunta (id, materia_id, nombre)"
            " VALUES (:id, :mid, 'Unidad 2')"
        ),
        {"id": otra_cat, "mid": materia_id},
    )
    for i in range(10):
        await session.execute(
            text(
                "INSERT INTO pregunta_banco (id, materia_id, enunciado, tipo, categoria_id)"
                " VALUES (:id, :mid, :e, 'multichoice', :cid)"
            ),
            {"id": str(uuid.uuid4()), "mid": materia_id, "e": f"U2-{i}", "cid": otra_cat},
        )
    await session.commit()

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial dos tramos",
            "materia_id": materia_id,
            "comision_id": comision_id,
            "sorteo": [
                {"categoria_id": cat_id, "cantidad": 6},
                {"categoria_id": otra_cat, "cantidad": 4},
            ],
            "sorteo_por_intento": True,
        },
    )
    assert resp.status_code == 201, resp.text
    examen_id = resp.json()["examen_id"]

    resumen = await client_admin.get(f"/api/v1/exam-content/{examen_id}/resumen")
    assert resumen.json()["cantidad_preguntas"] == 10


@pytest.mark.asyncio
async def test_examen_fijo_sigue_contando_las_seleccionadas(
    client_admin: AsyncClient, session: AsyncSession
):
    """El modo fijo NO cambia: cuenta las preguntas marcadas, como siempre."""
    materia_id, comision_id, cat_id = await _materia_con_banco(session, preguntas=30)
    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial fijo",
            "materia_id": materia_id,
            "comision_id": comision_id,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 5}],
            "sorteo_por_intento": False,
        },
    )
    assert resp.status_code == 201, resp.text
    examen_id = resp.json()["examen_id"]

    resumen = await client_admin.get(f"/api/v1/exam-content/{examen_id}/resumen")
    assert resumen.json()["cantidad_preguntas"] == 5
