"""Elegir DE DÓNDE puede salir el sorteo, y pedir un total contra eso.

Repartir cuotas por categoría tiene un problema que no se ve hasta que pasa: una
subcategoría con 1 pregunta y cuota 1 no sortea nada, esa pregunta la reciben
todos. Filtrar el pool lo evita: se marca de qué categorías puede salir, se
destildan las preguntas que no van, y se pide UN total contra el conjunto. Con 9
preguntas en tres subcategorías y un total de 6, salen 6 de las 9 al azar y
puede no tocar ninguna de una subcategoría.

`pool_preguntas` es la lista explícita de preguntas del banco que se copian al
examen. El tramo pasa a ser uno solo ("todo el pool, N preguntas").

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
from app.presentation.api.v1.exam_content.router import create_exam_content_router
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


async def _banco_en_tres_unidades(session: AsyncSession) -> tuple[str, dict[str, list[str]]]:
    """Materia con tres subcategorías de 3 preguntas cada una.

    Es el caso que planteó el dueño: 3 + 3 + 3 y un total de 6.
    """
    mid = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, 'M')"),
        {"id": mid, "c": f"POOL-{mid[:8]}"},
    )
    padre = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO categoria_pregunta (id, materia_id, nombre)"
            " VALUES (:id, :mid, 'Parcial')"
        ),
        {"id": padre, "mid": mid},
    )
    por_unidad: dict[str, list[str]] = {}
    for u in ("U1", "U2", "U3"):
        cid = str(uuid.uuid4())
        await session.execute(
            text(
                "INSERT INTO categoria_pregunta (id, materia_id, nombre, categoria_padre_id)"
                " VALUES (:id, :mid, :n, :p)"
            ),
            {"id": cid, "mid": mid, "n": u, "p": padre},
        )
        ids = []
        for i in range(3):
            pid = str(uuid.uuid4())
            await session.execute(
                text(
                    "INSERT INTO pregunta_banco"
                    " (id, materia_id, enunciado, tipo, categoria_id)"
                    " VALUES (:id, :mid, :e, 'multichoice', :cid)"
                ),
                {"id": pid, "mid": mid, "e": f"{u}-{i}", "cid": cid},
            )
            ids.append(pid)
        por_unidad[u] = ids
    await session.commit()
    return mid, por_unidad


@pytest.mark.asyncio
async def test_el_pool_del_examen_son_las_preguntas_elegidas(
    client_admin: AsyncClient, session: AsyncSession
):
    """9 preguntas en el banco, se eligen 6: el examen se lleva esas 6."""
    materia_id, por_unidad = await _banco_en_tres_unidades(session)
    elegidas = por_unidad["U1"] + por_unidad["U2"]

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Sorteo sobre pool elegido",
            "materia_id": materia_id,
            "pool_preguntas": elegidas,
            "sorteo": [{"categoria_id": None, "incluir_subcategorias": True, "cantidad": 4}],
            "sorteo_por_intento": True,
        },
    )
    assert resp.status_code == 201, resp.text
    examen_id = resp.json()["examen_id"]

    copiadas = await session.execute(
        text(
            "SELECT pregunta_banco_id::text FROM pregunta_examen WHERE examen_id = :eid"
        ),
        {"eid": examen_id},
    )
    assert sorted(r[0] for r in copiadas.all()) == sorted(elegidas)


@pytest.mark.asyncio
async def test_una_pregunta_destildada_no_le_puede_tocar_a_nadie(
    client_admin: AsyncClient, session: AsyncSession
):
    """Sacar una del desglose la deja afuera del examen, no solo del sorteo."""
    materia_id, por_unidad = await _banco_en_tres_unidades(session)
    todas = por_unidad["U1"] + por_unidad["U2"] + por_unidad["U3"]
    afuera = todas[0]
    elegidas = todas[1:]

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Con una pregunta afuera",
            "materia_id": materia_id,
            "pool_preguntas": elegidas,
            "sorteo": [{"categoria_id": None, "incluir_subcategorias": True, "cantidad": 5}],
            "sorteo_por_intento": True,
        },
    )
    assert resp.status_code == 201, resp.text

    copiadas = await session.execute(
        text(
            "SELECT COUNT(*) FROM pregunta_examen"
            " WHERE examen_id = :eid AND pregunta_banco_id = :pid"
        ),
        {"eid": resp.json()["examen_id"], "pid": afuera},
    )
    assert copiadas.scalar_one() == 0


@pytest.mark.asyncio
async def test_pedir_mas_de_lo_que_hay_en_el_pool_no_crea_nada(
    client_admin: AsyncClient, session: AsyncSession
):
    """El tope es el pool elegido, no el banco entero.

    Con 9 en el banco pero 6 elegidas, pedir 7 tiene que fallar: si respondiera
    201 el examen quedaría pidiendo preguntas que no tiene y reventaría recién
    cuando el primer alumno entrara a rendir.
    """
    materia_id, por_unidad = await _banco_en_tres_unidades(session)
    elegidas = por_unidad["U1"] + por_unidad["U2"]

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Pide de más",
            "materia_id": materia_id,
            "pool_preguntas": elegidas,
            "sorteo": [{"categoria_id": None, "incluir_subcategorias": True, "cantidad": 7}],
            "sorteo_por_intento": True,
        },
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["error"] == "sorteo_insuficiente"

    quedaron = await session.execute(
        text("SELECT COUNT(*) FROM examen_contenido WHERE titulo = 'Pide de más'")
    )
    assert quedaron.scalar_one() == 0


@pytest.mark.asyncio
async def test_una_pregunta_de_otra_materia_no_entra_por_id(
    client_admin: AsyncClient, session: AsyncSession
):
    """El pool viaja como ids: mandar uno ajeno no puede meter esa pregunta."""
    materia_id, por_unidad = await _banco_en_tres_unidades(session)
    otra_materia, otras = await _banco_en_tres_unidades(session)

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Con una intrusa",
            "materia_id": materia_id,
            "pool_preguntas": por_unidad["U1"] + [otras["U1"][0]],
            "sorteo": [{"categoria_id": None, "incluir_subcategorias": True, "cantidad": 2}],
            "sorteo_por_intento": True,
        },
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["error"] == "pool_invalido"
