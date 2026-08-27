"""Baja LÓGICA de una categoría del banco (antes era borrado físico en cascada).

`DELETE /categorias/{id}` hacía un DELETE real. Por el ON DELETE CASCADE del
`categoria_padre_id` se llevaba puestas TODAS sus subcategorías, y por el
SET NULL de `pregunta_banco.categoria_id` dejaba sus preguntas en "Sin
clasificar". Con un banco de 30 preguntas organizadas en varias unidades, un
click borraba la organización entera y no había forma de deshacerlo.

Ahora la categoría y su rama salen del árbol pero se pueden recuperar, y las
preguntas conservan a qué categoría pertenecían.

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
async def client(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    app.include_router(
        create_exam_content_router(session_factory=factory), prefix="/api/v1/exam-content"
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
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


async def _materia_con_arbol(session: AsyncSession) -> tuple[str, str, str, str]:
    """Materia con: Unidad 1 → Bloque A, y una pregunta en cada una."""
    mid = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, 'M')"),
        {"id": mid, "c": f"CAT-{mid[:8]}"},
    )
    padre = str(uuid.uuid4())
    hija = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO categoria_pregunta (id, materia_id, nombre)"
            " VALUES (:id, :mid, 'Unidad 1')"
        ),
        {"id": padre, "mid": mid},
    )
    await session.execute(
        text(
            "INSERT INTO categoria_pregunta (id, materia_id, nombre, categoria_padre_id)"
            " VALUES (:id, :mid, 'Bloque A', :p)"
        ),
        {"id": hija, "mid": mid, "p": padre},
    )
    p_padre, p_hija = str(uuid.uuid4()), str(uuid.uuid4())
    for pid, cat in ((p_padre, padre), (p_hija, hija)):
        await session.execute(
            text(
                "INSERT INTO pregunta_banco (id, materia_id, enunciado, tipo, categoria_id)"
                " VALUES (:id, :mid, :e, 'multichoice', :cid)"
            ),
            {"id": pid, "mid": mid, "e": f"P-{pid[:6]}", "cid": cat},
        )
    await session.commit()
    return mid, padre, hija, p_hija


async def _categorias(client: AsyncClient, materia_id: str, **params) -> list[dict]:
    r = await client.get(
        "/api/v1/exam-content/categorias",
        params={"materia_id": materia_id, **params},
    )
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_dar_de_baja_saca_la_categoria_del_arbol_sin_borrarla(
    client: AsyncClient, session: AsyncSession
):
    materia_id, padre, _hija, _ = await _materia_con_arbol(session)

    r = await client.delete(f"/api/v1/exam-content/categorias/{padre}")
    assert r.status_code == 204, r.text

    vigentes = await _categorias(client, materia_id)
    assert padre not in [c["id"] for c in vigentes]

    fila = await session.execute(
        text("SELECT eliminada_en FROM categoria_pregunta WHERE id = :id"), {"id": padre}
    )
    assert fila.scalar_one() is not None, "se borró de verdad en vez de darse de baja"


@pytest.mark.asyncio
async def test_la_rama_entera_sale_del_arbol(client: AsyncClient, session: AsyncSession):
    """Dar de baja el padre no puede dejar la subcategoría colgando de la nada."""
    materia_id, padre, hija, _ = await _materia_con_arbol(session)
    await client.delete(f"/api/v1/exam-content/categorias/{padre}")

    ids = [c["id"] for c in await _categorias(client, materia_id)]
    assert padre not in ids
    assert hija not in ids, "la subcategoría quedó huérfana en el árbol"


@pytest.mark.asyncio
async def test_las_preguntas_NO_pierden_su_categoria(
    client: AsyncClient, session: AsyncSession
):
    """LO QUE ROMPÍA EL BORRADO FÍSICO: el SET NULL las mandaba a Sin clasificar
    y la organización del banco no se podía recuperar."""
    _materia_id, padre, _hija, pregunta_de_la_hija = await _materia_con_arbol(session)
    await client.delete(f"/api/v1/exam-content/categorias/{padre}")

    cat = await session.execute(
        text("SELECT categoria_id FROM pregunta_banco WHERE id = :id"),
        {"id": pregunta_de_la_hija},
    )
    assert cat.scalar_one() is not None, "la pregunta perdió su categoría"


@pytest.mark.asyncio
async def test_se_ven_las_dadas_de_baja_con_el_filtro(
    client: AsyncClient, session: AsyncSession
):
    materia_id, padre, hija, _ = await _materia_con_arbol(session)
    await client.delete(f"/api/v1/exam-content/categorias/{padre}")

    de_baja = await _categorias(client, materia_id, estado="eliminada")
    ids = [c["id"] for c in de_baja]
    assert padre in ids and hija in ids

    todas = await _categorias(client, materia_id, estado="todas")
    assert len(todas) == 2


@pytest.mark.asyncio
async def test_reactivar_devuelve_la_rama_al_arbol(
    client: AsyncClient, session: AsyncSession
):
    materia_id, padre, hija, _ = await _materia_con_arbol(session)
    await client.delete(f"/api/v1/exam-content/categorias/{padre}")

    r = await client.post(f"/api/v1/exam-content/categorias/{padre}/reactivar")
    assert r.status_code == 200, r.text

    ids = [c["id"] for c in await _categorias(client, materia_id)]
    assert padre in ids and hija in ids, "la subcategoría no volvió con su padre"


@pytest.mark.asyncio
async def test_dar_de_baja_dos_veces_responde_404(
    client: AsyncClient, session: AsyncSession
):
    _materia_id, padre, _hija, _ = await _materia_con_arbol(session)
    assert (await client.delete(f"/api/v1/exam-content/categorias/{padre}")).status_code == 204
    segunda = await client.delete(f"/api/v1/exam-content/categorias/{padre}")
    assert segunda.status_code == 404, segunda.text
