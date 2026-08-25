"""c-78 E-07 (task 15.1): armar un examen que sortea por intento.

`POST /exam-content/crear-desde-banco` con `sorteo_por_intento=true` copia el POOL
ENTERO de cada tramo al examen (no las `cantidad` sorteadas) y guarda la REGLA del
sorteo en `tramo_sorteo_examen`. El set concreto lo resuelve después cada intento.

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


async def _banco(session: AsyncSession, *, cuantas: int = 30) -> tuple[str, str]:
    """Materia con una categoría de ``cuantas`` preguntas. Devuelve (materia, categoría)."""
    mid = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, 'M')"),
        {"id": mid, "c": f"ARM-{mid[:8]}"},
    )
    cat_id = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO categoria_pregunta (id, materia_id, nombre)"
            " VALUES (:id, :mid, 'Unidad 1')"
        ),
        {"id": cat_id, "mid": mid},
    )
    for i in range(cuantas):
        await session.execute(
            text(
                "INSERT INTO pregunta_banco (id, materia_id, enunciado, tipo, categoria_id)"
                " VALUES (:id, :mid, :e, 'multichoice', :cid)"
            ),
            {"id": str(uuid.uuid4()), "mid": mid, "e": f"P{i}", "cid": cat_id},
        )
    await session.commit()
    return mid, cat_id


@pytest.mark.asyncio
async def test_copia_el_pool_entero_y_no_solo_las_sorteadas(
    client_admin: AsyncClient, session: AsyncSession
):
    """RED→GREEN: un examen de 10 sobre un banco de 30 se lleva las 30.

    Es lo que hace posible sortear después sin volver al banco.
    """
    materia_id, cat_id = await _banco(session, cuantas=30)

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial sorteado",
            "materia_id": materia_id,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 10}],
            "sorteo_por_intento": True,
        },
    )
    assert resp.status_code == 201, resp.text
    examen_id = resp.json()["examen_id"]

    total = await session.execute(
        text("SELECT COUNT(*) FROM pregunta_examen WHERE examen_id = :eid"),
        {"eid": examen_id},
    )
    assert total.scalar_one() == 30

    # Nada queda marcado: quién entra lo decide el sorteo de cada intento.
    marcadas = await session.execute(
        text(
            "SELECT COUNT(*) FROM pregunta_examen"
            " WHERE examen_id = :eid AND seleccionada = true"
        ),
        {"eid": examen_id},
    )
    assert marcadas.scalar_one() == 0


@pytest.mark.asyncio
async def test_guarda_la_regla_del_sorteo(
    client_admin: AsyncClient, session: AsyncSession
):
    """La condición se persiste: categoría, subcategorías, tipos y cantidad."""
    materia_id, cat_id = await _banco(session, cuantas=30)

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial con regla",
            "materia_id": materia_id,
            "sorteo": [
                {
                    "categoria_id": cat_id,
                    "cantidad": 7,
                    "incluir_subcategorias": False,
                    "tipos": ["multichoice"],
                }
            ],
            "sorteo_por_intento": True,
        },
    )
    assert resp.status_code == 201, resp.text
    examen_id = resp.json()["examen_id"]

    fila = await session.execute(
        text(
            "SELECT categoria_id::text, incluir_subcategorias, tipos, cantidad"
            " FROM tramo_sorteo_examen WHERE examen_id = :eid"
        ),
        {"eid": examen_id},
    )
    categoria, incluir_sub, tipos, cantidad = fila.fetchone()
    assert categoria == cat_id
    assert incluir_sub is False
    assert tipos == ["multichoice"]
    assert cantidad == 7


@pytest.mark.asyncio
async def test_modo_clasico_sigue_copiando_solo_las_sorteadas(
    client_admin: AsyncClient, session: AsyncSession
):
    """TRIANGULATE / compat: sin `sorteo_por_intento` nada cambia."""
    materia_id, cat_id = await _banco(session, cuantas=30)

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial clásico",
            "materia_id": materia_id,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 10}],
        },
    )
    assert resp.status_code == 201, resp.text
    examen_id = resp.json()["examen_id"]

    total = await session.execute(
        text(
            "SELECT COUNT(*) FROM pregunta_examen"
            " WHERE examen_id = :eid AND seleccionada = true"
        ),
        {"eid": examen_id},
    )
    assert total.scalar_one() == 10

    tramos = await session.execute(
        text("SELECT COUNT(*) FROM tramo_sorteo_examen WHERE examen_id = :eid"),
        {"eid": examen_id},
    )
    assert tramos.scalar_one() == 0

    modo = await session.execute(
        text("SELECT modo_preguntas FROM examen_contenido WHERE id = :eid"),
        {"eid": examen_id},
    )
    assert modo.scalar_one() == "fijo"


@pytest.mark.asyncio
async def test_el_tope_se_compara_contra_lo_que_rinde_el_alumno(
    client_admin: AsyncClient, session: AsyncSession
):
    """El pool es a propósito más grande que el examen: el tope mira el examen.

    Sin esto, un examen de 10 con un pool de 30 y tope 12 se rechazaría por
    "excedido", que es exactamente al revés de lo que pasa.
    """
    materia_id, cat_id = await _banco(session, cuantas=30)

    ok = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial con tope holgado",
            "materia_id": materia_id,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 10}],
            "sorteo_por_intento": True,
            "limite_preguntas": 12,
        },
    )
    assert ok.status_code == 201, ok.text

    # TRIANGULATE: el tope SÍ corta cuando el examen lo excede de verdad.
    excedido = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial excedido",
            "materia_id": materia_id,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 20}],
            "sorteo_por_intento": True,
            "limite_preguntas": 12,
        },
    )
    assert excedido.status_code == 422
    assert excedido.json()["detail"]["error"] == "limite_preguntas_excedido"
    assert excedido.json()["detail"]["sorteadas"] == 20


@pytest.mark.asyncio
async def test_banco_insuficiente_se_rechaza_al_armar_no_al_rendir(
    client_admin: AsyncClient, session: AsyncSession
):
    """La diferencia con Moodle: el error lo ve el docente, no el alumno."""
    materia_id, cat_id = await _banco(session, cuantas=6)

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial imposible",
            "materia_id": materia_id,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 10}],
            "sorteo_por_intento": True,
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "sorteo_insuficiente"
    assert resp.json()["detail"]["disponibles"] == 6

    total = await session.execute(
        text("SELECT COUNT(*) FROM examen_contenido WHERE titulo = 'Parcial imposible'")
    )
    assert total.scalar_one() == 0


@pytest.mark.asyncio
async def test_nace_en_borrador_si_se_pide(
    client_admin: AsyncClient, session: AsyncSession
):
    """E-07: el examen se puede crear invisible para el alumno, para probarlo."""
    materia_id, cat_id = await _banco(session, cuantas=10)

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial en borrador",
            "materia_id": materia_id,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 5}],
            "borrador": True,
        },
    )
    assert resp.status_code == 201, resp.text

    fila = await session.execute(
        text("SELECT borrador FROM examen_contenido WHERE id = :eid"),
        {"eid": resp.json()["examen_id"]},
    )
    assert fila.scalar_one() is True

    # Por default NO nace en borrador (compat con todo lo que ya existe).
    normal = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial normal",
            "materia_id": materia_id,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 5}],
        },
    )
    assert normal.status_code == 201, normal.text
    fila = await session.execute(
        text("SELECT borrador FROM examen_contenido WHERE id = :eid"),
        {"eid": normal.json()["examen_id"]},
    )
    assert fila.scalar_one() is False


@pytest.mark.asyncio
async def test_las_replicas_multi_comision_heredan_el_sorteo(
    client_admin: AsyncClient, session: AsyncSession
):
    """E-06 + E-07: cada réplica se lleva el pool Y la regla del sorteo.

    Sin la regla, la réplica no sabría qué sortear y el alumno quedaría sin examen.
    """
    materia_id, cat_id = await _banco(session, cuantas=30)
    comisiones = []
    for codigo in ("C1", "C2"):
        cid = str(uuid.uuid4())
        await session.execute(
            text(
                "INSERT INTO comision (id, materia_id, codigo, nombre, codigo_matriculacion)"
                " VALUES (:id, :mid, :cod, :n, :km)"
            ),
            {
                "id": cid,
                "mid": materia_id,
                "cod": codigo,
                "n": codigo,
                "km": f"{materia_id[:8]}-{codigo}",
            },
        )
        comisiones.append(cid)
    await session.commit()

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial replicado y sorteado",
            "materia_id": materia_id,
            "comision_ids": comisiones,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 10}],
            "sorteo_por_intento": True,
        },
    )
    assert resp.status_code == 201, resp.text

    for item in resp.json()["examenes"]:
        pool = await session.execute(
            text("SELECT COUNT(*) FROM pregunta_examen WHERE examen_id = :eid"),
            {"eid": item["examen_id"]},
        )
        assert pool.scalar_one() == 30
        tramos = await session.execute(
            text(
                "SELECT cantidad FROM tramo_sorteo_examen WHERE examen_id = :eid"
            ),
            {"eid": item["examen_id"]},
        )
        assert [r[0] for r in tramos.fetchall()] == [10]
