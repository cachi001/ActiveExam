"""c-78 task 14.4 (E-06): administrar las comisiones que rinden un examen.

Decisión del dueño, posterior a 14.1/14.2: la comisión no se elige al duplicar —
se administra **desde el examen**. El profesor abre el examen y agrega o quita
comisiones.

Bajo el modelo replicado (D12) eso se traduce a: el examen y sus réplicas forman
un lote (`lote_replica_id`), agregar una comisión crea otra réplica con las MISMAS
preguntas dentro del lote, y quitarla es la baja lógica que ya existe
(`DELETE /{examen_id}`), que conserva la evidencia de lo ya rendido.

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


async def _materia_con_examen(session: AsyncSession, titulo: str = "Parcial 1") -> dict:
    """Materia con 3 comisiones (C1, C2, C3) y un examen de 2 preguntas en C1."""
    mid = str(uuid.uuid4())
    sufijo = mid[:8]
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, :n)"),
        {"id": mid, "c": f"COM-{sufijo}", "n": "Materia Comisiones"},
    )
    comisiones: dict[str, str] = {}
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
                "km": f"COM-{sufijo}-{codigo}",
            },
        )
        comisiones[codigo] = cid

    examen_id = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO examen_contenido (id, titulo, comision_id, tiempo_limite_min,"
            " nota_maxima, nota_aprobacion)"
            " VALUES (:id, :t, :cid, 45, 10, 6)"
        ),
        {"id": examen_id, "t": titulo, "cid": comisiones["C1"]},
    )
    for orden in range(2):
        await session.execute(
            text(
                "INSERT INTO pregunta_examen (id, examen_id, enunciado, tipo, orden, seleccionada)"
                " VALUES (:id, :eid, :e, 'multichoice', :o, true)"
            ),
            {
                "id": str(uuid.uuid4()),
                "eid": examen_id,
                "e": f"Enunciado {orden}",
                "o": orden,
            },
        )

    await session.commit()
    return {"materia_id": mid, "comisiones": comisiones, "examen_id": examen_id}


@pytest.mark.asyncio
async def test_examen_solo_lista_una_sola_comision(
    client_admin: AsyncClient, session: AsyncSession
):
    """RED→GREEN: un examen sin lote se lista a sí mismo, no vacío."""
    datos = await _materia_con_examen(session)

    resp = await client_admin.get(
        f"/api/v1/exam-content/{datos['examen_id']}/comisiones"
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]

    assert len(items) == 1
    assert items[0]["examen_id"] == datos["examen_id"]
    assert items[0]["comision_id"] == datos["comisiones"]["C1"]
    assert items[0]["comision_codigo"] == "C1"
    assert items[0]["dado_de_baja"] is False


@pytest.mark.asyncio
async def test_agregar_una_comision_crea_una_replica_con_las_mismas_preguntas(
    client_admin: AsyncClient, session: AsyncSession
):
    """Agregar C2 crea otro examen con el MISMO contenido, no re-sortea nada."""
    datos = await _materia_con_examen(session)

    resp = await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/comisiones",
        json={"comision_id": datos["comisiones"]["C2"]},
    )
    assert resp.status_code == 201, resp.text
    nueva = resp.json()
    assert nueva["comision_id"] == datos["comisiones"]["C2"]
    assert nueva["examen_id"] != datos["examen_id"]

    enunciados = await session.execute(
        text(
            "SELECT enunciado FROM pregunta_examen WHERE examen_id = :eid ORDER BY orden"
        ),
        {"eid": nueva["examen_id"]},
    )
    assert [r[0] for r in enunciados.fetchall()] == ["Enunciado 0", "Enunciado 1"]

    # La mecánica también viaja: es el mismo examen en otra comisión.
    fila = await session.execute(
        text(
            "SELECT tiempo_limite_min, nota_maxima FROM examen_contenido WHERE id = :eid"
        ),
        {"eid": nueva["examen_id"]},
    )
    tiempo, maxima = fila.fetchone()
    assert tiempo == 45
    assert float(maxima) == 10.0


@pytest.mark.asyncio
async def test_agregar_comision_adopta_al_original_en_el_lote(
    client_admin: AsyncClient, session: AsyncSession
):
    """El examen que estaba solo pasa a formar parte del lote junto con la réplica.

    Sin eso, el listado del examen original seguiría diciendo que se toma en una
    sola comisión.
    """
    datos = await _materia_con_examen(session)

    await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/comisiones",
        json={"comision_id": datos["comisiones"]["C2"]},
    )

    lotes = await session.execute(
        text("SELECT lote_replica_id::text FROM examen_contenido WHERE comision_id = ANY(:c)"),
        {"c": [datos["comisiones"]["C1"], datos["comisiones"]["C2"]]},
    )
    valores = {r[0] for r in lotes.fetchall()}
    assert len(valores) == 1
    assert valores != {None}

    # Y el listado, desde CUALQUIERA de los dos, muestra las dos comisiones.
    desde_original = await client_admin.get(
        f"/api/v1/exam-content/{datos['examen_id']}/comisiones"
    )
    assert desde_original.status_code == 200, desde_original.text
    assert {i["comision_codigo"] for i in desde_original.json()["items"]} == {"C1", "C2"}


@pytest.mark.asyncio
async def test_agregar_una_tercera_comision_reusa_el_lote(
    client_admin: AsyncClient, session: AsyncSession
):
    """TRIANGULATE: sumar C3 después no abre un lote nuevo, entra al que ya existe."""
    datos = await _materia_con_examen(session)

    await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/comisiones",
        json={"comision_id": datos["comisiones"]["C2"]},
    )
    await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/comisiones",
        json={"comision_id": datos["comisiones"]["C3"]},
    )

    listado = await client_admin.get(
        f"/api/v1/exam-content/{datos['examen_id']}/comisiones"
    )
    assert listado.status_code == 200, listado.text
    assert {i["comision_codigo"] for i in listado.json()["items"]} == {"C1", "C2", "C3"}


@pytest.mark.asyncio
async def test_el_titulo_de_la_replica_lleva_el_codigo_de_su_comision(
    client_admin: AsyncClient, session: AsyncSession
):
    """Mismo criterio que la creación multi-comisión, y sin renombrar al original.

    Un examen ya creado aparece en notas y en auditoría con su título: cambiárselo
    por agregar una comisión sería una sorpresa.
    """
    datos = await _materia_con_examen(session, titulo="Parcial 1")

    resp = await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/comisiones",
        json={"comision_id": datos["comisiones"]["C2"]},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["titulo"] == "Parcial 1 (C2)"

    original = await session.execute(
        text("SELECT titulo FROM examen_contenido WHERE id = :eid"),
        {"eid": datos["examen_id"]},
    )
    assert original.scalar_one() == "Parcial 1"


@pytest.mark.asyncio
async def test_el_sufijo_no_se_apila_sobre_un_titulo_que_ya_lo_tiene(
    client_admin: AsyncClient, session: AsyncSession
):
    """TRIANGULATE: partir de «Parcial 1 (C1)» da «Parcial 1 (C2)», no «Parcial 1 (C1) (C2)»."""
    datos = await _materia_con_examen(session, titulo="Parcial 1 (C1)")

    resp = await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/comisiones",
        json={"comision_id": datos["comisiones"]["C2"]},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["titulo"] == "Parcial 1 (C2)"


@pytest.mark.asyncio
async def test_agregar_dos_veces_la_misma_comision_se_rechaza(
    client_admin: AsyncClient, session: AsyncSession
):
    """Una comisión rinde el examen una sola vez: la segunda vez es un 409."""
    datos = await _materia_con_examen(session)

    primera = await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/comisiones",
        json={"comision_id": datos["comisiones"]["C2"]},
    )
    assert primera.status_code == 201, primera.text

    segunda = await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/comisiones",
        json={"comision_id": datos["comisiones"]["C2"]},
    )
    assert segunda.status_code == 409
    assert segunda.json()["detail"]["error"] == "comision_ya_incluida"

    # Y tampoco se puede agregar la comisión del propio examen.
    propia = await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/comisiones",
        json={"comision_id": datos["comisiones"]["C1"]},
    )
    assert propia.status_code == 409


@pytest.mark.asyncio
async def test_agregar_una_comision_de_otra_materia_se_rechaza(
    client_admin: AsyncClient, session: AsyncSession
):
    datos = await _materia_con_examen(session)
    ajenos = await _materia_con_examen(session)

    resp = await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/comisiones",
        json={"comision_id": ajenos["comisiones"]["C2"]},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "comision_de_otra_materia"


@pytest.mark.asyncio
async def test_quitar_una_comision_sin_intentos_la_saca_del_examen(
    client_admin: AsyncClient, session: AsyncSession
):
    """Si nadie rindió, la comisión sale del examen y se puede volver a agregar.

    El examen de esa comisión NO se borra: queda dado de baja y fuera del lote, así
    que se recupera desde el filtro "Dados de baja" si fue un error.
    """
    datos = await _materia_con_examen(session)

    agregada = await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/comisiones",
        json={"comision_id": datos["comisiones"]["C2"]},
    )
    replica_id = agregada.json()["examen_id"]

    quitada = await client_admin.delete(
        f"/api/v1/exam-content/{datos['examen_id']}/comisiones/{datos['comisiones']['C2']}"
    )
    assert quitada.status_code == 204, quitada.text

    listado = await client_admin.get(
        f"/api/v1/exam-content/{datos['examen_id']}/comisiones"
    )
    assert {i["comision_codigo"] for i in listado.json()["items"]} == {"C1"}

    fila = await session.execute(
        text(
            "SELECT eliminado_en IS NOT NULL, lote_replica_id IS NULL"
            " FROM examen_contenido WHERE id = :eid"
        ),
        {"eid": replica_id},
    )
    assert list(fila.fetchone()) == [True, True]

    # Y se puede volver a agregar.
    de_nuevo = await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/comisiones",
        json={"comision_id": datos["comisiones"]["C2"]},
    )
    assert de_nuevo.status_code == 201, de_nuevo.text


@pytest.mark.asyncio
async def test_no_se_puede_quitar_una_comision_que_ya_rindio(
    client_admin: AsyncClient, session: AsyncSession
):
    """Regla del dueño: con un intento rendido, la comisión no se quita.

    Sacarla dejaría el examen de esa comisión fuera del catálogo con evidencia
    viva colgando de él.
    """
    datos = await _materia_con_examen(session)

    agregada = await client_admin.post(
        f"/api/v1/exam-content/{datos['examen_id']}/comisiones",
        json={"comision_id": datos["comisiones"]["C2"]},
    )
    replica_id = agregada.json()["examen_id"]

    await session.execute(
        text(
            "INSERT INTO proctoring_session (id, modo, examen_contenido_id)"
            " VALUES (:id, 'examen', :eid)"
        ),
        {"id": str(uuid.uuid4()), "eid": replica_id},
    )
    await session.commit()

    resp = await client_admin.delete(
        f"/api/v1/exam-content/{datos['examen_id']}/comisiones/{datos['comisiones']['C2']}"
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "comision_con_intentos"

    # Sigue en el examen y sigue activa: no se tocó nada.
    listado = await client_admin.get(
        f"/api/v1/exam-content/{datos['examen_id']}/comisiones"
    )
    assert {i["comision_codigo"] for i in listado.json()["items"]} == {"C1", "C2"}
    activo = await session.execute(
        text("SELECT eliminado_en FROM examen_contenido WHERE id = :eid"),
        {"eid": replica_id},
    )
    assert activo.scalar_one() is None


@pytest.mark.asyncio
async def test_no_se_puede_quitar_la_unica_comision(
    client_admin: AsyncClient, session: AsyncSession
):
    """TRIANGULATE: quitar la última dejaría el examen sin ninguna comisión."""
    datos = await _materia_con_examen(session)

    resp = await client_admin.delete(
        f"/api/v1/exam-content/{datos['examen_id']}/comisiones/{datos['comisiones']['C1']}"
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "unica_comision"


@pytest.mark.asyncio
async def test_comisiones_de_un_examen_inexistente_404(
    client_admin: AsyncClient, session: AsyncSession
):
    resp = await client_admin.get(f"/api/v1/exam-content/{uuid.uuid4()}/comisiones")
    assert resp.status_code == 404
