"""c-78 §12 (E-01/E-02, D9/D10) — visibilidad de la nota y de los eventos.

Bloque A (PURO): la regla de que publicar es camino de IDA y qué ve el alumno
con cada valor de `mostrar_nota`.

Bloque B (DB real): el default `nunca` de todo examen nuevo, la acción
"Publicar notas ahora" (con su 409 al repetirla), el rechazo del retroceso desde
el PATCH de config, y el flag por examen de los eventos de proctoring.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.exam_content.visibilidad import (
    MOSTRAR_NOTA_AL_CERRAR,
    MOSTRAR_NOTA_INMEDIATA,
    MOSTRAR_NOTA_NUNCA,
    nota_visible,
    revision_visible,
    transicion_visibilidad_permitida,
)
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.comision_tutor import (  # noqa: F401
    ComisionTutorModel,
    MateriaCoordinadorModel,
    MateriaProfesorModel,
)
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.models.transactional import UsuarioModel  # noqa: F401
from app.presentation.api.v1.exam_content.router import create_exam_content_router
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

# ===========================================================================
# Bloque A — reglas puras
# ===========================================================================

_AHORA = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
_YA_CERRO = _AHORA - timedelta(hours=1)
_NO_CERRO = _AHORA + timedelta(hours=1)


def test_nunca_oculta_la_nota_aunque_el_examen_ya_haya_cerrado():
    """Es la diferencia con 'al_cerrar': el cierre NO publica solo."""
    assert not nota_visible(
        mostrar_nota=MOSTRAR_NOTA_NUNCA, cierre=_YA_CERRO, ahora=_AHORA
    )


def test_al_cerrar_publica_recien_despues_del_cierre():
    assert nota_visible(
        mostrar_nota=MOSTRAR_NOTA_AL_CERRAR, cierre=_YA_CERRO, ahora=_AHORA
    )
    assert not nota_visible(
        mostrar_nota=MOSTRAR_NOTA_AL_CERRAR, cierre=_NO_CERRO, ahora=_AHORA
    )


def test_inmediata_publica_siempre():
    assert nota_visible(
        mostrar_nota=MOSTRAR_NOTA_INMEDIATA, cierre=_NO_CERRO, ahora=_AHORA
    )


def test_la_revision_nunca_se_muestra_antes_que_la_nota():
    """Con 'nunca' no hay revisión aunque esté habilitada: filtraría respuestas."""
    assert not revision_visible(
        revision_habilitada=True,
        mostrar_nota=MOSTRAR_NOTA_NUNCA,
        cierre=_YA_CERRO,
        ahora=_AHORA,
    )


def test_la_visibilidad_avanza_pero_no_retrocede():
    # Hacia adelante: permitido.
    assert transicion_visibilidad_permitida(MOSTRAR_NOTA_NUNCA, MOSTRAR_NOTA_AL_CERRAR)
    assert transicion_visibilidad_permitida(MOSTRAR_NOTA_NUNCA, MOSTRAR_NOTA_INMEDIATA)
    assert transicion_visibilidad_permitida(
        MOSTRAR_NOTA_AL_CERRAR, MOSTRAR_NOTA_INMEDIATA
    )
    # Hacia atrás: bloqueado.
    assert not transicion_visibilidad_permitida(
        MOSTRAR_NOTA_INMEDIATA, MOSTRAR_NOTA_NUNCA
    )
    assert not transicion_visibilidad_permitida(
        MOSTRAR_NOTA_INMEDIATA, MOSTRAR_NOTA_AL_CERRAR
    )
    assert not transicion_visibilidad_permitida(
        MOSTRAR_NOTA_AL_CERRAR, MOSTRAR_NOTA_NUNCA
    )
    # Quedarse igual: permitido (un PATCH que reenvía la config no puede fallar).
    for valor in (MOSTRAR_NOTA_NUNCA, MOSTRAR_NOTA_AL_CERRAR, MOSTRAR_NOTA_INMEDIATA):
        assert transicion_visibilidad_permitida(valor, valor)


def test_un_valor_desconocido_se_trata_como_el_mas_restrictivo():
    """Fail-closed: ante un dato que no entendemos, la nota no se muestra."""
    assert not nota_visible(mostrar_nota="???", cierre=_YA_CERRO, ahora=_AHORA)


# ===========================================================================
# Bloque B — endpoints (DB real)
# ===========================================================================

pytestmark_db = pytest.mark.asyncio

_TABLES_TO_DROP = [
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "comision_tutor",
    "materia_coordinador",
    "materia_profesor",
    "comision",
    "materia",
]
_TABLES_TO_CREATE = [
    MateriaModel.__table__,
    MateriaCoordinadorModel.__table__,
    MateriaProfesorModel.__table__,
    ComisionModel.__table__,
    ComisionTutorModel.__table__,
    ExamenContenidoModel.__table__,
    PreguntaExamenModel.__table__,
    OpcionRespuestaModel.__table__,
]

_CONFIG_BASE = {
    "apertura": "2026-09-01T09:00:00+00:00",
    "cierre": "2026-09-01T11:00:00+00:00",
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
    application = FastAPI()
    application.state.jwt_validator = _build_test_jwt_validator()
    application.state.session_factory = factory
    application.include_router(
        create_exam_content_router(session_factory=factory, writeback_svc=None),
        prefix="/api/v1/exam-content",
    )
    return application


async def _crear_examen(factory) -> str:
    """Examen creado SIN tocar la visibilidad (usa el default de la columna)."""
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
        examen = ExamenContenidoModel(titulo=f"Parcial {sufijo}", comision_id=comision.id)
        s.add(examen)
        await s.flush()
        examen_id = examen.id
        await s.commit()
    return examen_id


def _admin(app):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["admin_sistema"], subject="staff-c78"),
    )


@pytest.mark.asyncio
async def test_un_examen_nuevo_nace_con_la_nota_oculta(app, factory):
    examen_id = await _crear_examen(factory)

    async with _admin(app) as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/config")

    assert resp.status_code == 200, resp.text
    cuerpo = resp.json()
    assert cuerpo["mostrar_nota"] == MOSTRAR_NOTA_NUNCA, (
        "todo examen nuevo tiene que nacer con la nota OCULTA (D9)"
    )
    assert cuerpo["notas_publicadas_en"] is None
    assert cuerpo["notas_publicadas_por"] is None
    # D10: los eventos tampoco se le muestran al alumno por default.
    assert cuerpo["mostrar_eventos_alumno"] is False


@pytest.mark.asyncio
async def test_publicar_notas_registra_quien_y_cuando(app, factory):
    examen_id = await _crear_examen(factory)

    async with _admin(app) as c:
        resp = await c.post(f"/api/v1/exam-content/{examen_id}/publicar-notas")

    assert resp.status_code == 200, resp.text
    cuerpo = resp.json()
    assert cuerpo["mostrar_nota"] == MOSTRAR_NOTA_AL_CERRAR
    assert cuerpo["notas_publicadas_en"] is not None
    assert cuerpo["notas_publicadas_por"], "tiene que quedar QUIÉN publicó"


@pytest.mark.asyncio
async def test_publicar_dos_veces_da_409(app, factory):
    """Camino de ida: no hay forma de "republicar" ni de deshacer."""
    examen_id = await _crear_examen(factory)

    async with _admin(app) as c:
        primera = await c.post(f"/api/v1/exam-content/{examen_id}/publicar-notas")
        segunda = await c.post(f"/api/v1/exam-content/{examen_id}/publicar-notas")

    assert primera.status_code == 200, primera.text
    assert segunda.status_code == 409, segunda.text
    assert segunda.json()["detail"]["error"] == "notas_ya_publicadas"


@pytest.mark.asyncio
async def test_el_patch_de_config_no_permite_volver_a_ocultar(app, factory):
    examen_id = await _crear_examen(factory)

    async with _admin(app) as c:
        await c.patch(
            f"/api/v1/exam-content/{examen_id}/config",
            json={**_CONFIG_BASE, "mostrar_nota": MOSTRAR_NOTA_INMEDIATA},
        )
        retroceso = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config",
            json={**_CONFIG_BASE, "mostrar_nota": MOSTRAR_NOTA_NUNCA},
        )

    assert retroceso.status_code == 409, retroceso.text
    assert retroceso.json()["detail"]["error"] == "visibilidad_no_retrocede"


@pytest.mark.asyncio
async def test_avanzar_de_al_cerrar_a_inmediata_si_se_permite(app, factory):
    """Triangulación: el bloqueo es del RETROCESO, no de todo cambio."""
    examen_id = await _crear_examen(factory)

    async with _admin(app) as c:
        paso1 = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config",
            json={**_CONFIG_BASE, "mostrar_nota": MOSTRAR_NOTA_AL_CERRAR},
        )
        paso2 = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config",
            json={**_CONFIG_BASE, "mostrar_nota": MOSTRAR_NOTA_INMEDIATA},
        )

    assert paso1.status_code == 200, paso1.text
    assert paso2.status_code == 200, paso2.text
    assert paso2.json()["mostrar_nota"] == MOSTRAR_NOTA_INMEDIATA


@pytest.mark.asyncio
async def test_publicar_desde_el_patch_tambien_sella_quien_y_cuando(app, factory):
    """El registro de publicación no depende de qué endpoint se use."""
    examen_id = await _crear_examen(factory)

    async with _admin(app) as c:
        resp = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config",
            json={**_CONFIG_BASE, "mostrar_nota": MOSTRAR_NOTA_INMEDIATA},
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["notas_publicadas_en"] is not None
    assert resp.json()["notas_publicadas_por"]


@pytest.mark.asyncio
async def test_mostrar_eventos_al_alumno_es_por_examen(app, factory):
    """D10: activarlo en un examen no lo activa en los demás."""
    examen_a = await _crear_examen(factory)
    examen_b = await _crear_examen(factory)

    async with _admin(app) as c:
        activado = await c.patch(
            f"/api/v1/exam-content/{examen_a}/config",
            json={**_CONFIG_BASE, "mostrar_eventos_alumno": True},
        )
        otro = await c.get(f"/api/v1/exam-content/{examen_b}/config")

    assert activado.status_code == 200, activado.text
    assert activado.json()["mostrar_eventos_alumno"] is True
    assert otro.json()["mostrar_eventos_alumno"] is False, (
        "el flag es POR EXAMEN: activarlo en uno no puede afectar a otro"
    )
