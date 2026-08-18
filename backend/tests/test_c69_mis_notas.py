"""Notas del ALUMNO: GET /api/v1/exam-content/mis-notas (C-69, student-facing).

El alumno autenticado ve SOLO sus notas finalizadas (identificado por el JWT:
username -> alumno_idnumber, email -> alumno_email), cada una con:
- nota academica + estado del envio a Moodle (pendiente|enviado|fallido|sin_token),
- estado L2.5 'en cola de revision': score de proctoring de la sesion vs el
  umbral_cola_revision del singleton de config (score >= umbral -> en cola).

DB real (DATABASE_URL). Sin mocks de DB (regla dura). NO expone es_correcta (D3).
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

from app.application.moodle.writeback_service import (
    MoodleWritebackService,
    WritebackEstado,
)
from app.infrastructure.auth.verifiers import encode_hs256
from app.infrastructure.moodle.client import MoodleClientConfig, MoodleRestClient
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ComisionModel,
    ExamenContenidoModel,
    MateriaModel,
    OpcionRespuestaModel,
    PreguntaExamenModel,
)
from app.infrastructure.persistence.models.moodle_writeback import (  # noqa: F401
    MoodleWritebackAuditModel,
    MoodleWritebackEstadoModel,
    RespuestaAlumnoModel,
)
from app.infrastructure.persistence.models.proctoring import (  # noqa: F401
    ProctoringEventModel,
    ProctoringSessionModel,
)
from app.infrastructure.persistence.models.transactional import (  # noqa: F401
    ConfiguracionSistemaModel,
    EventoScoreConfigModel,
)
from app.presentation.api.v1.exam_content.router import create_exam_taking_router
from tests.proctoring.conftest import (
    _TEST_JWT_AUDIENCE,
    _TEST_JWT_ISSUER,
    _TEST_JWT_SECRET,
    _build_test_jwt_validator,
)

# Umbral de cola de revision sembrado para los tests.
UMBRAL = 40

_TABLES_TO_DROP = [
    "moodle_writeback_audit",
    "moodle_writeback_estado",
    "respuesta_alumno",
    "opcion_respuesta",
    "pregunta_examen",
    "examen_contenido",
    "comision",
    "materia",
    "proctoring_event",
    "proctoring_biometria",
    "proctoring_session",
    "evento_score_config",
    "configuracion_sistema",
]
_TABLES_TO_CREATE = [
    MateriaModel.__table__,
    ComisionModel.__table__,
    ExamenContenidoModel.__table__,
    PreguntaExamenModel.__table__,
    OpcionRespuestaModel.__table__,
    ProctoringSessionModel.__table__,
    ProctoringEventModel.__table__,
    RespuestaAlumnoModel.__table__,
    MoodleWritebackEstadoModel.__table__,
    MoodleWritebackAuditModel.__table__,
    ConfiguracionSistemaModel.__table__,
    EventoScoreConfigModel.__table__,
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


@pytest_asyncio.fixture(autouse=True)
async def seed_config(factory):
    """Singleton de config (umbral) + pesos por tipo de evento (evento_score_config)."""
    async with factory() as s:
        # Limpia estado entre tests para aislamiento.
        await s.execute(text("TRUNCATE configuracion_sistema, evento_score_config CASCADE"))
        await s.execute(
            text(
                "TRUNCATE moodle_writeback_estado, proctoring_event, "
                "proctoring_session, examen_contenido CASCADE"
            )
        )
        s.add(ConfiguracionSistemaModel(id="global", umbral_cola_revision=UMBRAL))
        s.add(
            EventoScoreConfigModel(
                tipo_evento="rostro_ausente", severidad="alta", peso=50, activo=True
            )
        )
        s.add(
            EventoScoreConfigModel(
                tipo_evento="copiar_pegar", severidad="baja", peso=10, activo=True
            )
        )
        await s.commit()


def _moodle_svc() -> MoodleWritebackService:
    config = MoodleClientConfig(
        base_url="https://moodle.test", ws_token="tok"  # noqa: S106
    )
    return MoodleWritebackService(moodle_client=MoodleRestClient(config=config))


def _build_app(factory, *, writeback_svc):
    app = FastAPI()
    app.state.jwt_validator = _build_test_jwt_validator()
    app.include_router(
        create_exam_taking_router(session_factory=factory, writeback_svc=writeback_svc),
        prefix="/api/v1/exam-content",
    )
    return app


@pytest_asyncio.fixture
async def app_con_moodle(factory):
    return _build_app(factory, writeback_svc=_moodle_svc())


@pytest_asyncio.fixture
async def app_sin_moodle(factory):
    return _build_app(factory, writeback_svc=None)


def _token(idnumber: str, email: str, roles=("estudiante",)) -> str:
    """JWT HS256 de test con preferred_username=idnumber y el email dados."""
    claims = {
        "iss": _TEST_JWT_ISSUER,
        "aud": _TEST_JWT_AUDIENCE,
        "sub": f"sub-{idnumber}",
        "preferred_username": idnumber,  # -> username -> alumno_idnumber
        "email": email,
        "exp": 9999999999,
        "amr": ["otp"],
        "realm_access": {"roles": list(roles)},
    }
    return encode_hs256(claims, _TEST_JWT_SECRET)


def _client(app, idnumber: str, email: str):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {_token(idnumber, email)}"},
    )


async def _crear_examen(factory, titulo: str) -> str:
    # mostrar_nota='inmediata': el default del modelo es 'al_cerrar' y, sin fecha de
    # cierre, la nota NUNCA se vuelve visible (gate de visibilidad C-69) — el
    # endpoint devolvería nota=None y estos tests no podrían verificar el número.
    # La visibilidad tiene su cobertura propia en el dominio (visibilidad.py).
    async with factory() as s:
        examen = ExamenContenidoModel(titulo=titulo, mostrar_nota="inmediata")
        s.add(examen)
        await s.flush()
        examen_id = examen.id
        await s.commit()
    return examen_id


async def _crear_sesion_con_nota_y_eventos(
    factory,
    examen_id: str,
    *,
    idnumber: str,
    email: str,
    nota: float,
    estado: str = WritebackEstado.PENDIENTE,
    evento_tipo: str | None = None,
    n_eventos: int = 0,
    severidad: str = "alta",
) -> str:
    """Crea una sesion FINALIZADA + fila de nota + N eventos de un tipo."""
    async with factory() as s:
        sesion = ProctoringSessionModel(modo="examen", examen_contenido_id=examen_id)
        sesion.finalizada_en = datetime.now(timezone.utc)
        s.add(sesion)
        await s.flush()
        session_id = sesion.id

        for _ in range(n_eventos):
            s.add(
                ProctoringEventModel(
                    session_id=session_id,
                    tipo=evento_tipo or "rostro_ausente",
                    severidad=severidad,
                    ts_cliente=datetime.now(timezone.utc),
                )
            )

        s.add(
            MoodleWritebackEstadoModel(
                session_id=session_id,
                alumno_idnumber=idnumber,
                alumno_email=email,
                nota=nota,
                estado=estado,
                intento=0,
            )
        )
        await s.commit()
    return session_id


# ===========================================================================
# Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_alumno_ve_sus_notas_con_nota_y_estado(app_con_moodle, factory):
    examen_id = await _crear_examen(factory, "Álgebra I")
    await _crear_sesion_con_nota_y_eventos(
        factory, examen_id, idnumber="leg-A", email="a@u.edu", nota=8.5,
        evento_tipo="rostro_ausente", n_eventos=1,
    )

    async with _client(app_con_moodle, "leg-A", "a@u.edu") as c:
        resp = await c.get("/api/v1/exam-content/mis-notas")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {"items", "total"}
    assert body["total"] == 1
    item = body["items"][0]
    assert item["examen_id"] == examen_id
    assert item["examen_titulo"] == "Álgebra I"
    assert float(item["nota"]) == pytest.approx(8.5)
    assert item["estado_moodle"] == "pendiente"
    assert item["eventos"] == 1
    assert item["finalizada_en"] is not None


@pytest.mark.asyncio
async def test_en_cola_revision_segun_umbral(app_con_moodle, factory):
    """score >= umbral -> en cola; score < umbral -> no. Umbral sembrado = 40."""
    ex_alto = await _crear_examen(factory, "Examen riesgoso")
    ex_bajo = await _crear_examen(factory, "Examen tranquilo")
    # 1 evento rostro_ausente (peso 50) -> score 50 >= 40 -> en cola.
    await _crear_sesion_con_nota_y_eventos(
        factory, ex_alto, idnumber="leg-A", email="a@u.edu", nota=6.0,
        evento_tipo="rostro_ausente", n_eventos=1,
    )
    # 1 evento copiar_pegar (peso 10) -> score 10 < 40 -> NO en cola.
    await _crear_sesion_con_nota_y_eventos(
        factory, ex_bajo, idnumber="leg-A", email="a@u.edu", nota=9.0,
        evento_tipo="copiar_pegar", n_eventos=1, severidad="baja",
    )

    async with _client(app_con_moodle, "leg-A", "a@u.edu") as c:
        resp = await c.get("/api/v1/exam-content/mis-notas")
    assert resp.status_code == 200, resp.text
    items = {it["examen_id"]: it for it in resp.json()["items"]}

    alto = items[ex_alto]
    assert alto["en_cola_revision"] is True
    assert float(alto["score"]) == pytest.approx(50.0)
    assert float(alto["umbral_revision"]) == pytest.approx(float(UMBRAL))

    bajo = items[ex_bajo]
    assert bajo["en_cola_revision"] is False
    assert float(bajo["score"]) == pytest.approx(10.0)
    assert float(bajo["umbral_revision"]) == pytest.approx(float(UMBRAL))


@pytest.mark.asyncio
async def test_alumno_solo_ve_sus_propias_notas(app_con_moodle, factory):
    ex_a = await _crear_examen(factory, "Examen de A")
    ex_b = await _crear_examen(factory, "Examen de B")
    await _crear_sesion_con_nota_y_eventos(
        factory, ex_a, idnumber="leg-A", email="a@u.edu", nota=7.0,
        evento_tipo="rostro_ausente", n_eventos=1,
    )
    await _crear_sesion_con_nota_y_eventos(
        factory, ex_b, idnumber="leg-B", email="b@u.edu", nota=3.0,
        evento_tipo="rostro_ausente", n_eventos=1,
    )

    async with _client(app_con_moodle, "leg-A", "a@u.edu") as c:
        resp = await c.get("/api/v1/exam-content/mis-notas")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    examenes = {it["examen_id"] for it in body["items"]}
    assert ex_a in examenes
    assert ex_b not in examenes
    assert body["total"] == 1


@pytest.mark.asyncio
async def test_no_filtra_es_correcta(app_con_moodle, factory):
    examen_id = await _crear_examen(factory, "Examen D3")
    await _crear_sesion_con_nota_y_eventos(
        factory, examen_id, idnumber="leg-A", email="a@u.edu", nota=5.0,
        evento_tipo="rostro_ausente", n_eventos=1,
    )
    async with _client(app_con_moodle, "leg-A", "a@u.edu") as c:
        resp = await c.get("/api/v1/exam-content/mis-notas")
    assert resp.status_code == 200, resp.text
    for it in resp.json()["items"]:
        assert "es_correcta" not in it
        assert "respuestas" not in it


@pytest.mark.asyncio
async def test_sin_moodle_estado_sin_token(app_sin_moodle, factory):
    examen_id = await _crear_examen(factory, "Examen sin token")
    await _crear_sesion_con_nota_y_eventos(
        factory, examen_id, idnumber="leg-A", email="a@u.edu", nota=4.0,
        evento_tipo="rostro_ausente", n_eventos=1,
    )
    async with _client(app_sin_moodle, "leg-A", "a@u.edu") as c:
        resp = await c.get("/api/v1/exam-content/mis-notas")
    assert resp.status_code == 200, resp.text
    assert resp.json()["items"][0]["estado_moodle"] == "sin_token"


async def _crear_examen_con_config(
    factory, titulo: str, *, nota_maxima: float, nota_aprobacion: float
) -> str:
    async with factory() as s:
        examen = ExamenContenidoModel(
            titulo=titulo,
            nota_maxima=nota_maxima,
            nota_aprobacion=nota_aprobacion,
            # Idem _crear_examen: sin esto el gate de visibilidad (C-69) devuelve
            # nota=None y aprobado=False, y no se puede verificar la escala.
            mostrar_nota="inmediata",
        )
        s.add(examen)
        await s.flush()
        examen_id = examen.id
        await s.commit()
    return examen_id


@pytest.mark.asyncio
async def test_mis_notas_incluye_nota_maxima_y_aprobado(app_con_moodle, factory):
    """Cada ítem trae nota_maxima del examen y aprobado = nota >= nota_aprobacion."""
    ex_aprob = await _crear_examen_con_config(
        factory, "Aprobado", nota_maxima=20.0, nota_aprobacion=12.0
    )
    ex_reprob = await _crear_examen_con_config(
        factory, "Reprobado", nota_maxima=20.0, nota_aprobacion=12.0
    )
    # nota 15 >= 12 -> aprobado; nota 8 < 12 -> reprobado. nota_maxima=20 en ambos.
    await _crear_sesion_con_nota_y_eventos(
        factory, ex_aprob, idnumber="leg-A", email="a@u.edu", nota=15.0,
        evento_tipo="rostro_ausente", n_eventos=1,
    )
    await _crear_sesion_con_nota_y_eventos(
        factory, ex_reprob, idnumber="leg-A", email="a@u.edu", nota=8.0,
        evento_tipo="rostro_ausente", n_eventos=1,
    )

    async with _client(app_con_moodle, "leg-A", "a@u.edu") as c:
        resp = await c.get("/api/v1/exam-content/mis-notas")
    assert resp.status_code == 200, resp.text
    items = {it["examen_id"]: it for it in resp.json()["items"]}

    aprob = items[ex_aprob]
    assert float(aprob["nota_maxima"]) == pytest.approx(20.0)
    assert aprob["aprobado"] is True

    reprob = items[ex_reprob]
    assert float(reprob["nota_maxima"]) == pytest.approx(20.0)
    assert reprob["aprobado"] is False


@pytest.mark.asyncio
async def test_requiere_autenticacion(app_con_moodle):
    async with AsyncClient(
        transport=ASGITransport(app=app_con_moodle), base_url="http://test"
    ) as c:
        resp = await c.get("/api/v1/exam-content/mis-notas")
    assert resp.status_code == 401
