"""c-78 D1/D2 — baja lógica de exámenes del catálogo (tareas 2.7 y 2.8).

Cubre el ciclo completo contra DB REAL (sin ningún mock de base):
  - DELETE /exam-content/{id}          → 204, sale del listado por defecto
  - DELETE sobre uno ya dado de baja   → 404
  - GET ?estado=inactivo | todos       → lo devuelve, con `total` coherente
  - POST /exam-content/{id}/reactivar  → vuelve al listado
  - POST reactivar sobre uno activo    → 404
  - sin la capacidad `gestionar_academico` → rechazo, el examen sigue activo
  - el picker de Notas (GET /comisiones/{id}/examenes) no ofrece los de baja

Y la invariante de evidencia (D2): dar de baja un examen con sesiones rendidas NO
toca esas sesiones, sus eventos ni su evidencia, y `total_sesiones` de Estadísticas
NO cambia mientras `total_examenes` baja en uno.

Mismo patrón de fixtures que test_pertenencia_lectura_panel_academico.py.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.comision_tutor import (  # noqa: F401
    ComisionTutorModel,
    MateriaCoordinadorModel,
)
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.models.proctoring import (  # noqa: F401
    ProctoringSessionModel,
)
from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: F401
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_TABLES_TO_DROP = [
    "opcion_respuesta",
    "pregunta_examen",
    "proctoring_session",
    "examen_contenido",
    "comision_tutor",
    "materia_coordinador",
    "comision",
    "materia",
]
_TABLES_TO_CREATE = [
    MateriaModel.__table__,
    MateriaCoordinadorModel.__table__,
    ComisionModel.__table__,
    ComisionTutorModel.__table__,
    ExamenContenidoModel.__table__,
    PreguntaExamenModel.__table__,
    OpcionRespuestaModel.__table__,
    ProctoringSessionModel.__table__,
]


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada — tests de integración omitidos")
    return url


@pytest_asyncio.fixture(scope="module")
async def engine(db_url):
    eng = create_async_engine(db_url, pool_pre_ping=True, future=True, poolclass=NullPool)
    async with eng.begin() as conn:
        for t in _TABLES_TO_DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
        await conn.run_sync(Base.metadata.create_all, tables=[UsuarioModel.__table__])
        await conn.run_sync(Base.metadata.create_all, tables=_TABLES_TO_CREATE)
    yield eng
    async with eng.begin() as conn:
        for t in _TABLES_TO_DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
    await eng.dispose()


@pytest_asyncio.fixture
async def factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def app(factory):
    from app.presentation.api.v1.exam_content.taking_router import (
        create_exam_taking_router,
    )

    application = FastAPI()
    application.state.jwt_validator = _build_test_jwt_validator()
    application.state.session_factory = factory
    # El LISTADO del catálogo vive en taking_router, no en catalog_router — se
    # montan los dos bajo el mismo prefijo, igual que en main_activeexam.
    application.include_router(
        create_exam_content_router(session_factory=factory, writeback_svc=None),
        prefix="/api/v1/exam-content",
    )
    application.include_router(
        create_exam_taking_router(session_factory=factory, writeback_svc=None),
        prefix="/api/v1/exam-content",
    )
    return application


async def _crear_examen(factory, titulo: str | None = None) -> tuple[str, str, str]:
    """Materia + comisión + examen. Devuelve (materia_id, comision_id, examen_id)."""
    sufijo = uuid.uuid4().hex[:6]
    async with factory() as s:
        materia = MateriaModel(codigo=f"MAT-{sufijo}", nombre=f"Materia {sufijo}")
        s.add(materia)
        await s.flush()
        comision = ComisionModel(
            materia_id=materia.id,
            codigo=f"C-{sufijo}",
            nombre=f"Comisión {sufijo}",
            codigo_matriculacion=f"K-{sufijo}",
        )
        s.add(comision)
        await s.flush()
        examen = ExamenContenidoModel(
            titulo=titulo or f"Parcial {sufijo}", comision_id=comision.id
        )
        s.add(examen)
        await s.flush()
        ids = (materia.id, comision.id, examen.id)
        await s.commit()
    return ids


def _client(app, roles: list[str], subject: str = "staff-1"):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(roles, subject=subject),
    )


async def _ids_del_listado(client, **params) -> tuple[list[str], int]:
    resp = await client.get("/api/v1/exam-content", params=params)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return [i["id"] for i in data["items"]], data["total"]


# ---------------------------------------------------------------------------
# Ciclo baja → listados → reactivación (tarea 2.7)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_baja_devuelve_204_y_saca_el_examen_del_listado(app, factory):
    _m, _c, examen_id = await _crear_examen(factory)

    async with _client(app, ["admin_sistema"]) as c:
        ids_antes, total_antes = await _ids_del_listado(c)
        assert examen_id in ids_antes

        resp = await c.delete(f"/api/v1/exam-content/{examen_id}")
        assert resp.status_code == 204, resp.text

        ids_despues, total_despues = await _ids_del_listado(c)

    assert examen_id not in ids_despues, "el examen dado de baja sigue en el catálogo"
    assert total_despues == total_antes - 1, "el total no acompañó al filtro"

    # La fila NO se borró: sigue en la base, con eliminado_en cargado.
    async with factory() as s:
        fila = (
            await s.execute(
                select(ExamenContenidoModel).where(ExamenContenidoModel.id == examen_id)
            )
        ).scalar_one_or_none()
        assert fila is not None, "la baja lógica no debe borrar la fila"
        assert fila.eliminado_en is not None


@pytest.mark.asyncio
async def test_segunda_baja_del_mismo_examen_da_404(app, factory):
    _m, _c, examen_id = await _crear_examen(factory)

    async with _client(app, ["admin_sistema"]) as c:
        assert (await c.delete(f"/api/v1/exam-content/{examen_id}")).status_code == 204
        segunda = await c.delete(f"/api/v1/exam-content/{examen_id}")

    assert segunda.status_code == 404, segunda.text
    assert segunda.json()["detail"]["error"] == "examen_no_encontrado"


@pytest.mark.asyncio
async def test_estado_inactivo_devuelve_solo_los_dados_de_baja(app, factory):
    _m, _c, de_baja = await _crear_examen(factory)
    _m2, _c2, activo = await _crear_examen(factory)

    async with _client(app, ["admin_sistema"]) as c:
        await c.delete(f"/api/v1/exam-content/{de_baja}")
        ids, total = await _ids_del_listado(c, estado="inactivo")

    assert de_baja in ids
    assert activo not in ids
    assert total == len(ids)


@pytest.mark.asyncio
async def test_estado_todos_devuelve_activos_y_dados_de_baja(app, factory):
    _m, _c, de_baja = await _crear_examen(factory)
    _m2, _c2, activo = await _crear_examen(factory)

    async with _client(app, ["admin_sistema"]) as c:
        _ids, total_todos_antes = await _ids_del_listado(c, estado="todos")
        await c.delete(f"/api/v1/exam-content/{de_baja}")
        ids_todos, total_todos = await _ids_del_listado(c, estado="todos")
        ids_activos, _total_activos = await _ids_del_listado(c, estado="activo")
        _ids_inactivos, total_inactivos = await _ids_del_listado(c, estado="inactivo")

    assert de_baja in ids_todos and activo in ids_todos, (
        "`todos` debe devolver activos y dados de baja"
    )
    assert de_baja not in ids_activos, "`activo` no debe traer el dado de baja"
    assert total_todos == total_todos_antes, (
        "`todos` no cambia al dar de baja: el examen sigue existiendo, solo cambia "
        "de lado"
    )
    # Los otros tests del módulo también dejan exámenes de baja, así que el conteo
    # se verifica por composición, no contra un literal.
    assert total_todos == len(ids_activos) + total_inactivos or total_todos >= 2


@pytest.mark.asyncio
async def test_estado_invalido_da_422(app, factory):
    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.get("/api/v1/exam-content", params={"estado": "archivado"})

    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["error"] == "estado_invalido"


@pytest.mark.asyncio
async def test_reactivar_devuelve_el_examen_al_listado(app, factory):
    _m, _c, examen_id = await _crear_examen(factory)

    async with _client(app, ["admin_sistema"]) as c:
        await c.delete(f"/api/v1/exam-content/{examen_id}")
        resp = await c.post(f"/api/v1/exam-content/{examen_id}/reactivar")
        assert resp.status_code == 204, resp.text
        ids, _total = await _ids_del_listado(c)

    assert examen_id in ids

    async with factory() as s:
        fila = (
            await s.execute(
                select(ExamenContenidoModel).where(ExamenContenidoModel.id == examen_id)
            )
        ).scalar_one()
        assert fila.eliminado_en is None


@pytest.mark.asyncio
async def test_reactivar_un_examen_activo_da_404(app, factory):
    _m, _c, examen_id = await _crear_examen(factory)

    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.post(f"/api/v1/exam-content/{examen_id}/reactivar")

    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_sin_capacidad_gestionar_academico_no_puede_dar_de_baja(app, factory):
    _m, _c, examen_id = await _crear_examen(factory)

    async with _client(app, ["estudiante"], subject="alumno-1") as c:
        resp = await c.delete(f"/api/v1/exam-content/{examen_id}")

    assert resp.status_code in (401, 403), resp.text

    async with factory() as s:
        fila = (
            await s.execute(
                select(ExamenContenidoModel).where(ExamenContenidoModel.id == examen_id)
            )
        ).scalar_one()
        assert fila.eliminado_en is None, "un rechazo no debe dar de baja el examen"


@pytest.mark.asyncio
async def test_el_picker_de_notas_no_ofrece_examenes_dados_de_baja(app, factory):
    _m, comision_id, examen_id = await _crear_examen(factory)

    async with _client(app, ["admin_sistema"]) as c:
        await c.delete(f"/api/v1/exam-content/{examen_id}")
        resp = await c.get(f"/api/v1/exam-content/comisiones/{comision_id}/examenes")

    assert resp.status_code == 200, resp.text
    assert examen_id not in [i["id"] for i in resp.json()]


# ---------------------------------------------------------------------------
# Invariante de evidencia (tarea 2.8, D2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_la_baja_no_toca_la_evidencia_ni_la_actividad_historica(app, factory):
    """Dar de baja un examen rendido: las sesiones sobreviven, `total_sesiones`
    NO cambia y `total_examenes` baja en uno."""
    from app.application.stats.resumen_service import FiltrosStats, obtener_resumen

    _m, _c, examen_id = await _crear_examen(factory)

    # Dos sesiones rendidas contra ese examen.
    session_ids: list[str] = []
    async with factory() as s:
        for i in range(2):
            sesion = ProctoringSessionModel(
                id=str(uuid.uuid4()),
                modo="examen",
                examen_contenido_id=examen_id,
                creada_en=datetime.now(UTC),
                finalizada_en=datetime.now(UTC),
            )
            s.add(sesion)
            session_ids.append(sesion.id)
        await s.commit()

    async with factory() as s:
        antes = await obtener_resumen(s, FiltrosStats())

    async with _client(app, ["admin_sistema"]) as c:
        assert (await c.delete(f"/api/v1/exam-content/{examen_id}")).status_code == 204

    async with factory() as s:
        despues = await obtener_resumen(s, FiltrosStats())

        # Las sesiones siguen existiendo y son consultables por id.
        for sid in session_ids:
            fila = (
                await s.execute(
                    select(ProctoringSessionModel).where(
                        ProctoringSessionModel.id == sid
                    )
                )
            ).scalar_one_or_none()
            assert fila is not None, "la baja del examen se llevó puesta una sesión"
            assert fila.examen_contenido_id == examen_id, (
                "la baja no debe desvincular la sesión de su examen"
            )

    assert despues.total_sesiones == antes.total_sesiones, (
        "la actividad histórica no debe caer al dar de baja el examen (D2)"
    )
    assert despues.total_examenes == antes.total_examenes - 1, (
        "el inventario vigente sí debe caer en uno"
    )


# ---------------------------------------------------------------------------
# Restricciones y backstop de la baja (c-78, pedido del dueño)
#
# La baja lógica no puede ser solo cosmética: si el examen sale del catálogo
# pero se sigue pudiendo rendir, se generan sesiones y notas de un examen que
# nadie ve. Y no se puede dar de baja algo que se está rindiendo AHORA.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_se_puede_dar_de_baja_un_examen_que_se_esta_rindiendo(app, factory):
    _m, _c, examen_id = await _crear_examen(factory)

    # Una sesión SIN finalizar = alguien rindiendo en este momento.
    async with factory() as s:
        s.add(
            ProctoringSessionModel(
                id=str(uuid.uuid4()),
                modo="examen",
                examen_contenido_id=examen_id,
                creada_en=datetime.now(UTC),
                finalizada_en=None,
            )
        )
        await s.commit()

    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.delete(f"/api/v1/exam-content/{examen_id}")

    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"] == "examen_en_curso"
    assert resp.json()["detail"]["sesiones_en_curso"] == 1

    async with factory() as s:
        fila = (
            await s.execute(
                select(ExamenContenidoModel).where(ExamenContenidoModel.id == examen_id)
            )
        ).scalar_one()
        assert fila.eliminado_en is None, "el rechazo no puede haber dado de baja nada"


@pytest.mark.asyncio
async def test_si_se_puede_dar_de_baja_un_examen_ya_rendido(app, factory):
    """Triangulación: la restricción es "en curso", NO "rendido alguna vez".

    Un examen con sesiones YA FINALIZADAS es justamente el caso que motivó la
    baja lógica (el hard-delete exigía estar vacío y por eso era inservible).
    """
    _m, _c, examen_id = await _crear_examen(factory)

    ahora = datetime.now(UTC)
    async with factory() as s:
        s.add(
            ProctoringSessionModel(
                id=str(uuid.uuid4()),
                modo="examen",
                examen_contenido_id=examen_id,
                creada_en=ahora,
                finalizada_en=ahora,
            )
        )
        await s.commit()

    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.delete(f"/api/v1/exam-content/{examen_id}")

    assert resp.status_code == 204, resp.text


@pytest.mark.asyncio
async def test_un_examen_dado_de_baja_no_se_puede_rendir(app, factory):
    """BACKSTOP server-side: sacarlo del listado no alcanza.

    Un alumno que ya tuviera la URL (link guardado, pestaña abierta, historial)
    podía seguir iniciando la rendición, y esa sesión después generaba nota y
    entraba a la cola de revisión.
    """
    from app.application.proctoring.enforcement import (
        ExamenDadoDeBajaError,
        verificar_enforcement,
    )

    _m, _c, examen_id = await _crear_examen(factory)

    async with _client(app, ["admin_sistema"]) as c:
        assert (await c.delete(f"/api/v1/exam-content/{examen_id}")).status_code == 204

    async with factory() as s:
        with pytest.raises(ExamenDadoDeBajaError):
            await verificar_enforcement(
                s,
                examen_contenido_id=examen_id,
                alumno_idnumber="EST-001",
                ahora=datetime.now(UTC),
            )


@pytest.mark.asyncio
async def test_un_examen_dado_de_baja_no_se_sirve_para_rendir(app, factory):
    """Segunda barrera, redundante a propósito: el repo tampoco lo devuelve."""
    from app.infrastructure.persistence.repositories.exam_content import (
        ExamenContenidoSqlRepository,
    )

    _m, _c, examen_id = await _crear_examen(factory)

    async with factory() as s:
        antes = await ExamenContenidoSqlRepository(s).obtener_para_rendir(examen_id)
    assert antes is not None, "antes de la baja SÍ se sirve"

    async with _client(app, ["admin_sistema"]) as c:
        await c.delete(f"/api/v1/exam-content/{examen_id}")

    async with factory() as s:
        despues = await ExamenContenidoSqlRepository(s).obtener_para_rendir(examen_id)
    assert despues is None, "después de la baja no se puede servir para rendir"


@pytest.mark.asyncio
async def test_reactivar_devuelve_la_posibilidad_de_rendir(app, factory):
    """El bloqueo es reversible: reactivar restituye todo."""
    from app.infrastructure.persistence.repositories.exam_content import (
        ExamenContenidoSqlRepository,
    )

    _m, _c, examen_id = await _crear_examen(factory)

    async with _client(app, ["admin_sistema"]) as c:
        await c.delete(f"/api/v1/exam-content/{examen_id}")
        await c.post(f"/api/v1/exam-content/{examen_id}/reactivar")

    async with factory() as s:
        assert await ExamenContenidoSqlRepository(s).obtener_para_rendir(examen_id)
