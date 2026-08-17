"""Pool de preguntas seleccionables (C-69, opción B) — endpoints admin.

El examen importado es un POOL; el docente elige CUÁLES preguntas lo forman.

Endpoints (admin-only, SIN MFA — guard a nivel router, igual que el import):
- GET   /api/v1/exam-content/{examen_id}/preguntas            → todo el pool.
- PATCH /api/v1/exam-content/{examen_id}/preguntas-seleccion  → fija la selección.

D3: es_correcta NUNCA expuesta — el docente identifica la pregunta por enunciado.
DB real (DATABASE_URL).
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.exam_content.entities import (
    ExamenContenido,
    OpcionRespuesta,
    Pregunta,
)
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ExamenContenidoModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.models.proctoring import (  # noqa: F401
    ProctoringSessionModel,
)
from app.infrastructure.persistence.repositories.exam_content import (
    ExamenContenidoSqlRepository,
)
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_TABLES_TO_DROP = [
    "proctoring_session",
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
]
_TABLES_TO_CREATE = [
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
    application = FastAPI()
    application.state.jwt_validator = _build_test_jwt_validator()
    application.include_router(
        create_exam_content_router(session_factory=factory, writeback_svc=None),
        prefix="/api/v1/exam-content",
    )
    return application


def _admin_client(app):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["admin_sistema"]),
    )


def _examen(titulo: str, n: int) -> ExamenContenido:
    return ExamenContenido(
        titulo=titulo,
        comision_id=None,
        preguntas=tuple(
            Pregunta(
                enunciado=f"Enunciado {i}",
                tipo="multichoice",
                orden=i,
                opciones=(
                    OpcionRespuesta(texto="A", es_correcta=True, orden=0),
                    OpcionRespuesta(texto="B", es_correcta=False, orden=1),
                ),
            )
            for i in range(n)
        ),
    )


async def _crear_examen(factory, n: int = 3) -> tuple[str, list[str]]:
    """Crea un examen con n preguntas (todas seleccionadas por default).

    Devuelve (examen_id, [pregunta_ids ordenados por orden]).
    """
    async with factory() as s:
        repo = ExamenContenidoSqlRepository(s)
        guardado = await repo.guardar(_examen("Pool", n))
        await s.commit()
    ids = [p.id for p in sorted(guardado.preguntas, key=lambda p: p.orden)]
    return guardado.id, ids


async def _finalizar_intento(factory, examen_id: str) -> None:
    """Inserta una sesión de examen YA FINALIZADA vinculada al examen.

    Congela la selección (política: bloqueo al primer intento finalizado).
    """
    from datetime import datetime, timezone

    async with factory() as s:
        s.add(
            ProctoringSessionModel(
                modo="examen",
                examen_contenido_id=examen_id,
                finalizada_en=datetime.now(tz=timezone.utc),
            )
        )
        await s.commit()


# ---------------------------------------------------------------------------
# GET /{examen_id}/preguntas
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listar_pool_devuelve_todo_con_flags(app, factory):
    examen_id, ids = await _crear_examen(factory, n=3)
    async with _admin_client(app) as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/preguntas")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 3
    assert body["seleccionadas"] == 3  # recién importadas → todas seleccionadas
    assert [item["id"] for item in body["items"]] == ids
    for item in body["items"]:
        assert set(item.keys()) == {"id", "enunciado", "tipo", "orden", "seleccionada"}
        assert item["seleccionada"] is True


@pytest.mark.asyncio
async def test_listar_pool_no_expone_es_correcta(app, factory):
    examen_id, _ids = await _crear_examen(factory, n=2)
    async with _admin_client(app) as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/preguntas")
    assert resp.status_code == 200, resp.text
    assert "es_correcta" not in resp.text
    assert "opciones" not in resp.text


@pytest.mark.asyncio
async def test_listar_pool_examen_inexistente_404(app):
    async with _admin_client(app) as c:
        resp = await c.get(
            "/api/v1/exam-content/00000000-0000-0000-0000-000000000000/preguntas"
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_listar_pool_admin_only(app, factory):
    examen_id, _ids = await _crear_examen(factory, n=2)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["estudiante"]),
    ) as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/preguntas")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /{examen_id}/preguntas-seleccion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seleccion_setea_true_a_dadas_y_false_al_resto(app, factory):
    examen_id, ids = await _crear_examen(factory, n=4)
    elegidas = [ids[0], ids[2]]
    async with _admin_client(app) as c:
        resp = await c.patch(
            f"/api/v1/exam-content/{examen_id}/preguntas-seleccion",
            json={"seleccionadas": elegidas},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 4
    assert body["seleccionadas"] == 2
    estado = {item["id"]: item["seleccionada"] for item in body["items"]}
    assert estado[ids[0]] is True
    assert estado[ids[2]] is True
    assert estado[ids[1]] is False
    assert estado[ids[3]] is False

    # Persistido en la DB
    async with factory() as s:
        rows = (
            await s.execute(
                select(PreguntaExamenModel.id, PreguntaExamenModel.seleccionada).where(
                    PreguntaExamenModel.examen_id == examen_id
                )
            )
        ).all()
    persistido = {pid: sel for pid, sel in rows}
    assert persistido[ids[0]] is True
    assert persistido[ids[1]] is False


@pytest.mark.asyncio
async def test_seleccion_lista_vacia_422(app, factory):
    examen_id, _ids = await _crear_examen(factory, n=3)
    async with _admin_client(app) as c:
        resp = await c.patch(
            f"/api/v1/exam-content/{examen_id}/preguntas-seleccion",
            json={"seleccionadas": []},
        )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_seleccion_solo_ids_ajenos_422_y_no_muta(app, factory):
    examen_id, ids = await _crear_examen(factory, n=3)
    # Todas siguen seleccionadas; mandamos solo un id de otro examen → 0 válidas.
    async with _admin_client(app) as c:
        resp = await c.patch(
            f"/api/v1/exam-content/{examen_id}/preguntas-seleccion",
            json={"seleccionadas": ["11111111-1111-1111-1111-111111111111"]},
        )
    assert resp.status_code == 422, resp.text

    # No mutó: las 3 siguen seleccionadas (rollback).
    async with factory() as s:
        rows = (
            await s.execute(
                select(PreguntaExamenModel.seleccionada).where(
                    PreguntaExamenModel.examen_id == examen_id
                )
            )
        ).scalars().all()
    assert all(rows) and len(rows) == 3


@pytest.mark.asyncio
async def test_seleccion_ignora_ids_de_otro_examen(app, factory):
    examen_id, ids = await _crear_examen(factory, n=3)
    _otro_id, otros_ids = await _crear_examen(factory, n=2)
    # Mezcla: 1 id válido de este examen + 1 id del otro examen.
    async with _admin_client(app) as c:
        resp = await c.patch(
            f"/api/v1/exam-content/{examen_id}/preguntas-seleccion",
            json={"seleccionadas": [ids[1], otros_ids[0]]},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Solo el id válido de este examen quedó seleccionado.
    assert body["seleccionadas"] == 1
    estado = {item["id"]: item["seleccionada"] for item in body["items"]}
    assert estado[ids[1]] is True
    assert estado[ids[0]] is False
    # El otro examen no fue tocado.
    async with factory() as s:
        rows = (
            await s.execute(
                select(PreguntaExamenModel.seleccionada).where(
                    PreguntaExamenModel.examen_id == _otro_id
                )
            )
        ).scalars().all()
    assert all(rows)


@pytest.mark.asyncio
async def test_seleccion_examen_inexistente_404(app):
    async with _admin_client(app) as c:
        resp = await c.patch(
            "/api/v1/exam-content/00000000-0000-0000-0000-000000000000/preguntas-seleccion",
            json={"seleccionadas": ["x"]},
        )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_seleccion_extra_forbid_422(app, factory):
    examen_id, ids = await _crear_examen(factory, n=2)
    async with _admin_client(app) as c:
        resp = await c.patch(
            f"/api/v1/exam-content/{examen_id}/preguntas-seleccion",
            json={"seleccionadas": [ids[0]], "campo_extra": "x"},
        )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_seleccion_bloqueada_por_intento_finalizado_409(app, factory):
    """Con un intento FINALIZADO, cambiar la selección devuelve 409 y NO muta."""
    examen_id, ids = await _crear_examen(factory, n=3)
    await _finalizar_intento(factory, examen_id)
    async with _admin_client(app) as c:
        resp = await c.patch(
            f"/api/v1/exam-content/{examen_id}/preguntas-seleccion",
            json={"seleccionadas": [ids[0]]},
        )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"] == "seleccion_bloqueada"
    # No mutó: las 3 siguen seleccionadas (no se aplicó el cambio a solo ids[0]).
    async with factory() as s:
        rows = (
            await s.execute(
                select(PreguntaExamenModel.seleccionada).where(
                    PreguntaExamenModel.examen_id == examen_id
                )
            )
        ).scalars().all()
    assert all(rows) and len(rows) == 3


@pytest.mark.asyncio
async def test_pool_flag_bloqueada_refleja_intento_finalizado(app, factory):
    """GET /preguntas expone bloqueada=false antes de rendir y true tras finalizar."""
    examen_id, _ids = await _crear_examen(factory, n=3)
    async with _admin_client(app) as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/preguntas")
    assert resp.status_code == 200, resp.text
    assert resp.json()["bloqueada"] is False

    await _finalizar_intento(factory, examen_id)
    async with _admin_client(app) as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/preguntas")
    assert resp.status_code == 200, resp.text
    assert resp.json()["bloqueada"] is True


@pytest.mark.asyncio
async def test_seleccion_no_bloqueada_por_sesion_en_vivo(app, factory):
    """Una sesión SIN finalizar (en vivo) NO bloquea: se puede seguir ajustando."""
    examen_id, ids = await _crear_examen(factory, n=3)
    async with factory() as s:
        s.add(ProctoringSessionModel(modo="examen", examen_contenido_id=examen_id))
        await s.commit()
    async with _admin_client(app) as c:
        resp = await c.patch(
            f"/api/v1/exam-content/{examen_id}/preguntas-seleccion",
            json={"seleccionadas": [ids[0]]},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["seleccionadas"] == 1


@pytest.mark.asyncio
async def test_seleccion_admin_only(app, factory):
    examen_id, ids = await _crear_examen(factory, n=2)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["estudiante"]),
    ) as c:
        resp = await c.patch(
            f"/api/v1/exam-content/{examen_id}/preguntas-seleccion",
            json={"seleccionadas": [ids[0]]},
        )
    assert resp.status_code == 403
