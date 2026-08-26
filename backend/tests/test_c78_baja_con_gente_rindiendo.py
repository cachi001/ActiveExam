"""c-78 — Guarda de "hay gente rindiendo ahora" para materia y comisión, y el
aviso de impacto antes de confirmar una baja (Opción C del dueño).

Hasta ahora la guarda la tenía SOLO el examen: dar de baja una materia bloqueaba
la rendición de todos sus exámenes server-side, así que le cortaba el examen a
medio camino a quien estuviera rindiendo. Acá se cubre:

  - DELETE /materias/{id}   con gente rindiendo → 409 `materia_en_curso`
  - DELETE /comisiones/{id} con gente rindiendo → 409 `comision_en_curso`
  - una sesión ya VENCIDA no cuenta como gente rindiendo (la auto-finalización
    es lazy: el alumno que cerró el navegador deja la fila abierta para siempre)
  - la guarda mira solo el propio árbol: otra materia no bloquea

Y el aviso de la Opción C, que NO bloquea nada: `GET .../impacto-baja` devuelve
cuántas rendiciones ya tiene lo que se está por dar de baja, para que el diálogo
lo diga antes de confirmar.

Mismo patrón de fixtures que test_c78_examen_baja_logica.py (DB REAL, sin ningún
mock de base).
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

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
    application.include_router(
        create_exam_content_router(session_factory=factory, writeback_svc=None),
        prefix="/api/v1/exam-content",
    )
    application.include_router(
        create_exam_taking_router(session_factory=factory, writeback_svc=None),
        prefix="/api/v1/exam-content",
    )
    return application


async def _crear_arbol(
    factory,
    *,
    tiempo_limite_min: int | None = None,
    cierre: datetime | None = None,
) -> tuple[str, str, str]:
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
            titulo=f"Parcial {sufijo}",
            comision_id=comision.id,
            tiempo_limite_min=tiempo_limite_min,
            cierre=cierre,
        )
        s.add(examen)
        await s.flush()
        ids = (materia.id, comision.id, examen.id)
        await s.commit()
    return ids


async def _crear_sesion(
    factory,
    examen_id: str,
    *,
    finalizada: bool,
    creada_hace_min: int = 0,
) -> str:
    ahora = datetime.now(UTC)
    creada_en = ahora - timedelta(minutes=creada_hace_min)
    async with factory() as s:
        sesion = ProctoringSessionModel(
            id=str(uuid.uuid4()),
            modo="examen",
            examen_contenido_id=examen_id,
            creada_en=creada_en,
            finalizada_en=ahora if finalizada else None,
        )
        s.add(sesion)
        await s.commit()
        return sesion.id


def _client(app, roles: list[str], subject: str = "staff-1"):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(roles, subject=subject),
    )


async def _materia_activa(factory, materia_id: str) -> bool:
    async with factory() as s:
        return (
            await s.execute(
                select(MateriaModel.activa).where(MateriaModel.id == materia_id)
            )
        ).scalar_one()


async def _comision_activa(factory, comision_id: str) -> bool:
    async with factory() as s:
        return (
            await s.execute(
                select(ComisionModel.activa).where(ComisionModel.id == comision_id)
            )
        ).scalar_one()


# ---------------------------------------------------------------------------
# Guarda: no se da de baja algo que se está rindiendo AHORA
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_se_puede_dar_de_baja_una_materia_con_gente_rindiendo(app, factory):
    materia_id, _c, examen_id = await _crear_arbol(factory, tiempo_limite_min=120)
    await _crear_sesion(factory, examen_id, finalizada=False)

    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.delete(f"/api/v1/exam-content/materias/{materia_id}")

    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"] == "materia_en_curso"
    assert resp.json()["detail"]["sesiones_en_curso"] == 1
    assert await _materia_activa(factory, materia_id), (
        "el rechazo no puede haber dado de baja la materia"
    )


@pytest.mark.asyncio
async def test_si_se_puede_dar_de_baja_una_materia_ya_rendida(app, factory):
    """Triangulación: la restricción es "en curso", NO "rendida alguna vez"."""
    materia_id, _c, examen_id = await _crear_arbol(factory, tiempo_limite_min=120)
    await _crear_sesion(factory, examen_id, finalizada=True)

    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.delete(f"/api/v1/exam-content/materias/{materia_id}")

    assert resp.status_code == 204, resp.text
    assert not await _materia_activa(factory, materia_id)


@pytest.mark.asyncio
async def test_no_se_puede_dar_de_baja_una_comision_con_gente_rindiendo(app, factory):
    _m, comision_id, examen_id = await _crear_arbol(factory, tiempo_limite_min=120)
    await _crear_sesion(factory, examen_id, finalizada=False)

    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.delete(f"/api/v1/exam-content/comisiones/{comision_id}")

    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"] == "comision_en_curso"
    assert resp.json()["detail"]["sesiones_en_curso"] == 1
    assert await _comision_activa(factory, comision_id)


@pytest.mark.asyncio
async def test_si_se_puede_dar_de_baja_una_comision_ya_rendida(app, factory):
    _m, comision_id, examen_id = await _crear_arbol(factory, tiempo_limite_min=120)
    await _crear_sesion(factory, examen_id, finalizada=True)

    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.delete(f"/api/v1/exam-content/comisiones/{comision_id}")

    assert resp.status_code == 204, resp.text
    assert not await _comision_activa(factory, comision_id)


@pytest.mark.asyncio
async def test_una_sesion_vencida_no_cuenta_como_gente_rindiendo(app, factory):
    """El caso que motivó el criterio: la auto-finalización es LAZY.

    El alumno que cierra el navegador y no vuelve deja `finalizada_en = NULL`
    para siempre — nadie toca esa sesión, así que nadie la cierra. Contarla como
    "rindiendo" dejaba la materia sin poder darse de baja nunca. Una sesión
    cuyo tiempo ya se agotó NO es gente rindiendo.
    """
    materia_id, _c, examen_id = await _crear_arbol(factory, tiempo_limite_min=60)
    await _crear_sesion(factory, examen_id, finalizada=False, creada_hace_min=180)

    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.delete(f"/api/v1/exam-content/materias/{materia_id}")

    assert resp.status_code == 204, resp.text


@pytest.mark.asyncio
async def test_una_sesion_dentro_de_su_tiempo_si_cuenta(app, factory):
    """Triangulación del deadline: recién arrancada, con 60 min por delante."""
    materia_id, _c, examen_id = await _crear_arbol(factory, tiempo_limite_min=60)
    await _crear_sesion(factory, examen_id, finalizada=False, creada_hace_min=5)

    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.delete(f"/api/v1/exam-content/materias/{materia_id}")

    assert resp.status_code == 409, resp.text


@pytest.mark.asyncio
async def test_el_cierre_del_examen_tambien_vence_la_sesion(app, factory):
    """Sin tiempo límite individual, manda el cierre de la ventana del examen."""
    cerrado_hace_una_hora = datetime.now(UTC) - timedelta(hours=1)
    materia_id, _c, examen_id = await _crear_arbol(
        factory, tiempo_limite_min=None, cierre=cerrado_hace_una_hora
    )
    await _crear_sesion(factory, examen_id, finalizada=False, creada_hace_min=90)

    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.delete(f"/api/v1/exam-content/materias/{materia_id}")

    assert resp.status_code == 204, resp.text


@pytest.mark.asyncio
async def test_la_guarda_solo_mira_el_propio_arbol(app, factory):
    """Aislamiento: que alguien esté rindiendo en OTRA materia no bloquea esta."""
    materia_id, _c, _e = await _crear_arbol(factory, tiempo_limite_min=120)
    _m2, _c2, examen_ajeno = await _crear_arbol(factory, tiempo_limite_min=120)
    await _crear_sesion(factory, examen_ajeno, finalizada=False)

    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.delete(f"/api/v1/exam-content/materias/{materia_id}")

    assert resp.status_code == 204, resp.text


# ---------------------------------------------------------------------------
# Aviso de impacto (Opción C) — informa, NO bloquea
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_impacto_de_un_examen_cuenta_sus_rendiciones(app, factory):
    _m, _c, examen_id = await _crear_arbol(factory, tiempo_limite_min=120)
    for _ in range(3):
        await _crear_sesion(factory, examen_id, finalizada=True)

    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/impacto-baja")

    assert resp.status_code == 200, resp.text
    cuerpo = resp.json()
    assert cuerpo["rendiciones"] == 3
    assert cuerpo["sesiones_en_curso"] == 0
    assert cuerpo["examenes"] == 1


@pytest.mark.asyncio
async def test_impacto_de_una_comision_suma_sus_examenes(app, factory):
    _m, comision_id, examen_id = await _crear_arbol(factory, tiempo_limite_min=120)
    await _crear_sesion(factory, examen_id, finalizada=True)
    await _crear_sesion(factory, examen_id, finalizada=False)

    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.get(
            f"/api/v1/exam-content/comisiones/{comision_id}/impacto-baja"
        )

    assert resp.status_code == 200, resp.text
    cuerpo = resp.json()
    assert cuerpo["rendiciones"] == 1
    assert cuerpo["sesiones_en_curso"] == 1
    assert cuerpo["examenes"] == 1


@pytest.mark.asyncio
async def test_impacto_de_una_materia_suma_todas_sus_comisiones(app, factory):
    materia_id, _c, examen_id = await _crear_arbol(factory, tiempo_limite_min=120)
    await _crear_sesion(factory, examen_id, finalizada=True)
    await _crear_sesion(factory, examen_id, finalizada=True)

    # Segunda comisión de la MISMA materia, con su propio examen rendido.
    sufijo = uuid.uuid4().hex[:6]
    async with factory() as s:
        comision2 = ComisionModel(
            materia_id=materia_id,
            codigo=f"C2-{sufijo}",
            nombre=f"Comisión 2 {sufijo}",
            codigo_matriculacion=f"K2-{sufijo}",
        )
        s.add(comision2)
        await s.flush()
        examen2 = ExamenContenidoModel(
            titulo=f"Parcial 2 {sufijo}",
            comision_id=comision2.id,
            tiempo_limite_min=120,
        )
        s.add(examen2)
        await s.flush()
        examen2_id = examen2.id
        await s.commit()
    await _crear_sesion(factory, examen2_id, finalizada=True)

    async with _client(app, ["admin_sistema"]) as c:
        resp = await c.get(f"/api/v1/exam-content/materias/{materia_id}/impacto-baja")

    assert resp.status_code == 200, resp.text
    cuerpo = resp.json()
    assert cuerpo["rendiciones"] == 3
    assert cuerpo["examenes"] == 2
    assert cuerpo["comisiones"] == 2


@pytest.mark.asyncio
async def test_el_impacto_no_da_de_baja_nada(app, factory):
    """Es una consulta: pedirlo no puede tener efecto."""
    materia_id, _c, _e = await _crear_arbol(factory)

    async with _client(app, ["admin_sistema"]) as c:
        assert (
            await c.get(f"/api/v1/exam-content/materias/{materia_id}/impacto-baja")
        ).status_code == 200

    assert await _materia_activa(factory, materia_id)


@pytest.mark.asyncio
async def test_un_examen_dado_de_baja_no_cuenta_en_el_impacto_de_su_materia(
    app, factory
):
    """El aviso habla del inventario VIGENTE: lo ya dado de baja no se re-anuncia."""
    materia_id, _c, examen_id = await _crear_arbol(factory, tiempo_limite_min=120)
    await _crear_sesion(factory, examen_id, finalizada=True)

    async with _client(app, ["admin_sistema"]) as c:
        assert (
            await c.delete(f"/api/v1/exam-content/{examen_id}")
        ).status_code == 204
        resp = await c.get(f"/api/v1/exam-content/materias/{materia_id}/impacto-baja")

    assert resp.json()["examenes"] == 0
