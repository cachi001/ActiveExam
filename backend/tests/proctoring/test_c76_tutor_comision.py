"""C-76 bloques 6 y 8 — chat/pausa tutor↔alumno + supervisión acotada por comisión.

D2: el TUTOR ve/opera solo sesiones de examenes cuya comision tiene a SU usuario
como docente a cargo (asignar_docente, C-73 §9). COORDINADOR/REVISOR/ADMIN_SISTEMA
son de alcance institucional (global).
D4: el actor de chat pasa de 'proctor' a 'tutor'; el alumno no inicia el hilo.

DB real (DATABASE_URL). Sin mocks (regla dura #4). Fixture propia (function-scoped)
por la misma razon documentada en test_c76_pausas_limite.py: fixtures async
SESSION-scoped disparan "no current event loop" en este entorno (pre-existente,
independiente de este change).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.asyncio

_TABLAS = (
    "mensaje_chat",
    "pausa_autorizada",
    "proctoring_event",
    "proctoring_biometria",
    "proctoring_session",
    "comision",
    "materia",
    "examen_contenido",
    "usuario",
)

_TEST_JWT_SECRET = b"c76-tutor-comision-test-secret"
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
    from app.infrastructure.persistence.models.chat_pausa import (
        MensajeChatModel,
        PausaAutorizadaModel,
    )
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
        await conn.run_sync(MensajeChatModel.__table__.create, checkfirst=True)
        await conn.run_sync(PausaAutorizadaModel.__table__.create, checkfirst=True)

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


async def _crear_comision_con_docente(factory, *, docente_id: str | None) -> tuple[str, str]:
    """Crea materia + comision (+ usuario docente si corresponde). Devuelve
    (comision_id, examen_contenido_id)."""
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
                    email="tutor@uni.edu",
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
        examen = ExamenContenidoModel(titulo="Examen Test", comision_id=comision.id)
        session.add(examen)
        await session.commit()
        return comision.id, examen.id


async def _crear_sesion_con_examen(factory, examen_contenido_id: str) -> str:
    """Crea la sesion directo por DB (no via POST /sessions): el endpoint aplica
    el gate de inscripcion (C-71, `verificar_inscripcion`), que es un mecanismo
    DISTINTO al que este test cubre (scoping de supervision por comision, C-76
    bloque 8) y no queremos poblar la tabla `inscripcion` solo para esquivarlo."""
    from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel

    async with factory() as session:
        s = ProctoringSessionModel(
            modo="examen",
            examen_contenido_id=examen_contenido_id,
            alumno_idnumber="alumno-1",
        )
        session.add(s)
        await session.commit()
        await session.refresh(s)
        return s.id


# --- Bloque 6: chat tutor/alumno --------------------------------------------


async def test_alumno_no_puede_iniciar_el_chat(ctx) -> None:
    client, _ = ctx
    resp = await client.post(
        "/api/v1/proctoring/sessions", json={"modo": "test"}, headers=_h(["estudiante"], "a1")
    )
    sid = resp.json()["id"]
    r = await client.post(
        f"/api/v1/proctoring/sessions/{sid}/chat",
        json={"autor": "alumno", "texto": "hola"},
        headers=_h(["estudiante"], "a1"),
    )
    assert r.status_code == 403


async def test_tutor_inicia_y_alumno_responde(ctx) -> None:
    client, _ = ctx
    resp = await client.post(
        "/api/v1/proctoring/sessions", json={"modo": "test"}, headers=_h(["estudiante"], "a1")
    )
    sid = resp.json()["id"]
    r1 = await client.post(
        f"/api/v1/proctoring/sessions/{sid}/chat",
        json={"autor": "tutor", "texto": "¿todo bien?"},
        headers=_h(["tutor"], "tutor-x"),
    )
    assert r1.status_code == 201
    r2 = await client.post(
        f"/api/v1/proctoring/sessions/{sid}/chat",
        json={"autor": "alumno", "texto": "si"},
        headers=_h(["estudiante"], "a1"),
    )
    assert r2.status_code == 201


# --- Bloque 8: supervisión acotada por comisión ------------------------------


async def test_tutor_ve_sesion_de_su_comision(ctx) -> None:
    client, factory = ctx
    tutor_id = str(uuid.uuid4())
    _, examen_id = await _crear_comision_con_docente(factory, docente_id=tutor_id)
    sid = await _crear_sesion_con_examen(factory, examen_id)

    resp = await client.get(
        f"/api/v1/proctoring/sessions/{sid}", headers=_h(["tutor"], tutor_id)
    )
    assert resp.status_code == 200


async def test_tutor_403_fuera_de_su_comision(ctx) -> None:
    client, factory = ctx
    tutor_dueno = str(uuid.uuid4())
    tutor_ajeno = str(uuid.uuid4())
    _, examen_id = await _crear_comision_con_docente(factory, docente_id=tutor_dueno)
    sid = await _crear_sesion_con_examen(factory, examen_id)

    resp = await client.get(
        f"/api/v1/proctoring/sessions/{sid}", headers=_h(["tutor"], tutor_ajeno)
    )
    assert resp.status_code == 403


async def test_coordinador_ve_todo(ctx) -> None:
    client, factory = ctx
    tutor_dueno = str(uuid.uuid4())
    _, examen_id = await _crear_comision_con_docente(factory, docente_id=tutor_dueno)
    sid = await _crear_sesion_con_examen(factory, examen_id)

    resp = await client.get(
        f"/api/v1/proctoring/sessions/{sid}", headers=_h(["coordinador"], "coord-1")
    )
    assert resp.status_code == 200


async def test_listado_tutor_solo_muestra_su_comision(ctx) -> None:
    client, factory = ctx
    tutor_a = str(uuid.uuid4())
    tutor_b = str(uuid.uuid4())
    _, examen_a = await _crear_comision_con_docente(factory, docente_id=tutor_a)
    _, examen_b = await _crear_comision_con_docente(factory, docente_id=tutor_b)
    await _crear_sesion_con_examen(factory, examen_a)
    await _crear_sesion_con_examen(factory, examen_b)

    resp = await client.get(
        "/api/v1/proctoring/sessions", headers=_h(["tutor"], tutor_a)
    )
    assert resp.status_code == 200
    sesiones = resp.json()
    assert len(sesiones) == 1
    assert sesiones[0]["examen_contenido_id"] == examen_a


async def test_listado_coordinador_ve_todas(ctx) -> None:
    client, factory = ctx
    tutor_a = str(uuid.uuid4())
    tutor_b = str(uuid.uuid4())
    _, examen_a = await _crear_comision_con_docente(factory, docente_id=tutor_a)
    _, examen_b = await _crear_comision_con_docente(factory, docente_id=tutor_b)
    await _crear_sesion_con_examen(factory, examen_a)
    await _crear_sesion_con_examen(factory, examen_b)

    resp = await client.get(
        "/api/v1/proctoring/sessions", headers=_h(["coordinador"], "coord-1")
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_tutor_rechazado_al_aprobar_pausa_de_otra_comision(ctx) -> None:
    client, factory = ctx
    tutor_dueno = str(uuid.uuid4())
    tutor_ajeno = str(uuid.uuid4())
    _, examen_id = await _crear_comision_con_docente(factory, docente_id=tutor_dueno)
    sid = await _crear_sesion_con_examen(factory, examen_id)

    r = await client.post(
        f"/api/v1/proctoring/sessions/{sid}/pausas",
        json={"motivo": "baño"},
        headers=_h(["estudiante"], "alumno-1"),
    )
    pausa_id = r.json()["id"]

    resp = await client.patch(
        f"/api/v1/proctoring/pausas/{pausa_id}",
        json={"accion": "aprobar", "tutor_actor": tutor_ajeno},
        headers=_h(["tutor"], tutor_ajeno),
    )
    assert resp.status_code == 403


async def test_tutor_dueno_puede_aprobar_pausa_de_su_comision(ctx) -> None:
    client, factory = ctx
    tutor_dueno = str(uuid.uuid4())
    _, examen_id = await _crear_comision_con_docente(factory, docente_id=tutor_dueno)
    sid = await _crear_sesion_con_examen(factory, examen_id)

    r = await client.post(
        f"/api/v1/proctoring/sessions/{sid}/pausas",
        json={"motivo": "baño"},
        headers=_h(["estudiante"], "alumno-1"),
    )
    pausa_id = r.json()["id"]

    resp = await client.patch(
        f"/api/v1/proctoring/pausas/{pausa_id}",
        json={"accion": "aprobar", "tutor_actor": tutor_dueno},
        headers=_h(["tutor"], tutor_dueno),
    )
    assert resp.status_code == 200
    assert resp.json()["estado"] == "aprobada"
