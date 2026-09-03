"""Renombrar o dar de baja una categoría que ya se usó tiene que AVISAR.

Por qué existe
--------------
El resto del banco tiene guardas: dar de baja una pregunta que está en el pool de
un examen vigente devuelve 409. Las categorías no tienen ninguna. `PATCH
/categorias/{id}` devuelve 200 y `DELETE` devuelve 204 aunque la categoría sea la
de un examen que ya se rindió.

Bloquearlas sería peor que el problema: las preguntas del examen están COPIADAS
(`pregunta_examen`), así que renombrar o dar de baja una categoría **no cambia
ninguna nota** ni saca preguntas de un examen armado. Lo único que se degrada es
la trazabilidad: reconstruir de dónde salió cada pregunta de un examen rendido
pasa a mostrar el nombre nuevo, o una categoría que ya no está en el árbol.

Por eso la decisión fue AVISAR, NO BLOQUEAR:

- `GET /categorias/{id}/uso` dice en qué exámenes se usó la rama y cuáles ya se
  rindieron, para que la pantalla lo muestre ANTES de confirmar.
- El renombrado queda en el audit log con el nombre anterior. Sin eso, el aviso
  no sirve de nada: si nadie guarda cómo se llamaba, la trazabilidad se pierde
  igual.
- Renombrar y dar de baja siguen permitidos.

Los ENSAYOS no cuentan como rendición, igual que en el candado de config
(ver `test_ensayo_no_congela_el_examen.py`): dos partes del sistema no pueden
contar distinto lo mismo.

Contra DB REAL, sin mocks (regla dura de código #4).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    CategoriaPreguntaModel,
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaBancoModel,
    PreguntaExamenModel,
    TramoSorteoExamenModel,
)
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

pytestmark = pytest.mark.asyncio

# `audit_log` NO se dropea: la crea el hook del conftest y el renombrado escribe
# ahí. Dropearla dejaría el test verde por vacío en vez de por comportamiento.
_TABLAS = [
    "tramo_sorteo_examen",
    "proctoring_session",
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
        for nombre in _TABLAS:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{nombre}" CASCADE'))
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
                ProctoringSessionModel.__table__,
                TramoSorteoExamenModel.__table__,
            ],
        )
    yield eng
    async with eng.begin() as conn:
        for nombre in _TABLAS:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{nombre}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def client(factory):
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    app.include_router(
        create_exam_content_router(session_factory=factory),
        prefix="/api/v1/exam-content",
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["admin_sistema"], mfa=True),
    ) as c:
        yield c


@pytest_asyncio.fixture
async def session(factory):
    async with factory() as s:
        yield s
        await s.rollback()


async def _arbol(session: AsyncSession) -> tuple[str, str, str]:
    """Materia con `Unidad 1` → `Bloque A`. Devuelve (materia, padre, hija)."""
    mid = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO materia (id, codigo, nombre) VALUES (:id, :c, 'M')"),
        {"id": mid, "c": f"USO-{mid[:8]}"},
    )
    padre, hija = str(uuid.uuid4()), str(uuid.uuid4())
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
    await session.commit()
    return mid, padre, hija


async def _examen_con_pregunta_de(
    session: AsyncSession, categoria_id: str, *, titulo: str
) -> str:
    """Examen con una pregunta COPIADA que vino de esa categoría.

    `examen_contenido` no tiene `materia_id`: el vínculo con la materia pasa por
    la comisión. Lo que ata el examen a la categoría es la pregunta copiada.
    """
    eid = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO examen_contenido (id, titulo) VALUES (:id, :t)"),
        {"id": eid, "t": titulo},
    )
    await session.execute(
        text(
            "INSERT INTO pregunta_examen (id, examen_id, enunciado, tipo, categoria_id)"
            " VALUES (:id, :eid, 'Q', 'multichoice', :cid)"
        ),
        {"id": str(uuid.uuid4()), "eid": eid, "cid": categoria_id},
    )
    await session.commit()
    return eid


async def _sesion_finalizada(
    session: AsyncSession, examen_id: str, *, es_prueba: bool
) -> None:
    session.add(
        ProctoringSessionModel(
            modo="examen",
            examen_contenido_id=examen_id,
            finalizada_en=datetime.now(tz=timezone.utc),
            es_prueba=es_prueba,
        )
    )
    await session.commit()


async def _uso(client: AsyncClient, categoria_id: str) -> dict:
    r = await client.get(f"/api/v1/exam-content/categorias/{categoria_id}/uso")
    assert r.status_code == 200, r.text
    return r.json()


async def test_dice_en_que_examenes_se_uso_la_categoria(
    client: AsyncClient, session: AsyncSession
):
    _materia_id, padre, _hija = await _arbol(session)
    examen_id = await _examen_con_pregunta_de(session, padre, titulo="Parcial 1")

    uso = await _uso(client, padre)

    assert [e["examen_id"] for e in uso["examenes"]] == [examen_id]
    assert uso["examenes"][0]["titulo"] == "Parcial 1"
    assert uso["total_examenes"] == 1
    assert uso["aviso"], "se usó en un examen y no avisó nada"


async def test_una_categoria_sin_usar_no_avisa_nada(
    client: AsyncClient, session: AsyncSession
):
    """Triangulación: el aviso no puede aparecer siempre, o deja de significar algo."""
    _materia_id, padre, _hija = await _arbol(session)

    uso = await _uso(client, padre)

    assert uso["examenes"] == []
    assert uso["total_examenes"] == 0
    assert uso["examenes_rendidos"] == 0
    assert uso["aviso"] is None


async def test_marca_cual_de_los_examenes_ya_se_rindio(
    client: AsyncClient, session: AsyncSession
):
    """Es la diferencia que importa: sin rendir se puede reorganizar tranquilo."""
    _materia_id, padre, _hija = await _arbol(session)
    rendido = await _examen_con_pregunta_de(session, padre, titulo="Ya rendido")
    await _examen_con_pregunta_de(session, padre, titulo="Sin rendir")
    await _sesion_finalizada(session, rendido, es_prueba=False)

    uso = await _uso(client, padre)

    por_titulo = {e["titulo"]: e["rendido"] for e in uso["examenes"]}
    assert por_titulo == {"Ya rendido": True, "Sin rendir": False}
    assert uso["total_examenes"] == 2
    assert uso["examenes_rendidos"] == 1


async def test_un_ensayo_no_cuenta_como_rendido(
    client: AsyncClient, session: AsyncSession
):
    """Igual que el candado de config: el ensayo del docente no es una rendición."""
    _materia_id, padre, _hija = await _arbol(session)
    examen_id = await _examen_con_pregunta_de(session, padre, titulo="Solo ensayado")
    await _sesion_finalizada(session, examen_id, es_prueba=True)

    uso = await _uso(client, padre)

    assert uso["examenes"][0]["rendido"] is False
    assert uso["examenes_rendidos"] == 0


async def test_el_uso_de_una_subcategoria_cuenta_para_el_padre(
    client: AsyncClient, session: AsyncSession
):
    """Dar de baja el padre arrastra la rama entera, así que el aviso también."""
    _materia_id, padre, hija = await _arbol(session)
    examen_id = await _examen_con_pregunta_de(session, hija, titulo="Usa el Bloque A")

    uso = await _uso(client, padre)

    assert [e["examen_id"] for e in uso["examenes"]] == [examen_id]


async def test_tambien_cuenta_el_tramo_del_sorteo(
    client: AsyncClient, session: AsyncSession
):
    """Con sorteo por intento las preguntas se resuelven después: el vínculo con
    la categoría vive en el tramo, no en `pregunta_examen`."""
    _materia_id, padre, _hija = await _arbol(session)
    eid = str(uuid.uuid4())
    await session.execute(
        text("INSERT INTO examen_contenido (id, titulo) VALUES (:id, 'Sorteo por intento')"),
        {"id": eid},
    )
    session.add(
        TramoSorteoExamenModel(examen_id=eid, categoria_id=padre, cantidad=5)
    )
    await session.commit()

    uso = await _uso(client, padre)

    assert [e["examen_id"] for e in uso["examenes"]] == [eid]


async def test_renombrar_sigue_permitido_y_devuelve_el_aviso(
    client: AsyncClient, session: AsyncSession
):
    """AVISAR, NO BLOQUEAR: el 200 tiene que seguir siendo 200."""
    _materia_id, padre, _hija = await _arbol(session)
    examen_id = await _examen_con_pregunta_de(session, padre, titulo="Parcial 1")
    await _sesion_finalizada(session, examen_id, es_prueba=False)

    r = await client.patch(
        f"/api/v1/exam-content/categorias/{padre}", json={"nombre": "Unidad Uno"}
    )

    assert r.status_code == 200, r.text
    assert r.json()["nombre"] == "Unidad Uno"
    assert r.json()["aviso"], "renombró una categoría ya rendida sin avisar nada"


async def test_dar_de_baja_sigue_permitido(client: AsyncClient, session: AsyncSession):
    """Misma regla del otro lado: el aviso no puede convertirse en un candado."""
    _materia_id, padre, _hija = await _arbol(session)
    examen_id = await _examen_con_pregunta_de(session, padre, titulo="Parcial 1")
    await _sesion_finalizada(session, examen_id, es_prueba=False)

    r = await client.delete(f"/api/v1/exam-content/categorias/{padre}")

    assert r.status_code == 204, r.text


async def test_el_renombrado_queda_auditado_con_el_nombre_anterior(
    client: AsyncClient, session: AsyncSession
):
    """Sin esto el aviso no alcanza: si nadie guarda cómo se llamaba, la
    trazabilidad se pierde igual que si no hubiéramos avisado."""
    _materia_id, padre, _hija = await _arbol(session)

    r = await client.patch(
        f"/api/v1/exam-content/categorias/{padre}", json={"nombre": "Unidad Uno"}
    )
    assert r.status_code == 200, r.text

    fila = await session.execute(
        text(
            "SELECT accion, proposito FROM audit_log"
            " WHERE entidad_id = :id ORDER BY timestamp DESC LIMIT 1"
        ),
        {"id": padre},
    )
    entrada = fila.first()
    assert entrada is not None, "renombrar una categoría no dejó rastro"
    assert entrada.accion == "categoria_banco.edicion"
    assert "Unidad 1" in entrada.proposito, "no guardó el nombre anterior"
    assert "Unidad Uno" in entrada.proposito


async def test_uso_de_una_categoria_que_no_existe_da_404(client: AsyncClient):
    r = await client.get(f"/api/v1/exam-content/categorias/{uuid.uuid4()}/uso")
    assert r.status_code == 404, r.text
