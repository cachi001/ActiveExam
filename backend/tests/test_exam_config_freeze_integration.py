"""Integración del CANDADO de configuración del examen tras rendición.

Regla (pedido del owner): con >= 1 intento FINALIZADO, los campos de
mecánica/nota quedan CONGELADOS (409 config_congelada). Los controles de
publicación (mostrar_nota, revision_habilitada) siguen editables. El GET expone
`bloqueada` para que el front deshabilite.

DB real (DATABASE_URL). Sin mocks de DB (regla dura #4).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
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

# Solo campos que el PATCH acepta. `mezclar_preguntas` NO va: desde la migración
# 0046 es siempre true y el schema lo rechaza con 422 (`extra_forbidden`), esté el
# examen rendido o no. Mandarlo hacía fallar todos los PATCH de este módulo, y de
# paso rompía `test_rendido_acortar_cierre_409`: como el primer PATCH se caía con
# 422, el examen nunca quedaba con `cierre`, así que acortarlo después no apretaba
# nada y respondía 200 en vez de 409.
_CONFIG_VALIDA = {
    "tiempo_limite_min": 60,
    "intentos_permitidos": 2,
    "apertura": "2026-01-01T09:00:00+00:00",
    "cierre": "2026-12-31T20:00:00+00:00",
    "nota_maxima": 10.0,
    "nota_aprobacion": 6.0,
}


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


async def _crear_examen(factory) -> str:
    async with factory() as s:
        guardado = await ExamenContenidoSqlRepository(s).guardar(
            ExamenContenido(
                titulo="Examen",
                comision_id=None,
                preguntas=(
                    Pregunta(
                        enunciado="Q0",
                        tipo="multichoice",
                        orden=0,
                        opciones=(
                            OpcionRespuesta(texto="A", es_correcta=True, orden=0),
                            OpcionRespuesta(texto="B", es_correcta=False, orden=1),
                        ),
                    ),
                ),
            )
        )
        await s.commit()
    return guardado.id


async def _finalizar_intento(factory, examen_id: str) -> None:
    async with factory() as s:
        s.add(
            ProctoringSessionModel(
                modo="examen",
                examen_contenido_id=examen_id,
                finalizada_en=datetime.now(tz=timezone.utc),
            )
        )
        await s.commit()


@pytest.mark.asyncio
async def test_sin_rendicion_permite_editar_config_de_nota(app, factory):
    examen_id = await _crear_examen(factory)
    async with _admin_client(app) as c:
        r = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config",
            json={**_CONFIG_VALIDA, "nota_maxima": 20.0, "nota_aprobacion": 12.0},
        )
    assert r.status_code == 200, r.text
    assert r.json()["nota_maxima"] == 20.0
    assert r.json()["bloqueada"] is False


@pytest.mark.asyncio
async def test_rendido_congela_campo_de_nota_409(app, factory):
    examen_id = await _crear_examen(factory)
    async with _admin_client(app) as c:
        # Config inicial válida ANTES de rendir.
        await c.patch(f"/api/v1/exam-content/{examen_id}/config", json=_CONFIG_VALIDA)
    await _finalizar_intento(factory, examen_id)

    async with _admin_client(app) as c:
        r = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config",
            json={"nota_maxima": 20.0},
        )
    assert r.status_code == 409, r.text
    detalle = r.json()["detail"]
    assert detalle["error"] == "config_congelada"
    assert "nota_maxima" in detalle["campos"]


@pytest.mark.asyncio
async def test_rendido_permite_publicacion_de_resultados(app, factory):
    examen_id = await _crear_examen(factory)
    async with _admin_client(app) as c:
        await c.patch(f"/api/v1/exam-content/{examen_id}/config", json=_CONFIG_VALIDA)
    await _finalizar_intento(factory, examen_id)

    async with _admin_client(app) as c:
        r = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config",
            json={"mostrar_nota": "inmediata", "revision_habilitada": True},
        )
    assert r.status_code == 200, r.text
    assert r.json()["mostrar_nota"] == "inmediata"
    assert r.json()["revision_habilitada"] is True
    assert r.json()["bloqueada"] is True


@pytest.mark.asyncio
async def test_get_config_expone_bloqueada_tras_rendicion(app, factory):
    examen_id = await _crear_examen(factory)
    async with _admin_client(app) as c:
        await c.patch(f"/api/v1/exam-content/{examen_id}/config", json=_CONFIG_VALIDA)
        r_antes = await c.get(f"/api/v1/exam-content/{examen_id}/config")
    assert r_antes.json()["bloqueada"] is False

    await _finalizar_intento(factory, examen_id)
    async with _admin_client(app) as c:
        r_despues = await c.get(f"/api/v1/exam-content/{examen_id}/config")
    assert r_despues.json()["bloqueada"] is True


# ---------------------------------------------------------------------------
# C-72 sección 6 — candado DIRECCIONAL: cierre solo extender, intentos solo
# aumentar; congelado duro siempre; libres siempre. Reemplaza al binario.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rendido_permite_extender_cierre_200(app, factory):
    examen_id = await _crear_examen(factory)
    async with _admin_client(app) as c:
        await c.patch(f"/api/v1/exam-content/{examen_id}/config", json=_CONFIG_VALIDA)
    await _finalizar_intento(factory, examen_id)
    async with _admin_client(app) as c:
        r = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config",
            json={"cierre": "2027-06-30T20:00:00+00:00"},  # posterior al vigente (2026-12-31)
        )
    assert r.status_code == 200, r.text
    assert r.json()["cierre"].startswith("2027-06-30")


@pytest.mark.asyncio
async def test_rendido_acortar_cierre_409(app, factory):
    examen_id = await _crear_examen(factory)
    async with _admin_client(app) as c:
        await c.patch(f"/api/v1/exam-content/{examen_id}/config", json=_CONFIG_VALIDA)
    await _finalizar_intento(factory, examen_id)
    async with _admin_client(app) as c:
        r = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config",
            json={"cierre": "2026-06-30T20:00:00+00:00"},  # anterior al vigente → aprieta
        )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["error"] == "config_congelada"
    assert "cierre" in r.json()["detail"]["campos"]


@pytest.mark.asyncio
async def test_rendido_patch_mixto_congelado_y_libre_es_atomico(app, factory):
    examen_id = await _crear_examen(factory)
    async with _admin_client(app) as c:
        await c.patch(f"/api/v1/exam-content/{examen_id}/config", json=_CONFIG_VALIDA)
    await _finalizar_intento(factory, examen_id)
    async with _admin_client(app) as c:
        # nota_maxima (congelado duro) + revision_habilitada (libre) en el mismo PATCH
        r = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config",
            json={"nota_maxima": 20.0, "revision_habilitada": True},
        )
        assert r.status_code == 409, r.text
        assert "nota_maxima" in r.json()["detail"]["campos"]
        # atómico: el campo libre NO se persistió
        g = await c.get(f"/api/v1/exam-content/{examen_id}/config")
    assert g.json()["revision_habilitada"] is False


@pytest.mark.asyncio
async def test_get_config_expone_campos_congelados_y_ampliables(app, factory):
    examen_id = await _crear_examen(factory)
    async with _admin_client(app) as c:
        await c.patch(f"/api/v1/exam-content/{examen_id}/config", json=_CONFIG_VALIDA)
        # 6.12: sin rendiciones → ningún campo congelado
        antes = (await c.get(f"/api/v1/exam-content/{examen_id}/config")).json()
    assert antes["campos_congelados"] == []
    assert antes["campos_solo_ampliables"] == []

    await _finalizar_intento(factory, examen_id)
    async with _admin_client(app) as c:
        despues = (await c.get(f"/api/v1/exam-content/{examen_id}/config")).json()
    # 6.11: tras rendición, expone el detalle direccional
    assert "nota_maxima" in despues["campos_congelados"]
    assert set(despues["campos_solo_ampliables"]) == {"cierre", "intentos_permitidos"}
