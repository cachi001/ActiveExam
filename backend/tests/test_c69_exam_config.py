"""Configuración del examen POR EXAMEN (C-69, migración 0032).

ActiveExam opera la config (7 campos: timer, ventana, intentos, escala de nota,
shuffle); el alumno rinde con ella. Cubre:
- Validación de dominio (pura, sin DB).
- Roundtrip del repo (guardar/leer la config).
- Endpoints admin GET/PATCH /{id}/config (set, update parcial, validaciones 422,
  404, extra='forbid', admin-only).
- La nota usa nota_maxima (grade_calculator).
- La proyección de rendición expone timer/shuffle/escala de nota.
- El resumen/catálogo expone apertura/cierre/tiempo_limite_min/intentos_permitidos.

DB real (DATABASE_URL). Sin mocks de DB (regla dura). NO expone es_correcta (D3).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.exam_content.taking_service import proyectar_examen
from app.application.moodle.grade_calculator import (
    RespuestaAlumno,
    calcular_nota_academica,
)
from app.domain.exam_content.config import validar_config_examen
from app.domain.exam_content.entities import (
    ExamenContenido,
    OpcionRespuesta,
    Pregunta,
)
from app.domain.exam_content.errors import ConfigExamenInvalidaError
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.repositories.exam_content import (
    ExamenContenidoSqlRepository,
)
from app.presentation.api.v1.exam_content.router import (
    create_exam_content_router,
    create_exam_taking_router,
)
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

_TABLES_TO_DROP = [
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "comision",
    "materia",
]
_TABLES_TO_CREATE = [
    MateriaModel.__table__,
    ComisionModel.__table__,
    ExamenContenidoModel.__table__,
    PreguntaExamenModel.__table__,
    OpcionRespuestaModel.__table__,
]


# ---------------------------------------------------------------------------
# Validación de dominio — PURA, sin DB
# ---------------------------------------------------------------------------


def _valores_ok(**overrides):
    # C-69: apertura y cierre son OBLIGATORIOS → los defaults incluyen una ventana válida.
    base = dict(
        tiempo_limite_min=60,
        intentos_permitidos=1,
        apertura=datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc),
        cierre=datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc),
        nota_maxima=10.0,
        nota_aprobacion=6.0,
    )
    base.update(overrides)
    return base


def test_validacion_config_valida_no_eleva():
    validar_config_examen(**_valores_ok())
    # tiempo None (sin límite) también es válido
    validar_config_examen(**_valores_ok(tiempo_limite_min=None))
    # apertura < cierre válido
    ahora = datetime(2026, 1, 1, tzinfo=timezone.utc)
    validar_config_examen(
        **_valores_ok(apertura=ahora, cierre=ahora + timedelta(hours=2))
    )


def test_validacion_intentos_menor_a_uno_eleva():
    with pytest.raises(ConfigExamenInvalidaError):
        validar_config_examen(**_valores_ok(intentos_permitidos=0))


def test_validacion_nota_maxima_no_positiva_eleva():
    with pytest.raises(ConfigExamenInvalidaError):
        validar_config_examen(**_valores_ok(nota_maxima=0))


def test_validacion_nota_aprobacion_mayor_a_maxima_eleva():
    with pytest.raises(ConfigExamenInvalidaError):
        validar_config_examen(**_valores_ok(nota_maxima=10.0, nota_aprobacion=11.0))


def test_validacion_nota_aprobacion_negativa_eleva():
    with pytest.raises(ConfigExamenInvalidaError):
        validar_config_examen(**_valores_ok(nota_aprobacion=-1.0))


def test_validacion_apertura_posterior_a_cierre_eleva():
    ahora = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ConfigExamenInvalidaError):
        validar_config_examen(
            **_valores_ok(apertura=ahora, cierre=ahora - timedelta(hours=1))
        )


def test_validacion_tiempo_limite_cero_eleva():
    with pytest.raises(ConfigExamenInvalidaError):
        validar_config_examen(**_valores_ok(tiempo_limite_min=0))


# ---------------------------------------------------------------------------
# Fixtures de DB
# ---------------------------------------------------------------------------


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
async def admin_app(factory):
    application = FastAPI()
    application.state.jwt_validator = _build_test_jwt_validator()
    application.include_router(
        create_exam_content_router(session_factory=factory, writeback_svc=None),
        prefix="/api/v1/exam-content",
    )
    return application


@pytest_asyncio.fixture
async def taking_app(factory):
    application = FastAPI()
    application.state.jwt_validator = _build_test_jwt_validator()
    application.include_router(
        create_exam_taking_router(session_factory=factory, writeback_svc=None),
        prefix="/api/v1/exam-content",
    )
    return application


def _admin_client(app):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["admin_examenes"]),
    )


def _student_client(app):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(["estudiante"]),
    )


async def _crear_examen_simple(factory, titulo: str | None = None) -> str:
    async with factory() as s:
        examen = ExamenContenidoModel(titulo=titulo or f"Parcial {uuid.uuid4().hex[:6]}")
        s.add(examen)
        await s.flush()
        examen_id = examen.id
        await s.commit()
    return examen_id


# ---------------------------------------------------------------------------
# Roundtrip del repo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repo_guardar_y_leer_config(factory):
    """guardar() persiste la config y obtener() la devuelve (roundtrip)."""
    apertura = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    cierre = datetime(2026, 3, 1, 11, 0, tzinfo=timezone.utc)
    examen = ExamenContenido(
        titulo="Roundtrip",
        preguntas=(
            Pregunta(
                enunciado="¿2+2?",
                tipo="multichoice",
                opciones=(
                    OpcionRespuesta(texto="4", es_correcta=True, orden=0),
                    OpcionRespuesta(texto="5", es_correcta=False, orden=1),
                ),
            ),
        ),
        tiempo_limite_min=90,
        intentos_permitidos=3,
        apertura=apertura,
        cierre=cierre,
        nota_maxima=20.0,
        nota_aprobacion=12.0,
        mezclar_preguntas=True,
    )
    async with factory() as s:
        repo = ExamenContenidoSqlRepository(s)
        guardado = await repo.guardar(examen)
        await s.commit()
        leido = await repo.obtener(guardado.id)

    assert leido is not None
    assert leido.tiempo_limite_min == 90
    assert leido.intentos_permitidos == 3
    assert leido.apertura == apertura
    assert leido.cierre == cierre
    assert leido.nota_maxima == pytest.approx(20.0)
    assert leido.nota_aprobacion == pytest.approx(12.0)
    assert leido.mezclar_preguntas is True


@pytest.mark.asyncio
async def test_repo_defaults_compat(factory):
    """Un examen creado sin config toma los defaults (1 intento, 10/6, sin mezclar)."""
    examen_id = await _crear_examen_simple(factory)
    async with factory() as s:
        leido = await ExamenContenidoSqlRepository(s).obtener(examen_id)
    assert leido.intentos_permitidos == 1
    assert leido.nota_maxima == pytest.approx(10.0)
    assert leido.nota_aprobacion == pytest.approx(6.0)
    assert leido.mezclar_preguntas is False
    assert leido.tiempo_limite_min is None
    assert leido.apertura is None
    assert leido.cierre is None


# ---------------------------------------------------------------------------
# Endpoints GET/PATCH /{id}/config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_config_devuelve_defaults(admin_app, factory):
    examen_id = await _crear_examen_simple(factory)
    async with _admin_client(admin_app) as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/config")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {
        "tiempo_limite_min": None,
        "intentos_permitidos": 1,
        "apertura": None,
        "cierre": None,
        "nota_maxima": 10.0,
        "nota_aprobacion": 6.0,
        "mezclar_preguntas": False,
        "mostrar_nota": "al_cerrar",
        "revision_habilitada": False,
    }


@pytest.mark.asyncio
async def test_patch_config_setea_los_siete_campos(admin_app, factory):
    examen_id = await _crear_examen_simple(factory)
    payload = {
        "tiempo_limite_min": 45,
        "intentos_permitidos": 2,
        "apertura": "2026-03-01T09:00:00+00:00",
        "cierre": "2026-03-01T12:00:00+00:00",
        "nota_maxima": 20.0,
        "nota_aprobacion": 11.0,
        "mezclar_preguntas": True,
    }
    async with _admin_client(admin_app) as c:
        resp = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config", json=payload
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["tiempo_limite_min"] == 45
    assert body["intentos_permitidos"] == 2
    assert body["nota_maxima"] == 20.0
    assert body["nota_aprobacion"] == 11.0
    assert body["mezclar_preguntas"] is True
    assert body["apertura"].startswith("2026-03-01T09:00:00")
    assert body["cierre"].startswith("2026-03-01T12:00:00")

    # Persistido en la DB
    async with factory() as s:
        row = (
            await s.execute(
                select(ExamenContenidoModel).where(
                    ExamenContenidoModel.id == examen_id
                )
            )
        ).scalar_one()
        assert row.intentos_permitidos == 2
        assert float(row.nota_maxima) == 20.0
        assert row.mezclar_preguntas is True


@pytest.mark.asyncio
async def test_patch_config_parcial_preserva_el_resto(admin_app, factory):
    """Update parcial: solo cambia el campo enviado; el resto queda igual."""
    examen_id = await _crear_examen_simple(factory)
    async with _admin_client(admin_app) as c:
        # Ventana válida primero (apertura/cierre son obligatorios, C-69).
        await c.patch(
            f"/api/v1/exam-content/{examen_id}/config",
            json={
                "apertura": "2026-03-01T09:00:00+00:00",
                "cierre": "2026-03-01T11:00:00+00:00",
            },
        )
        resp = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config",
            json={"tiempo_limite_min": 30},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["tiempo_limite_min"] == 30
    # El resto conserva los defaults / lo seteado antes
    assert body["intentos_permitidos"] == 1
    assert body["nota_maxima"] == 10.0
    assert body["nota_aprobacion"] == 6.0
    assert body["mezclar_preguntas"] is False
    assert body["apertura"].startswith("2026-03-01T09:00:00")
    assert body["cierre"].startswith("2026-03-01T11:00:00")


@pytest.mark.asyncio
async def test_patch_config_fechas_obligatorias(admin_app, factory):
    """C-69: tiempo sigue siendo nullable, pero apertura/cierre son OBLIGATORIOS."""
    examen_id = await _crear_examen_simple(factory)
    async with _admin_client(admin_app) as c:
        r0 = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config",
            json={
                "apertura": "2026-03-01T09:00:00+00:00",
                "cierre": "2026-03-01T11:00:00+00:00",
                "tiempo_limite_min": 60,
            },
        )
        assert r0.status_code == 200, r0.text
        # tiempo → null: OK (sigue siendo nullable = sin límite).
        r1 = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config",
            json={"tiempo_limite_min": None},
        )
        assert r1.status_code == 200, r1.text
        assert r1.json()["tiempo_limite_min"] is None
        # apertura → null: RECHAZADO (obligatoria).
        r2 = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config",
            json={"apertura": None},
        )
        assert r2.status_code == 422, r2.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"intentos_permitidos": 0},
        {"nota_maxima": 0},
        {"nota_maxima": -5},
        {"nota_aprobacion": -1},
        {"nota_maxima": 10, "nota_aprobacion": 11},
        {"tiempo_limite_min": 0},
        {"tiempo_limite_min": -10},
        {
            "apertura": "2026-03-01T12:00:00+00:00",
            "cierre": "2026-03-01T09:00:00+00:00",
        },
    ],
)
async def test_patch_config_validaciones_422(admin_app, factory, payload):
    examen_id = await _crear_examen_simple(factory)
    async with _admin_client(admin_app) as c:
        resp = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config", json=payload
        )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_patch_config_aprobacion_contra_maxima_existente_422(admin_app, factory):
    """nota_aprobacion sola se valida contra la nota_maxima ACTUAL (default 10)."""
    examen_id = await _crear_examen_simple(factory)
    async with _admin_client(admin_app) as c:
        resp = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config",
            json={"nota_aprobacion": 15},
        )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_get_config_examen_inexistente_404(admin_app):
    async with _admin_client(admin_app) as c:
        resp = await c.get(
            "/api/v1/exam-content/00000000-0000-0000-0000-000000000000/config"
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_config_examen_inexistente_404(admin_app):
    async with _admin_client(admin_app) as c:
        resp = await c.patch(
            "/api/v1/exam-content/00000000-0000-0000-0000-000000000000/config",
            json={"intentos_permitidos": 2},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_config_extra_forbid_422(admin_app, factory):
    examen_id = await _crear_examen_simple(factory)
    async with _admin_client(admin_app) as c:
        resp = await c.patch(
            f"/api/v1/exam-content/{examen_id}/config",
            json={"intentos_permitidos": 2, "campo_raro": "x"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_config_admin_only(admin_app, factory):
    examen_id = await _crear_examen_simple(factory)
    async with AsyncClient(
        transport=ASGITransport(app=admin_app),
        base_url="http://test",
        headers=auth_headers(["estudiante"]),
    ) as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/config")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# La nota usa nota_maxima
# ---------------------------------------------------------------------------


async def _crear_examen_con_n_preguntas(
    factory, *, n: int, nota_maxima: float
) -> tuple[str, list[str], list[str]]:
    """Examen multichoice con n preguntas seleccionadas; nota_maxima configurada.

    Devuelve (examen_id, [pregunta_ids], [opcion_correcta_ids])."""
    async with factory() as s:
        examen = ExamenContenidoModel(titulo="Escala", nota_maxima=nota_maxima)
        s.add(examen)
        await s.flush()
        pregunta_ids: list[str] = []
        correctas: list[str] = []
        for i in range(n):
            p = PreguntaExamenModel(
                examen_id=examen.id, enunciado=f"P{i}", tipo="multichoice", orden=i
            )
            s.add(p)
            await s.flush()
            oc = OpcionRespuestaModel(
                pregunta_id=p.id, texto="C", es_correcta=True, orden=0
            )
            ow = OpcionRespuestaModel(
                pregunta_id=p.id, texto="W", es_correcta=False, orden=1
            )
            s.add_all([oc, ow])
            await s.flush()
            pregunta_ids.append(p.id)
            correctas.append(oc.id)
        examen_id = examen.id
        await s.commit()
    return examen_id, pregunta_ids, correctas


@pytest.mark.asyncio
async def test_nota_sobre_nota_maxima_configurable(factory):
    """nota_maxima=20 → 10/10 correctas = 20 (no 10)."""
    examen_id, pids, correctas = await _crear_examen_con_n_preguntas(
        factory, n=10, nota_maxima=20.0
    )
    respuestas = [
        RespuestaAlumno(pregunta_id=p, opcion_elegida_id=c)
        for p, c in zip(pids, correctas)
    ]
    async with factory() as s:
        nota = await calcular_nota_academica(
            db=s, examen_contenido_id=examen_id, respuestas=respuestas
        )
    assert nota == pytest.approx(20.0)


@pytest.mark.asyncio
async def test_nota_redondea_a_entero(factory):
    """1/3 correctas sobre 10 = 3.33 → 3 (redondeo a entero, ROUND_HALF_UP, estilo Moodle)."""
    examen_id, pids, correctas = await _crear_examen_con_n_preguntas(
        factory, n=3, nota_maxima=10.0
    )
    respuestas = [RespuestaAlumno(pregunta_id=pids[0], opcion_elegida_id=correctas[0])]
    async with factory() as s:
        nota = await calcular_nota_academica(
            db=s, examen_contenido_id=examen_id, respuestas=respuestas
        )
    assert nota == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# La proyección de rendición expone timer/shuffle/escala de nota
# ---------------------------------------------------------------------------


def test_proyeccion_expone_config_y_no_es_correcta():
    examen = ExamenContenido(
        id="ex-1",
        titulo="Rendir",
        tiempo_limite_min=75,
        mezclar_preguntas=True,
        nota_maxima=20.0,
        nota_aprobacion=12.0,
        preguntas=(
            Pregunta(
                id="p1",
                enunciado="¿?",
                tipo="multichoice",
                seleccionada=True,
                opciones=(
                    OpcionRespuesta(id="o1", texto="A", es_correcta=True, orden=0),
                    OpcionRespuesta(id="o2", texto="B", es_correcta=False, orden=1),
                ),
            ),
        ),
    )
    proj = proyectar_examen(examen)
    assert proj.tiempo_limite_min == 75
    assert proj.mezclar_preguntas is True
    assert proj.nota_maxima == pytest.approx(20.0)
    assert proj.nota_aprobacion == pytest.approx(12.0)
    # D3: la proyección no tiene es_correcta en sus opciones
    assert not hasattr(proj.preguntas[0].opciones[0], "es_correcta")


@pytest.mark.asyncio
async def test_endpoint_rendir_incluye_config(taking_app, factory):
    """GET /{id} expone tiempo_limite_min/mezclar_preguntas/nota_maxima/nota_aprobacion."""
    async with factory() as s:
        examen = ExamenContenidoModel(
            titulo="Rendir HTTP",
            tiempo_limite_min=50,
            mezclar_preguntas=True,
            nota_maxima=20.0,
            nota_aprobacion=12.0,
        )
        s.add(examen)
        await s.flush()
        p = PreguntaExamenModel(
            examen_id=examen.id, enunciado="P", tipo="multichoice", orden=0,
            seleccionada=True,
        )
        s.add(p)
        await s.flush()
        s.add_all([
            OpcionRespuestaModel(pregunta_id=p.id, texto="C", es_correcta=True, orden=0),
            OpcionRespuestaModel(pregunta_id=p.id, texto="W", es_correcta=False, orden=1),
        ])
        examen_id = examen.id
        await s.commit()

    async with _student_client(taking_app) as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["tiempo_limite_min"] == 50
    assert body["mezclar_preguntas"] is True
    assert body["nota_maxima"] == 20.0
    assert body["nota_aprobacion"] == 12.0
    # D3: es_correcta NUNCA viaja
    assert "es_correcta" not in body["preguntas"][0]["opciones"][0]


# ---------------------------------------------------------------------------
# Resumen + catálogo exponen apertura/cierre/tiempo_limite_min/intentos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resumen_expone_ventana_e_intentos(taking_app, factory):
    apertura = "2026-04-01T08:00:00+00:00"
    cierre = "2026-04-01T10:00:00+00:00"
    async with factory() as s:
        examen = ExamenContenidoModel(
            titulo="Con ventana",
            apertura=datetime(2026, 4, 1, 8, 0, tzinfo=timezone.utc),
            cierre=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
            tiempo_limite_min=120,
            intentos_permitidos=2,
        )
        s.add(examen)
        await s.flush()
        examen_id = examen.id
        await s.commit()

    async with _student_client(taking_app) as c:
        resp = await c.get(f"/api/v1/exam-content/{examen_id}/resumen")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["apertura"].startswith("2026-04-01T08:00:00")
    assert body["cierre"].startswith("2026-04-01T10:00:00")
    assert body["tiempo_limite_min"] == 120
    assert body["intentos_permitidos"] == 2


@pytest.mark.asyncio
async def test_catalogo_expone_ventana_e_intentos(taking_app, factory):
    async with factory() as s:
        examen = ExamenContenidoModel(
            titulo="Catálogo ventana",
            tiempo_limite_min=90,
            intentos_permitidos=3,
        )
        s.add(examen)
        await s.flush()
        examen_id = examen.id
        await s.commit()

    # C-71: el catálogo del ALUMNO se filtra por inscripción (no ve exámenes sin
    # comisión / de comisiones no inscriptas). Este test verifica la EXPOSICIÓN de
    # campos (ventana/intentos) del catálogo, no la visibilidad por rol → usa un
    # cliente staff, que ve todo el catálogo.
    async with _admin_client(taking_app) as c:
        resp = await c.get(f"/api/v1/exam-content?q=Catálogo ventana")
    assert resp.status_code == 200, resp.text
    items = {it["id"]: it for it in resp.json()["items"]}
    assert examen_id in items
    it = items[examen_id]
    assert it["tiempo_limite_min"] == 90
    assert it["intentos_permitidos"] == 3
    assert "apertura" in it
    assert "cierre" in it
