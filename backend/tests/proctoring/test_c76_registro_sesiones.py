"""C-76 tarea 17 — Registro de sesiones: tabla + paginacion real + filtros.

GET /sessions/registro (paginado + filtros: alumno, examen, fecha, nivel de
riesgo) y GET /sessions/registro/examenes (catalogo de exámenes con sesiones,
para que el frontend NUNCA hardcodee la lista).

DB real (DATABASE_URL). Sin mocks (regla dura #4). Fixture propia
(function-scoped), mismo patron que test_c76_tutor_comision.py.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.asyncio

_TABLAS = (
    "proctoring_event",
    "proctoring_biometria",
    "proctoring_session",
    "comision",
    "materia",
    "examen_contenido",
    "usuario",
)

_TEST_JWT_SECRET = b"c76-registro-sesiones-test-secret"
_TEST_JWT_ISSUER = "activeexam-auth"
_TEST_JWT_AUDIENCE = "proctoring-api"


def _db_url() -> str | None:
    return os.environ.get("DATABASE_URL")


def _token(roles: list[str], subject: str, *, mfa: bool = True) -> str:
    from app.infrastructure.auth.verifiers import encode_hs256

    claims: dict = {
        "iss": _TEST_JWT_ISSUER,
        "aud": _TEST_JWT_AUDIENCE,
        "sub": subject,
        "preferred_username": "+".join(roles),
        "email": "test@uni.edu",
        "exp": 9999999999,
        "realm_access": {"roles": roles},
    }
    if mfa:
        claims["amr"] = ["otp"]
    return encode_hs256(claims, _TEST_JWT_SECRET)


def _h(roles: list[str], subject: str) -> dict:
    return {"Authorization": f"Bearer {_token(roles, subject)}"}


@pytest_asyncio.fixture
async def ctx():
    """App + engine + factory, con las tablas de proctoring + academicas creadas."""
    url = _db_url()
    if not url:
        pytest.skip("DATABASE_URL no esta seteada; test de integracion (DB real).")

    from app.domain.auth.token import TokenPolicy
    from app.infrastructure.auth.jwks_cache import JwksCache
    from app.infrastructure.auth.jwt_validator import JwtValidator
    from app.infrastructure.auth.verifiers import build_hs256_verify
    from app.infrastructure.persistence.models.exam_content import (
        ComisionModel,
        ExamenContenidoModel,
        MateriaModel,
    )
    from app.infrastructure.persistence.models.proctoring import (
        ProctoringBiometriaModel,
        ProctoringEventModel,
        ProctoringSessionModel,
    )
    from app.infrastructure.persistence.models.transactional import UsuarioModel
    from app.presentation.api.v1.proctoring.router import create_proctoring_router
    from app.infrastructure.reinferencia.mediapipe_adapter import MediaPipeReinferencia

    engine = create_async_engine(url, pool_pre_ping=True, future=True, poolclass=NullPool)
    async with engine.begin() as conn:
        for name in _TABLAS:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
        await conn.run_sync(UsuarioModel.__table__.create, checkfirst=True)
        await conn.run_sync(MateriaModel.__table__.create, checkfirst=True)
        await conn.run_sync(ComisionModel.__table__.create, checkfirst=True)
        await conn.run_sync(ExamenContenidoModel.__table__.create, checkfirst=True)
        await conn.run_sync(ProctoringSessionModel.__table__.create, checkfirst=True)
        await conn.run_sync(ProctoringEventModel.__table__.create, checkfirst=True)
        await conn.run_sync(ProctoringBiometriaModel.__table__.create, checkfirst=True)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    app = FastAPI()
    cache = JwksCache(lambda: {"keys": [{"kid": "test-key"}]}, ttl_seconds=3600)
    policy = TokenPolicy(issuers_aceptados=frozenset({_TEST_JWT_ISSUER}), audience=_TEST_JWT_AUDIENCE)
    app.state.jwt_validator = JwtValidator(
        jwks_cache=cache, policy=policy, verify_fn=build_hs256_verify(_TEST_JWT_SECRET)
    )
    router = create_proctoring_router(
        session_factory=factory, reinferencia=MediaPipeReinferencia()
    )
    app.include_router(router, prefix="/api/v1/proctoring")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, factory

    async with engine.begin() as conn:
        for name in _TABLAS:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await engine.dispose()


async def _crear_examen(factory, *, titulo: str, docente_id: str | None = None) -> str:
    """Crea materia + comision (+ examen). Devuelve examen_contenido_id."""
    from app.infrastructure.persistence.models.exam_content import (
        ComisionModel,
        ExamenContenidoModel,
        MateriaModel,
    )
    from app.infrastructure.persistence.models.transactional import UsuarioModel

    async with factory() as session:
        if docente_id is not None:
            session.add(
                UsuarioModel(
                    id=docente_id,
                    username=f"tutor-{docente_id[:8]}",
                    email=f"tutor-{docente_id[:8]}@uni.edu",
                    roles=["tutor"],
                )
            )
        materia = MateriaModel(codigo=f"MAT-{uuid.uuid4().hex[:8]}", nombre="Materia Test")
        session.add(materia)
        await session.flush()
        comision = ComisionModel(
            materia_id=materia.id,
            codigo="C1",
            nombre="Comision 1",
            codigo_matriculacion=f"MAT-C1-{uuid.uuid4().hex[:8]}",
            docente_id=docente_id,
        )
        session.add(comision)
        await session.flush()
        examen = ExamenContenidoModel(titulo=titulo, comision_id=comision.id)
        session.add(examen)
        await session.commit()
        return examen.id


async def _crear_sesion_finalizada(
    factory,
    *,
    examen_contenido_id: str | None,
    alumno_idnumber: str = "alumno-1",
    alumno_email: str = "alumno1@uni.edu",
    finalizada_en: datetime | None = None,
) -> str:
    from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel

    async with factory() as session:
        s = ProctoringSessionModel(
            modo="examen",
            examen_contenido_id=examen_contenido_id,
            alumno_idnumber=alumno_idnumber,
            alumno_email=alumno_email,
            finalizada_en=finalizada_en or datetime.now(timezone.utc),
        )
        session.add(s)
        await session.commit()
        await session.refresh(s)
        return s.id


async def _crear_evento(factory, session_id: str, *, severidad: str, tipo: str = "cara_ausente") -> None:
    from app.infrastructure.persistence.models.proctoring import ProctoringEventModel

    async with factory() as session:
        session.add(
            ProctoringEventModel(
                session_id=session_id,
                tipo=tipo,
                severidad=severidad,
                ts_cliente=datetime.now(timezone.utc),
                ts_backend=datetime.now(timezone.utc),
            )
        )
        await session.commit()


# --- Paginacion ---------------------------------------------------------------


async def test_paginacion_real_pagina_1_de_2(ctx) -> None:
    client, factory = ctx
    examen_id = await _crear_examen(factory, titulo="Examen A")
    for i in range(3):
        await _crear_sesion_finalizada(factory, examen_contenido_id=examen_id, alumno_idnumber=f"al-{i}")

    resp = await client.get(
        "/api/v1/proctoring/sessions/registro",
        params={"page": 1, "page_size": 2},
        headers=_h(["coordinador"], "coord-1"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) == 2


async def test_paginacion_real_pagina_2_trae_el_resto(ctx) -> None:
    client, factory = ctx
    examen_id = await _crear_examen(factory, titulo="Examen A")
    for i in range(3):
        await _crear_sesion_finalizada(factory, examen_contenido_id=examen_id, alumno_idnumber=f"al-{i}")

    resp = await client.get(
        "/api/v1/proctoring/sessions/registro",
        params={"page": 2, "page_size": 2},
        headers=_h(["coordinador"], "coord-1"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 1


# --- Filtro por alumno ----------------------------------------------------


async def test_filtro_alumno_por_idnumber(ctx) -> None:
    client, factory = ctx
    examen_id = await _crear_examen(factory, titulo="Examen A")
    await _crear_sesion_finalizada(factory, examen_contenido_id=examen_id, alumno_idnumber="legajo-999")
    await _crear_sesion_finalizada(factory, examen_contenido_id=examen_id, alumno_idnumber="legajo-111")

    resp = await client.get(
        "/api/v1/proctoring/sessions/registro",
        params={"q": "999"},
        headers=_h(["coordinador"], "coord-1"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"]


async def test_filtro_alumno_por_nombre_y_respuesta_incluye_alumno_nombre(ctx) -> None:
    """Busca por nombre/apellido del usuario (no solo idnumber/email) y la
    respuesta trae `alumno_nombre` resuelto contra `usuario` (columna "Alumno")."""
    client, factory = ctx
    from app.infrastructure.persistence.models.transactional import UsuarioModel

    examen_id = await _crear_examen(factory, titulo="Examen A")
    sid = await _crear_sesion_finalizada(
        factory, examen_contenido_id=examen_id, alumno_idnumber="legajo-77", alumno_email="ana@uni.edu"
    )
    async with factory() as session:
        session.add(
            UsuarioModel(
                id=str(uuid.uuid4()),
                username="legajo-77",
                email="ana@uni.edu",
                roles=["estudiante"],
                nombre="Ana",
                apellido="Gomez",
            )
        )
        await session.commit()

    resp = await client.get(
        "/api/v1/proctoring/sessions/registro",
        params={"q": "Gomez"},
        headers=_h(["coordinador"], "coord-1"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == sid
    assert body["items"][0]["alumno_nombre"] == "Ana Gomez"


# --- Filtro por examen ------------------------------------------------------


async def test_filtro_por_examen(ctx) -> None:
    client, factory = ctx
    examen_a = await _crear_examen(factory, titulo="Examen A")
    examen_b = await _crear_examen(factory, titulo="Examen B")
    await _crear_sesion_finalizada(factory, examen_contenido_id=examen_a)
    await _crear_sesion_finalizada(factory, examen_contenido_id=examen_b)

    resp = await client.get(
        "/api/v1/proctoring/sessions/registro",
        params={"exam_id": examen_a},
        headers=_h(["coordinador"], "coord-1"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["examen_contenido_id"] == examen_a


# --- Filtro por rango de fecha ----------------------------------------------


async def test_filtro_por_rango_de_fecha(ctx) -> None:
    client, factory = ctx
    examen_id = await _crear_examen(factory, titulo="Examen A")
    vieja = datetime.now(timezone.utc) - timedelta(days=30)
    reciente = datetime.now(timezone.utc)
    await _crear_sesion_finalizada(factory, examen_contenido_id=examen_id, finalizada_en=vieja)
    await _crear_sesion_finalizada(factory, examen_contenido_id=examen_id, finalizada_en=reciente)

    desde = (reciente - timedelta(days=1)).isoformat()
    resp = await client.get(
        "/api/v1/proctoring/sessions/registro",
        params={"fecha_desde": desde},
        headers=_h(["coordinador"], "coord-1"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1


# --- Filtro por nivel de riesgo ---------------------------------------------


async def test_filtro_por_nivel_de_riesgo_alto(ctx) -> None:
    client, factory = ctx
    examen_id = await _crear_examen(factory, titulo="Examen A")
    sid_alto = await _crear_sesion_finalizada(factory, examen_contenido_id=examen_id, alumno_idnumber="riesgoso")
    # 2 eventos criticos (peso fallback 80 c/u, cap 100) -> score alto (>=70 default).
    await _crear_evento(factory, sid_alto, severidad="critica")
    await _crear_evento(factory, sid_alto, severidad="critica")

    sid_bajo = await _crear_sesion_finalizada(factory, examen_contenido_id=examen_id, alumno_idnumber="tranquilo")
    # Sin eventos -> score 0 -> bajo.

    resp = await client.get(
        "/api/v1/proctoring/sessions/registro",
        params={"nivel_riesgo": "alto"},
        headers=_h(["coordinador"], "coord-1"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == sid_alto
    for item in body["items"]:
        assert item["id"] != sid_bajo


async def test_filtro_por_nivel_de_riesgo_bajo(ctx) -> None:
    client, factory = ctx
    examen_id = await _crear_examen(factory, titulo="Examen A")
    sid_alto = await _crear_sesion_finalizada(factory, examen_contenido_id=examen_id, alumno_idnumber="riesgoso")
    await _crear_evento(factory, sid_alto, severidad="critica")
    await _crear_evento(factory, sid_alto, severidad="critica")
    sid_bajo = await _crear_sesion_finalizada(factory, examen_contenido_id=examen_id, alumno_idnumber="tranquilo")

    resp = await client.get(
        "/api/v1/proctoring/sessions/registro",
        params={"nivel_riesgo": "bajo"},
        headers=_h(["coordinador"], "coord-1"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == sid_bajo


async def test_nivel_riesgo_invalido_422(ctx) -> None:
    client, _ = ctx
    resp = await client.get(
        "/api/v1/proctoring/sessions/registro",
        params={"nivel_riesgo": "extremo"},
        headers=_h(["coordinador"], "coord-1"),
    )
    assert resp.status_code == 422


# --- Solo finalizadas --------------------------------------------------------


async def test_solo_lista_sesiones_finalizadas(ctx) -> None:
    client, factory = ctx
    examen_id = await _crear_examen(factory, titulo="Examen A")
    from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel

    async with factory() as session:
        activa = ProctoringSessionModel(
            modo="examen", examen_contenido_id=examen_id, alumno_idnumber="en-curso"
        )
        session.add(activa)
        await session.commit()
    await _crear_sesion_finalizada(factory, examen_contenido_id=examen_id)

    resp = await client.get(
        "/api/v1/proctoring/sessions/registro",
        headers=_h(["coordinador"], "coord-1"),
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


# --- Scoping por comision (tutor) -------------------------------------------


async def test_tutor_solo_ve_su_comision_en_el_registro(ctx) -> None:
    client, factory = ctx
    tutor_a = str(uuid.uuid4())
    tutor_b = str(uuid.uuid4())
    examen_a = await _crear_examen(factory, titulo="Examen A", docente_id=tutor_a)
    examen_b = await _crear_examen(factory, titulo="Examen B", docente_id=tutor_b)
    await _crear_sesion_finalizada(factory, examen_contenido_id=examen_a)
    await _crear_sesion_finalizada(factory, examen_contenido_id=examen_b)

    resp = await client.get(
        "/api/v1/proctoring/sessions/registro",
        headers=_h(["tutor"], tutor_a),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["examen_contenido_id"] == examen_a


# --- Catalogo de examenes con sesiones ---------------------------------------


async def test_catalogo_examenes_solo_los_que_tienen_sesiones(ctx) -> None:
    client, factory = ctx
    examen_con_sesion = await _crear_examen(factory, titulo="Con sesion")
    await _crear_examen(factory, titulo="Sin sesion")
    await _crear_sesion_finalizada(factory, examen_contenido_id=examen_con_sesion)

    resp = await client.get(
        "/api/v1/proctoring/sessions/registro/examenes",
        headers=_h(["coordinador"], "coord-1"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == examen_con_sesion
    assert body[0]["titulo"] == "Con sesion"


# --- Agregados sobre el TOTAL filtrado (C-76 tarea 19.3/19.5) ---------------


async def test_agregados_reflejan_el_total_filtrado_no_la_pagina(ctx) -> None:
    """Con page_size chico y mas resultados totales, los agregados (distribucion
    de riesgo, en_cola_revision) tienen que contar sobre las 12 sesiones
    filtradas, NO solo sobre los 5 items que trae la pagina actual.

    C-76 tarea 20.4: `total_eventos`/`total_discrepancias` (tarea 19) se
    retiraron de la respuesta — reemplazados por `en_cola_revision`."""
    client, factory = ctx
    examen_id = await _crear_examen(factory, titulo="Examen A")

    # 10 sesiones "bajo" (sin eventos) + 2 sesiones "alto" (2 eventos criticos c/u).
    for i in range(10):
        await _crear_sesion_finalizada(factory, examen_contenido_id=examen_id, alumno_idnumber=f"bajo-{i}")
    for i in range(2):
        sid = await _crear_sesion_finalizada(factory, examen_contenido_id=examen_id, alumno_idnumber=f"alto-{i}")
        await _crear_evento(factory, sid, severidad="critica")
        await _crear_evento(factory, sid, severidad="critica")

    resp = await client.get(
        "/api/v1/proctoring/sessions/registro",
        params={"page": 1, "page_size": 5},
        headers=_h(["coordinador"], "coord-1"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 12
    assert len(body["items"]) == 5  # la pagina actual, NO el universo filtrado

    assert "total_eventos" not in body
    assert "total_discrepancias" not in body
    assert body["riesgo_bajo"] == 10
    assert body["riesgo_medio"] == 0
    assert body["riesgo_alto"] == 2
    assert body["en_cola_revision"] == 2  # score >= umbral alto, mismo total que riesgo_alto


async def test_agregados_respetan_el_filtro_de_nivel_de_riesgo(ctx) -> None:
    """Si se filtra por nivel_riesgo=alto, los agregados tienen que reflejar
    SOLO las sesiones que matchean el filtro (no el universo completo de
    sesiones finalizadas)."""
    client, factory = ctx
    examen_id = await _crear_examen(factory, titulo="Examen A")

    sid_alto = await _crear_sesion_finalizada(factory, examen_contenido_id=examen_id, alumno_idnumber="riesgoso")
    await _crear_evento(factory, sid_alto, severidad="critica")
    await _crear_evento(factory, sid_alto, severidad="critica")
    await _crear_sesion_finalizada(factory, examen_contenido_id=examen_id, alumno_idnumber="tranquilo")

    resp = await client.get(
        "/api/v1/proctoring/sessions/registro",
        params={"nivel_riesgo": "alto"},
        headers=_h(["coordinador"], "coord-1"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["riesgo_bajo"] == 0
    assert body["riesgo_medio"] == 0
    assert body["riesgo_alto"] == 1
    assert body["en_cola_revision"] == 1


async def test_catalogo_examenes_tutor_acotado_a_su_comision(ctx) -> None:
    client, factory = ctx
    tutor_a = str(uuid.uuid4())
    tutor_b = str(uuid.uuid4())
    examen_a = await _crear_examen(factory, titulo="Examen A", docente_id=tutor_a)
    examen_b = await _crear_examen(factory, titulo="Examen B", docente_id=tutor_b)
    await _crear_sesion_finalizada(factory, examen_contenido_id=examen_a)
    await _crear_sesion_finalizada(factory, examen_contenido_id=examen_b)

    resp = await client.get(
        "/api/v1/proctoring/sessions/registro/examenes",
        headers=_h(["tutor"], tutor_a),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == examen_a
