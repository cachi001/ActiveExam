"""c-78 F-01 (D3) — "entra a la Cola de revisión" cuenta lo mismo en todas partes.

Definición canónica: una sesión entra a la Cola si tiene un examen REAL vinculado
(`examen_contenido_id IS NOT NULL`) y su score alcanza el umbral vivo.

Cubre:
- tarea 4.5: el agregado `en_cola_revision` de GET /sessions/registro excluye las
  sesiones de diagnóstico (sin examen) aunque superen el umbral, y el LISTADO de
  esa misma pantalla sigue mostrándolas (se borran desde ahí).
- tarea 4.6: coherencia cruzada con un dataset fijo que incluye diagnóstico sobre
  el umbral — el conteo de la Cola de revisión (el predicado que consume el panel
  sobre GET /proctoring/sessions), el agregado del Registro de sesiones y el
  `sesiones_en_riesgo` de Estadísticas dan el MISMO número.

DB real (DATABASE_URL). Sin mocks (regla dura #4). Mismo patrón de fixture que
test_c76_registro_sesiones.py.
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

pytestmark = pytest.mark.asyncio

_TABLAS = (
    "proctoring_event",
    "proctoring_biometria",
    "proctoring_session",
    "comision_tutor",
    "comision",
    "materia",
    "examen_contenido",
    "usuario",
)

_TEST_JWT_SECRET = b"c78-coherencia-cola-test-secret"
_TEST_JWT_ISSUER = "activeexam-auth"
_TEST_JWT_AUDIENCE = "proctoring-api"

# Umbral por defecto del sistema cuando no hay configuración cargada. Las sesiones
# del dataset se construyen con eventos suficientes para quedar claramente de un
# lado o del otro, así que el valor exacto no condiciona el resultado.
_SEVERIDAD_ALTA = "alta"


def _db_url() -> str | None:
    return os.environ.get("DATABASE_URL")


def _h(roles: list[str], subject: str = "staff-1") -> dict:
    from app.infrastructure.auth.verifiers import encode_hs256

    token = encode_hs256(
        {
            "iss": _TEST_JWT_ISSUER,
            "aud": _TEST_JWT_AUDIENCE,
            "sub": subject,
            "preferred_username": "+".join(roles),
            "email": "test@uni.edu",
            "exp": 9999999999,
            "amr": ["otp"],
            "realm_access": {"roles": roles},
        },
        _TEST_JWT_SECRET,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def ctx():
    url = _db_url()
    if not url:
        pytest.skip("DATABASE_URL no está seteada; test de integración (DB real).")

    from app.domain.auth.token import TokenPolicy
    from app.infrastructure.auth.jwks_cache import JwksCache
    from app.infrastructure.auth.jwt_validator import JwtValidator
    from app.infrastructure.auth.verifiers import build_hs256_verify
    from app.infrastructure.persistence.models.comision_tutor import ComisionTutorModel
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
    from app.infrastructure.reinferencia.mediapipe_adapter import MediaPipeReinferencia
    from app.presentation.api.v1.proctoring.router import create_proctoring_router

    engine = create_async_engine(url, pool_pre_ping=True, future=True, poolclass=NullPool)
    async with engine.begin() as conn:
        for name in _TABLAS:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
        await conn.run_sync(UsuarioModel.__table__.create, checkfirst=True)
        await conn.run_sync(MateriaModel.__table__.create, checkfirst=True)
        await conn.run_sync(ComisionModel.__table__.create, checkfirst=True)
        await conn.run_sync(ComisionTutorModel.__table__.create, checkfirst=True)
        await conn.run_sync(ExamenContenidoModel.__table__.create, checkfirst=True)
        await conn.run_sync(ProctoringSessionModel.__table__.create, checkfirst=True)
        await conn.run_sync(ProctoringEventModel.__table__.create, checkfirst=True)
        await conn.run_sync(ProctoringBiometriaModel.__table__.create, checkfirst=True)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    app = FastAPI()
    cache = JwksCache(lambda: {"keys": [{"kid": "test-key"}]}, ttl_seconds=3600)
    policy = TokenPolicy(
        issuers_aceptados=frozenset({_TEST_JWT_ISSUER}), audience=_TEST_JWT_AUDIENCE
    )
    app.state.jwt_validator = JwtValidator(
        jwks_cache=cache, policy=policy, verify_fn=build_hs256_verify(_TEST_JWT_SECRET)
    )
    app.include_router(
        create_proctoring_router(
            session_factory=factory, reinferencia=MediaPipeReinferencia()
        ),
        prefix="/api/v1/proctoring",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, factory

    async with engine.begin() as conn:
        for name in _TABLAS:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
    await engine.dispose()


async def _crear_examen(factory) -> str:
    from app.infrastructure.persistence.models.exam_content import (
        ComisionModel,
        ExamenContenidoModel,
        MateriaModel,
    )

    sufijo = uuid.uuid4().hex[:8]
    async with factory() as session:
        materia = MateriaModel(codigo=f"MAT-{sufijo}", nombre="Materia Coherencia")
        session.add(materia)
        await session.flush()
        comision = ComisionModel(
            materia_id=materia.id,
            codigo="C1",
            nombre="Comisión 1",
            codigo_matriculacion=f"K-{sufijo}",
        )
        session.add(comision)
        await session.flush()
        examen = ExamenContenidoModel(titulo="Parcial Coherencia", comision_id=comision.id)
        session.add(examen)
        await session.commit()
        return examen.id


async def _crear_sesion(
    factory,
    *,
    examen_contenido_id: str | None,
    eventos_alta: int,
    alumno_idnumber: str,
) -> str:
    """Sesión FINALIZADA con N eventos de severidad alta (para empujar el score)."""
    from app.infrastructure.persistence.models.proctoring import (
        ProctoringEventModel,
        ProctoringSessionModel,
    )

    ahora = datetime.now(timezone.utc)
    async with factory() as session:
        s = ProctoringSessionModel(
            modo="examen" if examen_contenido_id else "test",
            examen_contenido_id=examen_contenido_id,
            alumno_idnumber=alumno_idnumber,
            alumno_email=f"{alumno_idnumber}@uni.edu",
            creada_en=ahora,
            finalizada_en=ahora,
        )
        session.add(s)
        await session.flush()
        for _ in range(eventos_alta):
            session.add(
                ProctoringEventModel(
                    session_id=s.id,
                    tipo="cara_ausente",
                    severidad=_SEVERIDAD_ALTA,
                    ts_cliente=ahora,
                    ts_backend=ahora,
                )
            )
        await session.commit()
        return s.id


async def _dataset_fijo(factory) -> dict:
    """Tres sesiones finalizadas:

    - `con_examen_alta`: examen vinculado + score sobre el umbral  → SÍ entra
    - `diagnostico_alta`: SIN examen + score sobre el umbral       → NO entra
    - `con_examen_baja`: examen vinculado + score bajo el umbral   → NO entra

    El caso del medio es exactamente el que hacía divergir los tres contadores.
    """
    examen_id = await _crear_examen(factory)
    con_examen_alta = await _crear_sesion(
        factory, examen_contenido_id=examen_id, eventos_alta=12, alumno_idnumber="al-alta"
    )
    diagnostico_alta = await _crear_sesion(
        factory, examen_contenido_id=None, eventos_alta=12, alumno_idnumber="al-diag"
    )
    con_examen_baja = await _crear_sesion(
        factory, examen_contenido_id=examen_id, eventos_alta=0, alumno_idnumber="al-baja"
    )
    return {
        "examen_id": examen_id,
        "con_examen_alta": con_examen_alta,
        "diagnostico_alta": diagnostico_alta,
        "con_examen_baja": con_examen_baja,
    }


# ---------------------------------------------------------------------------
# Tarea 4.5 — el agregado del Registro de sesiones
# ---------------------------------------------------------------------------


async def test_agregado_del_registro_excluye_las_sesiones_de_diagnostico(ctx) -> None:
    client, factory = ctx
    datos = await _dataset_fijo(factory)

    resp = await client.get(
        "/api/v1/proctoring/sessions/registro",
        params={"page": 1, "page_size": 50},
        headers=_h(["admin_sistema"]),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["en_cola_revision"] == 1, (
        "el agregado debe contar SOLO la sesión con examen vinculado sobre el "
        f"umbral; la de diagnóstico no entra a ninguna cola. Body: {body}"
    )

    # El LISTADO no cambia: la sesión de diagnóstico se sigue mostrando (desde esta
    # pantalla se la borra). Lo que se corrigió es el agregado, no la lista.
    ids_listados = {i["id"] for i in body["items"]}
    assert datos["diagnostico_alta"] in ids_listados, (
        "el listado de Registro de sesiones dejó de mostrar las sesiones de "
        "diagnóstico; eso NO es parte del arreglo"
    )
    assert datos["con_examen_alta"] in ids_listados
    assert datos["con_examen_baja"] in ids_listados


# ---------------------------------------------------------------------------
# Tarea 4.6 — coherencia cruzada de los tres consumidores
# ---------------------------------------------------------------------------


async def test_los_tres_consumidores_dan_el_mismo_numero(ctx) -> None:
    """Cola de revisión == Registro de sesiones == Estadísticas."""
    from app.application.stats.resumen_service import FiltrosStats, obtener_resumen

    client, factory = ctx
    datos = await _dataset_fijo(factory)

    # 1) Cola de revisión / Panel de administración: consumen GET /proctoring/sessions
    #    y aplican el predicado canónico (examen vinculado + score >= umbral). Se
    #    reproduce acá el MISMO predicado que `entraACola` del frontend.
    resp_sesiones = await client.get(
        "/api/v1/proctoring/sessions", headers=_h(["admin_sistema"])
    )
    assert resp_sesiones.status_code == 200, resp_sesiones.text
    sesiones = resp_sesiones.json()
    if isinstance(sesiones, dict):
        sesiones = sesiones.get("items", [])
    umbral = next(
        (
            s.get("umbral_cola_revision_efectivo")
            for s in sesiones
            if s.get("umbral_cola_revision_efectivo") is not None
        ),
        None,
    )
    assert umbral is not None, "el backend debe exponer el umbral efectivo por sesión"
    cola = sum(
        1
        for s in sesiones
        if s.get("score", 0) >= umbral
        and (s.get("examen_contenido_id") is not None or s.get("exam_id") is not None)
    )

    # 2) Registro de sesiones: el agregado del endpoint.
    resp_registro = await client.get(
        "/api/v1/proctoring/sessions/registro",
        params={"page": 1, "page_size": 50},
        headers=_h(["admin_sistema"]),
    )
    assert resp_registro.status_code == 200, resp_registro.text
    registro = resp_registro.json()["en_cola_revision"]

    # 3) Estadísticas: sesiones_en_riesgo (server-side, ya excluye las sin examen).
    async with factory() as session:
        resumen = await obtener_resumen(session, FiltrosStats())
    estadisticas = resumen.sesiones_en_riesgo

    assert cola == registro == estadisticas, (
        "los tres consumidores deben contar lo mismo con el dataset fijo "
        f"(cola={cola}, registro={registro}, estadisticas={estadisticas})"
    )
    assert cola == 1, (
        "con el dataset fijo entra UNA sola sesión: la que tiene examen vinculado y "
        f"supera el umbral (ids: {datos})"
    )
