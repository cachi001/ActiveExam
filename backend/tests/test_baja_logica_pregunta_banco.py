"""Baja LÓGICA de una pregunta del banco, con las guardas que evitan romper exámenes.

No había ninguna forma de sacar una pregunta del banco desde la aplicación: ni
endpoint ni botón. Con el import duplicando preguntas al editarlas (arreglado
aparte), el banco se ensuciaba y no se podía limpiar salvo entrando a la base.

Se agrega baja lógica, el mismo patrón que materia, comisión, examen y usuario:
`DELETE /preguntas/{id}` da de baja y `POST /preguntas/{id}/reactivar` revierte.
Nada se borra nunca: un examen ya rendido tiene que poder reconstruirse (regla
dura #6, cadena de custodia).

GUARDA: no se puede dar de baja una pregunta que está en el pool de un examen
ACTIVO. El pool del examen es una copia, así que técnicamente el examen no se
rompería; pero el docente que da de baja una pregunta espera que deje de tomarse,
y en un examen ya armado seguiría saliendo sorteada. Se rechaza con 409 y se
dice en qué exámenes está, para que sea una decisión informada y no una sorpresa.

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
async def client_admin(db_engine):
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


async def _materia_con_preguntas(
    session: AsyncSession, *, cuantas: int = 12
) -> tuple[str, str, str, list[str]]:
    """Materia + comisión + categoría con `cuantas` preguntas. Devuelve sus ids."""
    mid = str(uuid.uuid4())
    sufijo = mid[:8]
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, 'M')"),
        {"id": mid, "c": f"BAJA-{sufijo}"},
    )
    cid = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO comision (id, materia_id, codigo, nombre, codigo_matriculacion)"
            " VALUES (:id, :mid, 'C1', 'C1', :km)"
        ),
        {"id": cid, "mid": mid, "km": f"BAJA-{sufijo}-C1"},
    )
    cat_id = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO categoria_pregunta (id, materia_id, nombre)"
            " VALUES (:id, :mid, 'Unidad 1')"
        ),
        {"id": cat_id, "mid": mid},
    )
    ids: list[str] = []
    for i in range(cuantas):
        pid = str(uuid.uuid4())
        ids.append(pid)
        await session.execute(
            text(
                "INSERT INTO pregunta_banco (id, materia_id, enunciado, tipo, categoria_id)"
                " VALUES (:id, :mid, :e, 'multichoice', :cid)"
            ),
            {"id": pid, "mid": mid, "e": f"P{i}", "cid": cat_id},
        )
    await session.commit()
    return mid, cid, cat_id, ids


async def _listar(client: AsyncClient, materia_id: str, **params) -> list[dict]:
    resp = await client.get(
        "/api/v1/exam-content/preguntas",
        params={"materia_id": materia_id, **params},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_dar_de_baja_saca_la_pregunta_del_banco_sin_borrarla(
    client_admin: AsyncClient, session: AsyncSession
):
    """RED→GREEN: deja de listarse, pero la fila sigue en la base."""
    materia_id, _, _, ids = await _materia_con_preguntas(session, cuantas=3)

    resp = await client_admin.delete(f"/api/v1/exam-content/preguntas/{ids[0]}")
    assert resp.status_code == 204, resp.text

    vigentes = await _listar(client_admin, materia_id)
    assert ids[0] not in [p["id"] for p in vigentes]
    assert len(vigentes) == 2

    fila = await session.execute(
        text("SELECT eliminada_en FROM pregunta_banco WHERE id = :id"), {"id": ids[0]}
    )
    assert fila.scalar_one() is not None, "se borró de verdad en vez de darse de baja"


@pytest.mark.asyncio
async def test_se_pueden_ver_las_dadas_de_baja_con_el_filtro(
    client_admin: AsyncClient, session: AsyncSession
):
    """La papelera: sin esto, dar de baja es indistinguible de borrar."""
    materia_id, _, _, ids = await _materia_con_preguntas(session, cuantas=3)
    await client_admin.delete(f"/api/v1/exam-content/preguntas/{ids[0]}")

    de_baja = await _listar(client_admin, materia_id, estado="eliminada")
    assert [p["id"] for p in de_baja] == [ids[0]]

    todas = await _listar(client_admin, materia_id, estado="todas")
    assert len(todas) == 3
    marcada = next(p for p in todas if p["id"] == ids[0])
    assert marcada["eliminada_en"] is not None


@pytest.mark.asyncio
async def test_reactivar_la_devuelve_al_banco(
    client_admin: AsyncClient, session: AsyncSession
):
    materia_id, _, _, ids = await _materia_con_preguntas(session, cuantas=3)
    await client_admin.delete(f"/api/v1/exam-content/preguntas/{ids[0]}")

    resp = await client_admin.post(
        f"/api/v1/exam-content/preguntas/{ids[0]}/reactivar"
    )
    assert resp.status_code == 200, resp.text

    vigentes = await _listar(client_admin, materia_id)
    assert ids[0] in [p["id"] for p in vigentes]
    assert len(vigentes) == 3


@pytest.mark.asyncio
async def test_no_se_puede_dar_de_baja_una_pregunta_usada_por_un_examen(
    client_admin: AsyncClient, session: AsyncSession
):
    """LA GUARDA: el examen ya armado la seguiría sorteando."""
    materia_id, comision_id, cat_id, ids = await _materia_con_preguntas(
        session, cuantas=12
    )
    crear = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial con esa pregunta",
            "materia_id": materia_id,
            "comision_id": comision_id,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 5}],
            "sorteo_por_intento": True,
        },
    )
    assert crear.status_code == 201, crear.text

    resp = await client_admin.delete(f"/api/v1/exam-content/preguntas/{ids[0]}")
    assert resp.status_code == 409, resp.text
    detalle = resp.json()["detail"]
    assert detalle["error"] == "pregunta_en_uso"
    assert "Parcial con esa pregunta" in str(detalle)

    # Y sigue vigente: el rechazo no dejó a medias la baja.
    vigentes = await _listar(client_admin, materia_id)
    assert ids[0] in [p["id"] for p in vigentes]


@pytest.mark.asyncio
async def test_un_examen_dado_de_baja_no_bloquea(
    client_admin: AsyncClient, session: AsyncSession
):
    """Triangulación: la guarda mira exámenes ACTIVOS, no el historial entero."""
    materia_id, comision_id, cat_id, ids = await _materia_con_preguntas(
        session, cuantas=12
    )
    crear = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial viejo",
            "materia_id": materia_id,
            "comision_id": comision_id,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 5}],
            "sorteo_por_intento": True,
        },
    )
    examen_id = crear.json()["examen_id"]
    baja_examen = await client_admin.delete(f"/api/v1/exam-content/{examen_id}")
    assert baja_examen.status_code in (200, 204), baja_examen.text

    resp = await client_admin.delete(f"/api/v1/exam-content/preguntas/{ids[0]}")
    assert resp.status_code == 204, resp.text


@pytest.mark.asyncio
async def test_una_pregunta_de_baja_no_entra_a_un_examen_nuevo(
    client_admin: AsyncClient, session: AsyncSession
):
    """Que no se liste es la mitad: tampoco tiene que llegar al pool."""
    materia_id, comision_id, cat_id, ids = await _materia_con_preguntas(
        session, cuantas=10
    )
    for pid in ids[:4]:
        r = await client_admin.delete(f"/api/v1/exam-content/preguntas/{pid}")
        assert r.status_code == 204, r.text

    crear = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial posterior a la baja",
            "materia_id": materia_id,
            "comision_id": comision_id,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 3}],
            "sorteo_por_intento": True,
        },
    )
    assert crear.status_code == 201, crear.text
    examen_id = crear.json()["examen_id"]

    pool = await session.execute(
        text(
            "SELECT pb.id FROM pregunta_examen pe "
            "JOIN pregunta_banco pb ON pb.id = pe.pregunta_banco_id "
            "WHERE pe.examen_id = :eid"
        ),
        {"eid": examen_id},
    )
    en_el_pool = {r[0] for r in pool}
    assert en_el_pool.isdisjoint(set(ids[:4])), "una pregunta de baja llegó al examen"


@pytest.mark.asyncio
async def test_dar_de_baja_dos_veces_responde_404(
    client_admin: AsyncClient, session: AsyncSession
):
    """Mismo contrato que materia, examen y usuario."""
    _, _, _, ids = await _materia_con_preguntas(session, cuantas=2)
    assert (await client_admin.delete(f"/api/v1/exam-content/preguntas/{ids[0]}")).status_code == 204
    segunda = await client_admin.delete(f"/api/v1/exam-content/preguntas/{ids[0]}")
    assert segunda.status_code == 404, segunda.text
