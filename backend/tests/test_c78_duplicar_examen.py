"""c-78 task 14.2 (E-06): duplicar un examen.

`POST /exam-content/{examen_id}/duplicar` crea un examen nuevo con las mismas
preguntas y la misma configuración de mecánica y nota, y SIN arrastrar nada de lo
que pertenece al examen original: ni intentos, ni notas publicadas, ni el destino
de write-back en Moodle. Opcionalmente se le puede dar otro título y mandarlo a
otra comisión de la misma materia.

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
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_TABLES = [
    "proctoring_session",
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
                ProctoringSessionModel.__table__,
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


async def _examen_rendido(session: AsyncSession) -> dict:
    """Un examen ya usado: 2 preguntas con opciones, destino de Moodle fijado,
    notas publicadas y una sesión rendida.

    Devuelve {materia_id, comision_id, comision_hermana_id, examen_id}.
    """
    mid = str(uuid.uuid4())
    sufijo = mid[:8]
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, :n)"),
        {"id": mid, "c": f"DUP-{sufijo}", "n": "Materia Dup"},
    )
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
                "mid": mid,
                "cod": codigo,
                "n": f"Comisión {codigo}",
                "km": f"DUP-{sufijo}-{codigo}",
            },
        )
        comisiones.append(cid)

    examen_id = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO examen_contenido"
            " (id, titulo, comision_id, moodle_courseid, moodle_cmid, moodle_component,"
            "  tiempo_limite_min, intentos_permitidos, nota_maxima, nota_aprobacion,"
            "  limite_preguntas, mostrar_nota, notas_publicadas_en, notas_publicadas_por,"
            "  politica_intentos)"
            " VALUES (:id, :t, :cid, 77, 88, 'mod_quiz', 45, 2, 10, 6, 20, 'inmediata',"
            "         now(), 'alguien@utn.edu.ar', 'PRIMERO')"
        ),
        {"id": examen_id, "t": "Parcial original", "cid": comisiones[0]},
    )

    for orden in range(2):
        pregunta_id = str(uuid.uuid4())
        await session.execute(
            text(
                "INSERT INTO pregunta_examen (id, examen_id, enunciado, tipo, orden, seleccionada)"
                " VALUES (:id, :eid, :e, 'multichoice', :o, true)"
            ),
            {
                "id": pregunta_id,
                "eid": examen_id,
                "e": f"Enunciado {orden}",
                "o": orden,
            },
        )
        for i, correcta in enumerate([True, False]):
            await session.execute(
                text(
                    "INSERT INTO opcion_respuesta (id, pregunta_id, texto, es_correcta, orden)"
                    " VALUES (:id, :pid, :t, :c, :o)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "pid": pregunta_id,
                    "t": f"Opción {orden}.{i}",
                    "c": correcta,
                    "o": i,
                },
            )

    await session.execute(
        text(
            "INSERT INTO proctoring_session (id, modo, examen_contenido_id, finalizada_en)"
            " VALUES (:id, 'examen', :eid, now())"
        ),
        {"id": str(uuid.uuid4()), "eid": examen_id},
    )

    await session.commit()
    return {
        "materia_id": mid,
        "comision_id": comisiones[0],
        "comision_hermana_id": comisiones[1],
        "examen_id": examen_id,
    }


@pytest.mark.asyncio
async def test_duplicar_copia_preguntas_y_opciones(
    client_admin: AsyncClient, session: AsyncSession
):
    """RED→GREEN: la copia trae las mismas preguntas y opciones, con ids propios."""
    datos = await _examen_rendido(session)

    resp = await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/duplicar", json={}
    )
    assert resp.status_code == 201, resp.text
    copia_id = resp.json()["examen_id"]
    assert copia_id != datos["examen_id"]
    assert resp.json()["total_preguntas"] == 2

    enunciados = await session.execute(
        text(
            "SELECT enunciado FROM pregunta_examen WHERE examen_id = :eid ORDER BY orden"
        ),
        {"eid": copia_id},
    )
    assert [r[0] for r in enunciados.fetchall()] == ["Enunciado 0", "Enunciado 1"]

    # Las opciones se copian con su marca de correcta: sin eso la copia no se
    # puede calificar.
    opciones = await session.execute(
        text(
            "SELECT o.texto, o.es_correcta FROM opcion_respuesta o"
            " JOIN pregunta_examen p ON p.id = o.pregunta_id"
            " WHERE p.examen_id = :eid ORDER BY p.orden, o.orden"
        ),
        {"eid": copia_id},
    )
    assert [(r[0], r[1]) for r in opciones.fetchall()] == [
        ("Opción 0.0", True),
        ("Opción 0.1", False),
        ("Opción 1.0", True),
        ("Opción 1.1", False),
    ]

    # Las preguntas son filas NUEVAS: editar la copia no toca al original.
    ids_originales = await session.execute(
        text("SELECT id FROM pregunta_examen WHERE examen_id = :eid"),
        {"eid": datos["examen_id"]},
    )
    ids_copia = await session.execute(
        text("SELECT id FROM pregunta_examen WHERE examen_id = :eid"),
        {"eid": copia_id},
    )
    assert not ({r[0] for r in ids_originales.fetchall()} & {r[0] for r in ids_copia.fetchall()})


@pytest.mark.asyncio
async def test_duplicar_no_arrastra_moodle_ni_notas_publicadas(
    client_admin: AsyncClient, session: AsyncSession
):
    """Lo que la copia NO hereda: destino de Moodle y notas ya publicadas.

    Heredar el `cmid` haría que la copia escriba encima de las notas del original;
    heredar `notas_publicadas_en` diría que se publicaron notas que no existen.
    """
    datos = await _examen_rendido(session)

    resp = await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/duplicar", json={}
    )
    assert resp.status_code == 201, resp.text
    copia_id = resp.json()["examen_id"]

    fila = await session.execute(
        text(
            "SELECT moodle_courseid, moodle_cmid, moodle_component,"
            " notas_publicadas_en, notas_publicadas_por, eliminado_en, lote_replica_id"
            " FROM examen_contenido WHERE id = :eid"
        ),
        {"eid": copia_id},
    )
    assert list(fila.fetchone()) == [None] * 7


@pytest.mark.asyncio
async def test_duplicar_no_arrastra_intentos(
    client_admin: AsyncClient, session: AsyncSession
):
    """TRIANGULATE: la sesión rendida queda en el original y la copia nace sin ninguna."""
    datos = await _examen_rendido(session)

    resp = await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/duplicar", json={}
    )
    assert resp.status_code == 201, resp.text
    copia_id = resp.json()["examen_id"]

    del_original = await session.execute(
        text("SELECT COUNT(*) FROM proctoring_session WHERE examen_contenido_id = :eid"),
        {"eid": datos["examen_id"]},
    )
    de_la_copia = await session.execute(
        text("SELECT COUNT(*) FROM proctoring_session WHERE examen_contenido_id = :eid"),
        {"eid": copia_id},
    )
    assert del_original.scalar_one() == 1
    assert de_la_copia.scalar_one() == 0


@pytest.mark.asyncio
async def test_duplicar_conserva_la_configuracion_de_mecanica_y_nota(
    client_admin: AsyncClient, session: AsyncSession
):
    """La copia sirve para volver a tomar lo mismo: la mecánica viaja con ella."""
    datos = await _examen_rendido(session)

    resp = await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/duplicar", json={}
    )
    assert resp.status_code == 201, resp.text
    copia_id = resp.json()["examen_id"]

    fila = await session.execute(
        text(
            "SELECT tiempo_limite_min, intentos_permitidos, nota_maxima,"
            " nota_aprobacion, limite_preguntas, mostrar_nota, politica_intentos"
            " FROM examen_contenido WHERE id = :eid"
        ),
        {"eid": copia_id},
    )
    tiempo, intentos, maxima, aprobacion, limite, mostrar, politica = fila.fetchone()
    assert tiempo == 45
    assert intentos == 2
    assert float(maxima) == 10.0
    assert float(aprobacion) == 6.0
    assert limite == 20
    assert mostrar == "inmediata"
    assert politica == "PRIMERO"


@pytest.mark.asyncio
async def test_duplicar_titulo_por_defecto_y_titulo_propio(
    client_admin: AsyncClient, session: AsyncSession
):
    """Sin título, la copia se llama «… (copia)»; con título, se llama como se pidió."""
    datos = await _examen_rendido(session)

    por_defecto = await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/duplicar", json={}
    )
    assert por_defecto.status_code == 201, por_defecto.text
    assert por_defecto.json()["titulo"] == "Parcial original (copia)"

    propio = await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/duplicar",
        json={"titulo": "Recuperatorio"},
    )
    assert propio.status_code == 201, propio.text
    assert propio.json()["titulo"] == "Recuperatorio"


@pytest.mark.asyncio
async def test_duplicar_a_otra_comision_de_la_misma_materia(
    client_admin: AsyncClient, session: AsyncSession
):
    """La copia puede ir a otra comisión de la materia; por default queda en la misma."""
    datos = await _examen_rendido(session)

    misma = await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/duplicar", json={}
    )
    assert misma.status_code == 201, misma.text
    assert misma.json()["comision_id"] == datos["comision_id"]

    otra = await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/duplicar",
        json={"comision_id": datos["comision_hermana_id"]},
    )
    assert otra.status_code == 201, otra.text
    assert otra.json()["comision_id"] == datos["comision_hermana_id"]


@pytest.mark.asyncio
async def test_duplicar_a_comision_de_otra_materia_se_rechaza(
    client_admin: AsyncClient, session: AsyncSession
):
    """TRIANGULATE: mover la copia a otra materia dejaría preguntas que no corresponden."""
    datos = await _examen_rendido(session)
    ajenos = await _examen_rendido(session)

    resp = await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/duplicar",
        json={"comision_id": ajenos["comision_id"]},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "comision_de_otra_materia"

    # Nada quedó colgando en la comisión ajena. Se cuenta sobre ESA comisión (que
    # es nueva en cada test) y no sobre el título, que otros tests del módulo
    # también usan.
    total = await session.execute(
        text(
            "SELECT COUNT(*) FROM examen_contenido"
            " WHERE comision_id = :cid AND titulo LIKE '%(copia)%'"
        ),
        {"cid": ajenos["comision_id"]},
    )
    assert total.scalar_one() == 0


@pytest.mark.asyncio
async def test_duplicar_un_examen_inexistente_404(
    client_admin: AsyncClient, session: AsyncSession
):
    resp = await client_admin.post(
        f"/api/v1/exam-content/{uuid.uuid4()}/duplicar", json={}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_duplicar_un_examen_dado_de_baja_404(
    client_admin: AsyncClient, session: AsyncSession
):
    """Un examen fuera del catálogo no se duplica: primero se reactiva."""
    datos = await _examen_rendido(session)
    await session.execute(
        text("UPDATE examen_contenido SET eliminado_en = now() WHERE id = :eid"),
        {"eid": datos["examen_id"]},
    )
    await session.commit()

    resp = await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/duplicar", json={}
    )
    assert resp.status_code == 404
