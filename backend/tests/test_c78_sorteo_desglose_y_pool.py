"""c-78 E-07/E-08 (tasks 15.4/15.6): desglose del sorteo y actualización del pool.

`GET /{examen_id}/sorteo` dice, por tramo, cuántas preguntas hay en el pool del
examen contra cuántas se sortean, y si el banco creció desde que se armó.

`POST /{examen_id}/sorteo/actualizar-pool` incorpora esas nuevas. El pool está
congelado a propósito (es lo que evita que tocar el banco rompa un examen), así que
ampliarlo es una decisión explícita — y se bloquea una vez que alguien rindió,
porque si no dos alumnos sortearían de conjuntos distintos.

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


async def _materia_con_comision(
    session: AsyncSession, *, preguntas: int = 20
) -> tuple[str, str, str]:
    """Materia con una comisión y una categoría de ``preguntas`` preguntas."""
    mid = str(uuid.uuid4())
    sufijo = mid[:8]
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, 'M')"),
        {"id": mid, "c": f"POOL-{sufijo}"},
    )
    cid = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO comision (id, materia_id, codigo, nombre, codigo_matriculacion)"
            " VALUES (:id, :mid, 'C1', 'C1', :km)"
        ),
        {"id": cid, "mid": mid, "km": f"POOL-{sufijo}-C1"},
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


async def _crear_examen_sorteado(
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


async def _sumar_al_banco(
    session: AsyncSession, materia_id: str, cat_id: str, cuantas: int
) -> None:
    for i in range(cuantas):
        await session.execute(
            text(
                "INSERT INTO pregunta_banco (id, materia_id, enunciado, tipo, categoria_id)"
                " VALUES (:id, :mid, :e, 'multichoice', :cid)"
            ),
            {
                "id": str(uuid.uuid4()),
                "mid": materia_id,
                "e": f"Nueva {i}-{uuid.uuid4().hex[:6]}",
                "cid": cat_id,
            },
        )
    await session.commit()


@pytest.mark.asyncio
async def test_desglose_dice_cuantas_hay_y_cuantas_se_sortean(
    client_admin: AsyncClient, session: AsyncSession
):
    """RED→GREEN (15.4): el docente ve el desglose por tramo."""
    materia_id, comision_id, cat_id = await _materia_con_comision(session, preguntas=20)
    examen_id = await _crear_examen_sorteado(
        client_admin, materia_id, comision_id, cat_id, 8
    )

    resp = await client_admin.get(f"/api/v1/exam-content/{examen_id}/sorteo")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["modo_preguntas"] == "sorteo_por_intento"
    assert body["largo_del_examen"] == 8
    assert body["pool_total"] == 20
    assert len(body["tramos"]) == 1
    tramo = body["tramos"][0]
    assert tramo["cantidad"] == 8
    assert tramo["en_el_pool"] == 20
    assert tramo["en_el_banco"] == 20
    assert tramo["categoria_nombre"] == "Unidad 1"


@pytest.mark.asyncio
async def test_avisa_cuando_el_banco_crecio(
    client_admin: AsyncClient, session: AsyncSession
):
    """El pool está congelado: si el banco crece, el examen NO lo incorpora solo.

    Sin este aviso, cargar 12 preguntas al banco y suponer que el examen mejoró
    sería una trampa silenciosa.
    """
    materia_id, comision_id, cat_id = await _materia_con_comision(session, preguntas=20)
    examen_id = await _crear_examen_sorteado(
        client_admin, materia_id, comision_id, cat_id, 8
    )

    await _sumar_al_banco(session, materia_id, cat_id, 12)

    resp = await client_admin.get(f"/api/v1/exam-content/{examen_id}/sorteo")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["nuevas_en_el_banco"] == 12
    # El pool sigue igual: nada entró solo.
    assert body["pool_total"] == 20
    assert body["tramos"][0]["en_el_pool"] == 20
    assert body["tramos"][0]["en_el_banco"] == 32


@pytest.mark.asyncio
async def test_actualizar_el_pool_incorpora_las_nuevas(
    client_admin: AsyncClient, session: AsyncSession
):
    """TRIANGULATE: cuando el docente lo decide, las nuevas entran al sorteo."""
    materia_id, comision_id, cat_id = await _materia_con_comision(session, preguntas=20)
    examen_id = await _crear_examen_sorteado(
        client_admin, materia_id, comision_id, cat_id, 8
    )
    await _sumar_al_banco(session, materia_id, cat_id, 12)

    resp = await client_admin.post(
        f"/api/v1/exam-content/{examen_id}/sorteo/actualizar-pool"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["pool_total"] == 32
    assert body["nuevas_en_el_banco"] == 0
    assert body["tramos"][0]["en_el_pool"] == 32

    # Las nuevas entran SIN marcar, igual que al armar: quién rinde cada una lo
    # decide el sorteo del intento.
    marcadas = await session.execute(
        text(
            "SELECT COUNT(*) FROM pregunta_examen"
            " WHERE examen_id = :eid AND seleccionada = true"
        ),
        {"eid": examen_id},
    )
    assert marcadas.scalar_one() == 0


@pytest.mark.asyncio
async def test_actualizar_dos_veces_no_duplica(
    client_admin: AsyncClient, session: AsyncSession
):
    """Idempotente: sin nada nuevo en el banco, no agrega copias."""
    materia_id, comision_id, cat_id = await _materia_con_comision(session, preguntas=20)
    examen_id = await _crear_examen_sorteado(
        client_admin, materia_id, comision_id, cat_id, 8
    )
    await _sumar_al_banco(session, materia_id, cat_id, 5)

    primera = await client_admin.post(
        f"/api/v1/exam-content/{examen_id}/sorteo/actualizar-pool"
    )
    segunda = await client_admin.post(
        f"/api/v1/exam-content/{examen_id}/sorteo/actualizar-pool"
    )
    assert primera.json()["pool_total"] == 25
    assert segunda.json()["pool_total"] == 25


@pytest.mark.asyncio
async def test_no_se_puede_ampliar_el_pool_si_ya_rindio_alguien(
    client_admin: AsyncClient, session: AsyncSession
):
    """Regla del diseño: con intentos rendidos, dos alumnos sortearían de conjuntos
    distintos y dejaría de ser el mismo examen."""
    materia_id, comision_id, cat_id = await _materia_con_comision(session, preguntas=20)
    examen_id = await _crear_examen_sorteado(
        client_admin, materia_id, comision_id, cat_id, 8
    )
    await _sumar_al_banco(session, materia_id, cat_id, 5)
    await session.execute(
        text(
            "INSERT INTO proctoring_session (id, modo, examen_contenido_id)"
            " VALUES (:id, 'examen', :eid)"
        ),
        {"id": str(uuid.uuid4()), "eid": examen_id},
    )
    await session.commit()

    resp = await client_admin.post(
        f"/api/v1/exam-content/{examen_id}/sorteo/actualizar-pool"
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "pool_bloqueado"

    # Y el desglose lo dice, para que la UI apague el botón antes de intentarlo.
    lectura = await client_admin.get(f"/api/v1/exam-content/{examen_id}/sorteo")
    assert lectura.json()["pool_editable"] is False
    assert lectura.json()["total_intentos"] == 1


@pytest.mark.asyncio
async def test_un_examen_con_preguntas_fijas_no_tiene_sorteo(
    client_admin: AsyncClient, session: AsyncSession
):
    """Compat: un examen clásico responde 'fijo' y no ofrece actualizar pool."""
    materia_id, comision_id, cat_id = await _materia_con_comision(session, preguntas=20)
    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial clásico",
            "materia_id": materia_id,
            "comision_id": comision_id,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 8}],
        },
    )
    examen_id = resp.json()["examen_id"]

    lectura = await client_admin.get(f"/api/v1/exam-content/{examen_id}/sorteo")
    assert lectura.status_code == 200, lectura.text
    assert lectura.json()["modo_preguntas"] == "fijo"
    assert lectura.json()["tramos"] == []

    intento = await client_admin.post(
        f"/api/v1/exam-content/{examen_id}/sorteo/actualizar-pool"
    )
    assert intento.status_code == 422
    assert intento.json()["detail"]["error"] == "examen_sin_sorteo"
