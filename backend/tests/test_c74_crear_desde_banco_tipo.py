"""C-74: filtro por tipo de pregunta en `POST /exam-content/crear-desde-banco`.

El sorteo por categoría ya funcionaba (D4/task 3), pero no discriminaba tipo
de pregunta dentro de la categoría — si una categoría mezclaba multichoice y
cloze, el sorteo podía traer cualquiera de los dos sin que el docente pudiera
pedir "solo multichoice" o "solo cloze". `SorteoCategoriaItem.tipos` (None =
cualquier tipo) cierra ese gap.

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
)
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_TABLES = [
    "opcion_blank_banco",
    "blank_banco",
    "opcion_banco",
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
    router = create_exam_content_router(session_factory=factory)
    app.include_router(router, prefix="/api/v1/exam-content")
    return app


@pytest_asyncio.fixture
async def client_admin(app_admin):
    async with AsyncClient(
        transport=ASGITransport(app=app_admin),
        base_url="http://test",
        headers=auth_headers(["admin_examenes"], mfa=True),
    ) as c:
        yield c


@pytest_asyncio.fixture
async def session(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
        await s.rollback()


async def _materia_con_categoria_mixta(session: AsyncSession) -> tuple[str, str]:
    """Materia con 1 categoría que tiene 3 multichoice + 2 truefalse.

    Devuelve (materia_id, categoria_id).
    """
    mid = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, :n)"),
        {"id": mid, "c": f"TIPO-{mid[:8]}", "n": "Materia Tipo"},
    )
    cat_id = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO categoria_pregunta (id, materia_id, nombre) VALUES (:id, :mid, :n)"
        ),
        {"id": cat_id, "mid": mid, "n": "Unidad Mixta"},
    )

    for i in range(3):
        await session.execute(
            text(
                "INSERT INTO pregunta_banco (id, materia_id, enunciado, tipo, categoria_id)"
                " VALUES (:id, :mid, :e, 'multichoice', :cid)"
            ),
            {"id": str(uuid.uuid4()), "mid": mid, "e": f"MC-{i}", "cid": cat_id},
        )
    for i in range(2):
        await session.execute(
            text(
                "INSERT INTO pregunta_banco (id, materia_id, enunciado, tipo, categoria_id)"
                " VALUES (:id, :mid, :e, 'truefalse', :cid)"
            ),
            {"id": str(uuid.uuid4()), "mid": mid, "e": f"TF-{i}", "cid": cat_id},
        )

    await session.commit()
    return mid, cat_id


@pytest.mark.asyncio
async def test_crear_desde_banco_filtra_por_tipo_multichoice(
    client_admin: AsyncClient, session: AsyncSession
):
    """RED→GREEN: pedir 2 multichoice de una categoría mixta trae solo multichoice."""
    materia_id, cat_id = await _materia_con_categoria_mixta(session)

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial solo multichoice",
            "materia_id": materia_id,
            "sorteo": [
                {"categoria_id": cat_id, "cantidad": 2, "tipos": ["multichoice"]}
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    examen_id = resp.json()["examen_id"]
    assert resp.json()["total_preguntas"] == 2

    tipos = await session.execute(
        text("SELECT tipo FROM pregunta_examen WHERE examen_id = :eid"),
        {"eid": examen_id},
    )
    assert {r[0] for r in tipos.fetchall()} == {"multichoice"}


@pytest.mark.asyncio
async def test_crear_desde_banco_filtra_por_tipo_truefalse(
    client_admin: AsyncClient, session: AsyncSession
):
    """TRIANGULATE: mismo tramo, distinto tipo → confirma que el filtro no está hardcodeado."""
    materia_id, cat_id = await _materia_con_categoria_mixta(session)

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial solo truefalse",
            "materia_id": materia_id,
            "sorteo": [
                {"categoria_id": cat_id, "cantidad": 2, "tipos": ["truefalse"]}
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    examen_id = resp.json()["examen_id"]

    tipos = await session.execute(
        text("SELECT tipo FROM pregunta_examen WHERE examen_id = :eid"),
        {"eid": examen_id},
    )
    assert {r[0] for r in tipos.fetchall()} == {"truefalse"}


@pytest.mark.asyncio
async def test_crear_desde_banco_sin_tipos_sortea_de_todos(
    client_admin: AsyncClient, session: AsyncSession
):
    """Control: sin `tipos` (compat hacia atrás), el sorteo sigue mezclando tipos."""
    materia_id, cat_id = await _materia_con_categoria_mixta(session)

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial mixto",
            "materia_id": materia_id,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 5}],
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["total_preguntas"] == 5


@pytest.mark.asyncio
async def test_crear_desde_banco_default_escala_100_60(
    client_admin: AsyncClient, session: AsyncSession
):
    """RED→GREEN: sin nota_maxima/nota_aprobacion en el body, el examen queda en
    100/60 — nunca en el viejo default 'sobre 10' de la columna."""
    materia_id, cat_id = await _materia_con_categoria_mixta(session)

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial escala default",
            "materia_id": materia_id,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 2, "tipos": ["multichoice"]}],
        },
    )
    assert resp.status_code == 201, resp.text
    examen_id = resp.json()["examen_id"]

    row = await session.execute(
        text("SELECT nota_maxima, nota_aprobacion FROM examen_contenido WHERE id = :eid"),
        {"eid": examen_id},
    )
    nota_maxima, nota_aprobacion = row.fetchone()
    assert float(nota_maxima) == 100.0
    assert float(nota_aprobacion) == 60.0


@pytest.mark.asyncio
async def test_crear_desde_banco_escala_personalizada(
    client_admin: AsyncClient, session: AsyncSession
):
    """TRIANGULATE: el docente puede pedir otra escala (ej. sobre 10) al crear."""
    materia_id, cat_id = await _materia_con_categoria_mixta(session)

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial escala 10",
            "materia_id": materia_id,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 2, "tipos": ["multichoice"]}],
            "nota_maxima": 10,
            "nota_aprobacion": 6,
        },
    )
    assert resp.status_code == 201, resp.text
    examen_id = resp.json()["examen_id"]

    row = await session.execute(
        text("SELECT nota_maxima, nota_aprobacion FROM examen_contenido WHERE id = :eid"),
        {"eid": examen_id},
    )
    nota_maxima, nota_aprobacion = row.fetchone()
    assert float(nota_maxima) == 10.0
    assert float(nota_aprobacion) == 6.0


@pytest.mark.asyncio
async def test_crear_desde_banco_nota_aprobacion_mayor_a_maxima_422(
    client_admin: AsyncClient, session: AsyncSession
):
    """TRIANGULATE: nota_aprobacion > nota_maxima es inválido, se rechaza ANTES de crear nada."""
    materia_id, cat_id = await _materia_con_categoria_mixta(session)

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial inválido",
            "materia_id": materia_id,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 2, "tipos": ["multichoice"]}],
            "nota_maxima": 10,
            "nota_aprobacion": 15,
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "config_invalida"

    total = await session.execute(
        text("SELECT COUNT(*) FROM examen_contenido WHERE titulo = 'Parcial inválido'")
    )
    assert total.scalar_one() == 0


@pytest.mark.asyncio
async def test_crear_desde_banco_tipo_insuficiente_422(
    client_admin: AsyncClient, session: AsyncSession
):
    """Pedir más truefalse de las que hay (2 disponibles, se piden 5) → 422."""
    materia_id, cat_id = await _materia_con_categoria_mixta(session)

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial imposible",
            "materia_id": materia_id,
            "sorteo": [
                {"categoria_id": cat_id, "cantidad": 5, "tipos": ["truefalse"]}
            ],
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "sorteo_insuficiente"
