"""c-78 task 14.1 (E-06): crear un examen para varias comisiones, replicado.

D12 del design, revisado con el dato del dueño de que en el campus hay UNA sola
aula por materia y las comisiones son grupos dentro de esa aula: se descarta la
relación N:M examen-comisión y se replica. `POST /exam-content/crear-desde-banco`
acepta `comision_ids` y crea N exámenes independientes, uno por comisión, con el
MISMO set de preguntas (se sortea una vez y se copia), en una operación todo o
nada. El título de cada réplica lleva el código de su comisión entre paréntesis.

Las réplicas comparten `lote_replica_id` para que el sistema sepa cuáles nacieron
juntas: sin eso no hay forma de reconstruirlo después.

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
        headers=auth_headers(["admin_sistema"], mfa=True),
    ) as c:
        yield c


@pytest_asyncio.fixture
async def session(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
        await s.rollback()


async def _materia_con_3_comisiones(session: AsyncSession) -> tuple[str, str, list[str]]:
    """Materia con 1 categoría de 6 multichoice y 3 comisiones (C1, C2, C3).

    Devuelve (materia_id, categoria_id, [comision_id...]) en orden C1, C2, C3.
    """
    mid = str(uuid.uuid4())
    sufijo = mid[:8]
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, :n)"),
        {"id": mid, "c": f"MULTI-{sufijo}", "n": "Materia Multi"},
    )
    cat_id = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO categoria_pregunta (id, materia_id, nombre) VALUES (:id, :mid, :n)"
        ),
        {"id": cat_id, "mid": mid, "n": "Unidad 1"},
    )
    for i in range(6):
        await session.execute(
            text(
                "INSERT INTO pregunta_banco (id, materia_id, enunciado, tipo, categoria_id)"
                " VALUES (:id, :mid, :e, 'multichoice', :cid)"
            ),
            {"id": str(uuid.uuid4()), "mid": mid, "e": f"Pregunta {i}", "cid": cat_id},
        )

    comision_ids: list[str] = []
    for codigo in ("C1", "C2", "C3"):
        cid = str(uuid.uuid4())
        await session.execute(
            text(
                "INSERT INTO comision (id, materia_id, codigo, nombre, codigo_matriculacion)"
                " VALUES (:id, :mid, :cod, :n, :km)"
            ),
            {
                "id": cid,
                "mid": mid,
                "cod": codigo,
                "n": f"Comisión {codigo}",
                "km": f"MULTI-{sufijo}-{codigo}",
            },
        )
        comision_ids.append(cid)

    await session.commit()
    return mid, cat_id, comision_ids


async def _titulos_de(session: AsyncSession, examen_ids: list[str]) -> list[str]:
    """Títulos persistidos, en el orden de `examen_ids`."""
    titulos: list[str] = []
    for eid in examen_ids:
        fila = await session.execute(
            text("SELECT titulo FROM examen_contenido WHERE id = :eid"),
            {"eid": eid},
        )
        titulos.append(fila.scalar_one())
    return titulos


@pytest.mark.asyncio
async def test_replica_un_examen_por_comision(
    client_admin: AsyncClient, session: AsyncSession
):
    """RED→GREEN: 3 comisiones → 3 exámenes independientes, uno por comisión."""
    materia_id, cat_id, comisiones = await _materia_con_3_comisiones(session)

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial 1",
            "materia_id": materia_id,
            "comision_ids": comisiones,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 4}],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert len(body["examenes"]) == 3
    assert [e["comision_id"] for e in body["examenes"]] == comisiones
    # Los tres son exámenes distintos, no el mismo repetido.
    assert len({e["examen_id"] for e in body["examenes"]}) == 3
    assert body["total_preguntas"] == 4

    for item in body["examenes"]:
        cuenta = await session.execute(
            text("SELECT COUNT(*) FROM pregunta_examen WHERE examen_id = :eid"),
            {"eid": item["examen_id"]},
        )
        assert cuenta.scalar_one() == 4


@pytest.mark.asyncio
async def test_titulo_de_cada_replica_lleva_el_codigo_de_su_comision(
    client_admin: AsyncClient, session: AsyncSession
):
    """Decisión del dueño: «Parcial 1» + C1/C2/C3 → «Parcial 1 (C1)», etc.

    Sin el sufijo los tres se ven idénticos en el picker de Notas, donde no hay
    columna de comisión.
    """
    materia_id, cat_id, comisiones = await _materia_con_3_comisiones(session)

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial 1",
            "materia_id": materia_id,
            "comision_ids": comisiones,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 2}],
        },
    )
    assert resp.status_code == 201, resp.text
    examenes = resp.json()["examenes"]

    assert [e["titulo"] for e in examenes] == [
        "Parcial 1 (C1)",
        "Parcial 1 (C2)",
        "Parcial 1 (C3)",
    ]
    # El título viaja a la base, no solo a la respuesta.
    persistidos = await _titulos_de(session, [e["examen_id"] for e in examenes])
    assert persistidos == ["Parcial 1 (C1)", "Parcial 1 (C2)", "Parcial 1 (C3)"]


@pytest.mark.asyncio
async def test_las_replicas_comparten_el_mismo_set_de_preguntas(
    client_admin: AsyncClient, session: AsyncSession
):
    """TRIANGULATE: se sortea UNA vez y ese set se copia a las N réplicas.

    Con 6 preguntas en el banco y 4 pedidas, tres sorteos independientes casi
    nunca darían el mismo trío — este test falla si cada réplica sortea por su
    cuenta.
    """
    materia_id, cat_id, comisiones = await _materia_con_3_comisiones(session)

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial mismo set",
            "materia_id": materia_id,
            "comision_ids": comisiones,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 4}],
        },
    )
    assert resp.status_code == 201, resp.text
    examenes = resp.json()["examenes"]

    sets: list[set[str]] = []
    for item in examenes:
        filas = await session.execute(
            text(
                "SELECT pregunta_banco_id FROM pregunta_examen WHERE examen_id = :eid"
            ),
            {"eid": item["examen_id"]},
        )
        sets.append({r[0] for r in filas.fetchall()})

    assert sets[0] == sets[1] == sets[2]
    assert len(sets[0]) == 4


@pytest.mark.asyncio
async def test_las_replicas_comparten_lote_y_una_sola_comision_no_lo_tiene(
    client_admin: AsyncClient, session: AsyncSession
):
    """El lote marca cuáles nacieron juntas; un examen suelto no pertenece a ninguno."""
    materia_id, cat_id, comisiones = await _materia_con_3_comisiones(session)

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial con lote",
            "materia_id": materia_id,
            "comision_ids": comisiones,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 2}],
        },
    )
    assert resp.status_code == 201, resp.text
    lote = resp.json()["lote_replica_id"]
    assert lote is not None

    filas = await session.execute(
        text("SELECT lote_replica_id FROM examen_contenido WHERE lote_replica_id = :l"),
        {"l": lote},
    )
    assert len(filas.fetchall()) == 3

    # TRIANGULATE: una sola comisión no es un lote — ni sufijo, ni lote_replica_id.
    solo = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial suelto",
            "materia_id": materia_id,
            "comision_ids": [comisiones[0]],
            "sorteo": [{"categoria_id": cat_id, "cantidad": 2}],
        },
    )
    assert solo.status_code == 201, solo.text
    assert solo.json()["lote_replica_id"] is None
    assert solo.json()["examenes"][0]["titulo"] == "Parcial suelto"


@pytest.mark.asyncio
async def test_comision_de_otra_materia_no_crea_ninguna_replica(
    client_admin: AsyncClient, session: AsyncSession
):
    """Todo o nada: si una comisión no es de la materia, no se crea NADA.

    Replicar a una comisión de otra materia dejaría un examen con preguntas de un
    banco que esa comisión no cursa.
    """
    materia_id, cat_id, comisiones = await _materia_con_3_comisiones(session)
    _, _, ajenas = await _materia_con_3_comisiones(session)

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial mezclado",
            "materia_id": materia_id,
            "comision_ids": [comisiones[0], ajenas[0]],
            "sorteo": [{"categoria_id": cat_id, "cantidad": 2}],
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "comision_de_otra_materia"

    total = await session.execute(
        text("SELECT COUNT(*) FROM examen_contenido WHERE titulo LIKE 'Parcial mezclado%'")
    )
    assert total.scalar_one() == 0


@pytest.mark.asyncio
async def test_comision_inexistente_no_crea_ninguna_replica(
    client_admin: AsyncClient, session: AsyncSession
):
    """TRIANGULATE del todo o nada: una comisión que no existe aborta el lote entero."""
    materia_id, cat_id, comisiones = await _materia_con_3_comisiones(session)

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial fantasma",
            "materia_id": materia_id,
            "comision_ids": [comisiones[0], str(uuid.uuid4())],
            "sorteo": [{"categoria_id": cat_id, "cantidad": 2}],
        },
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"] == "comision_inexistente"

    total = await session.execute(
        text("SELECT COUNT(*) FROM examen_contenido WHERE titulo LIKE 'Parcial fantasma%'")
    )
    assert total.scalar_one() == 0


@pytest.mark.asyncio
async def test_sorteo_insuficiente_no_crea_ninguna_replica(
    client_admin: AsyncClient, session: AsyncSession
):
    """El 422 del sorteo sigue abortando todo, también en modo replicado."""
    materia_id, cat_id, comisiones = await _materia_con_3_comisiones(session)

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial imposible",
            "materia_id": materia_id,
            "comision_ids": comisiones,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 99}],
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "sorteo_insuficiente"

    total = await session.execute(
        text("SELECT COUNT(*) FROM examen_contenido WHERE titulo LIKE 'Parcial imposible%'")
    )
    assert total.scalar_one() == 0


@pytest.mark.asyncio
async def test_comision_id_y_comision_ids_juntos_se_rechaza(
    client_admin: AsyncClient, session: AsyncSession
):
    """Las dos formas de decir a qué comisión va son excluyentes."""
    materia_id, cat_id, comisiones = await _materia_con_3_comisiones(session)

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial ambiguo",
            "materia_id": materia_id,
            "comision_id": comisiones[0],
            "comision_ids": comisiones,
            "sorteo": [{"categoria_id": cat_id, "cantidad": 2}],
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_comision_id_suelto_sigue_funcionando(
    client_admin: AsyncClient, session: AsyncSession
):
    """Compat: el body viejo (una comisión, sin `comision_ids`) no cambia."""
    materia_id, cat_id, comisiones = await _materia_con_3_comisiones(session)

    resp = await client_admin.post(
        "/api/v1/exam-content/crear-desde-banco",
        json={
            "titulo": "Parcial clásico",
            "materia_id": materia_id,
            "comision_id": comisiones[0],
            "sorteo": [{"categoria_id": cat_id, "cantidad": 3}],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert body["titulo"] == "Parcial clásico"
    assert body["total_preguntas"] == 3
    assert body["lote_replica_id"] is None
    # `examen_id` sigue siendo la forma corta que consume el front viejo.
    assert body["examen_id"] == body["examenes"][0]["examen_id"]

    fila = await session.execute(
        text("SELECT comision_id::text FROM examen_contenido WHERE id = :eid"),
        {"eid": body["examen_id"]},
    )
    assert fila.scalar_one() == comisiones[0]
