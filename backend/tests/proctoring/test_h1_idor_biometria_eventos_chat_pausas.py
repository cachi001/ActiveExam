"""Pentest seguridad — H1 (IDOR) + biometría sin auth, hallazgos del 2026-08-21.

Fixes derivados de la auditoría de seguridad (mismo patrón que
``test_c69_sesion_propiedad.py`` para respuestas/finalizar, ahora extendido a
biometría/eventos/chat/pausas):

- CRÍTICO: ``POST /sessions/{id}/biometria`` no exigía NINGÚN token — cualquiera
  que conociera un ``session_id`` ajeno podía plantar un veredicto biométrico
  falso. Ahora exige auth Y pertenencia (401 sin token, 403 sesión ajena).
- CRÍTICO: ``POST /sessions/{id}/events`` solo exigía un token válido de
  CUALQUIER rol — nunca verificaba que la sesión fuera del alumno autenticado.
  Ahora exige pertenencia (403 sesión ajena).
- Mismo patrón en chat (lectura + escritura) y pausas (solicitar/listar/finalizar),
  preservando el acceso legítimo del alumno dueño y de roles de supervisión con
  alcance institucional (coordinador/admin) — no se rompe la supervisión en vivo.

DB real (DATABASE_URL). Sin mocks de DB (regla dura de código).

Correr:
    DATABASE_URL=postgresql+asyncpg://... pytest tests/proctoring/test_h1_idor_biometria_eventos_chat_pausas.py -v
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.models.chat_pausa import (  # noqa: F401
    MensajeChatModel,
    PausaAutorizadaModel,
)
from app.infrastructure.persistence.models.exam_content import (  # noqa: F401
    ExamenContenidoModel,
)
from app.infrastructure.persistence.models.proctoring import (  # noqa: F401
    ProctoringBiometriaModel,
    ProctoringEventModel,
    ProctoringSessionModel,
)
from app.infrastructure.persistence.models.transactional import (
    ConfiguracionSistemaModel,
)
from tests.proctoring.conftest import _build_test_jwt_validator, auth_headers

pytestmark = pytest.mark.asyncio

_BASE = "/api/v1/proctoring"

# Dos alumnos DISTINTOS (username = preferred_username del JWT), un coordinador y
# un admin. Desde c-79 el coordinador NO es institucional: está acotado a SUS
# materias. El alcance institucional, que es el que no se puede romper al cerrar
# el IDOR, hoy lo tiene admin_sistema.
_OWNER = auth_headers(["estudiante"], username="alumno-owner", email="owner@uni.edu")
_ATACANTE = auth_headers(["estudiante"], username="alumno-atacante", email="atk@uni.edu")
_COORDINADOR = auth_headers(["coordinador"], username="coord-1", email="coord@uni.edu")
_ADMIN = auth_headers(["admin_sistema"], username="admin-1", email="admin@uni.edu")

_DROP = [
    "mensaje_chat",
    "pausa_autorizada",
    "examen_contenido",
    "proctoring_biometria",
    "proctoring_event",
    "proctoring_session",
]
_CREATE = [
    ExamenContenidoModel.__table__,
    ProctoringSessionModel.__table__,
    ProctoringEventModel.__table__,
    ProctoringBiometriaModel.__table__,
    MensajeChatModel.__table__,
    PausaAutorizadaModel.__table__,
]


@pytest.fixture(scope="module")
def db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL no seteada — tests de integración omitidos")
    return url


@pytest_asyncio.fixture(scope="module")
async def engine(db_url: str):
    eng = create_async_engine(db_url, pool_pre_ping=True, future=True, poolclass=NullPool)
    async with eng.begin() as conn:
        for t in _DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
        await conn.run_sync(Base.metadata.create_all, tables=_CREATE)
    yield eng
    async with eng.begin() as conn:
        for t in _DROP:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
    await eng.dispose()


@pytest.fixture(scope="module")
def reinferencia():
    # Una sola instancia por módulo (evita el deadlock de GC del adapter MediaPipe).
    from app.infrastructure.reinferencia.mediapipe_adapter import MediaPipeReinferencia

    return MediaPipeReinferencia()


@pytest.fixture(scope="module")
def app(engine, reinferencia):
    from fastapi import FastAPI

    from app.infrastructure.persistence.session_activeexam import create_activeexam_session_factory
    from app.presentation.api.v1.proctoring.router import create_proctoring_router

    factory = create_activeexam_session_factory(engine)
    router = create_proctoring_router(session_factory=factory, reinferencia=reinferencia)
    a = FastAPI()
    a.state.jwt_validator = _build_test_jwt_validator()
    a.include_router(router, prefix="/api/v1/proctoring")
    return a


@pytest_asyncio.fixture(autouse=True)
async def _limpiar(engine):
    """Trunca todas las tablas antes de cada test (aislamiento)."""
    async with engine.begin() as conn:
        nombres = ", ".join(f'"{t}"' for t in _DROP)
        await conn.execute(text(f"TRUNCATE {nombres} RESTART IDENTITY CASCADE"))
    yield


@pytest_asyncio.fixture(autouse=True)
async def _seed_config(engine):
    """Asegura la fila 'global' de configuracion_sistema (umbral_cola_revision):
    ``crear_o_reanudar_sesion`` la lee SIEMPRE al crear una sesión (foto de config,
    migración 0083) y sin ella el POST /sessions responde 503. Esta tabla vive
    en la DB compartida (no está en ``_DROP``/``_CREATE``, que solo maneja las
    tablas propias de este módulo) — mismo patrón que otros tests de integración
    del repo (ver test_c71_writeback_gate_integration.py)."""
    async with async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)() as s:
        existing = await s.get(ConfiguracionSistemaModel, "global")
        if existing is None:
            s.add(ConfiguracionSistemaModel(id="global", umbral_cola_revision=70))
            await s.commit()
    yield


@pytest_asyncio.fixture
async def db(engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
        await s.rollback()


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _crear_sesion(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(f"{_BASE}/sessions", json={"modo": "test"}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _evento_body(tipo: str = "cambio_pestana") -> dict:
    return {
        "tipo": tipo,
        "severidad": "baja",
        "ts_cliente": datetime.now(timezone.utc).isoformat(),
    }


async def _eventos_de(db: AsyncSession, session_id: str) -> list[ProctoringEventModel]:
    await db.commit()
    return list(
        (
            await db.execute(
                select(ProctoringEventModel).where(
                    ProctoringEventModel.session_id == session_id
                )
            )
        )
        .scalars()
        .all()
    )


# ---------------------------------------------------------------------------
# CRÍTICO 1 — biometría sin auth / IDOR
# ---------------------------------------------------------------------------


async def test_biometria_sin_token_401(client: AsyncClient) -> None:
    """Sin Authorization header → 401 (antes: 200, sin exigir NADA)."""
    sid = await _crear_sesion(client, _OWNER)
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/biometria",
        json={"liveness_ok": True, "retos_resueltos": [], "resultado": "verificado"},
    )
    assert resp.status_code == 401, resp.text


async def test_biometria_de_otro_alumno_403(client: AsyncClient, db: AsyncSession) -> None:
    """El atacante intenta plantar un veredicto biométrico en la sesión del owner → 403."""
    sid = await _crear_sesion(client, _OWNER)
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/biometria",
        json={"liveness_ok": True, "retos_resueltos": [], "resultado": "verificado"},
        headers=_ATACANTE,
    )
    assert resp.status_code == 403, resp.text

    row = (
        await db.execute(
            select(ProctoringBiometriaModel).where(
                ProctoringBiometriaModel.session_id == sid
            )
        )
    ).scalar_one_or_none()
    assert row is None, "el atacante no debe poder persistir ningún veredicto"


async def test_biometria_del_dueno_200(client: AsyncClient) -> None:
    """Happy path: el dueño guarda su propio resultado biométrico."""
    sid = await _crear_sesion(client, _OWNER)
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/biometria",
        json={"liveness_ok": True, "retos_resueltos": [], "resultado": "verificado"},
        headers=_OWNER,
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# CRÍTICO 2 — IDOR en eventos
# ---------------------------------------------------------------------------


async def test_evento_de_otro_alumno_403(client: AsyncClient, db: AsyncSession) -> None:
    """El atacante intenta inyectar un evento falso en la sesión del owner → 403."""
    sid = await _crear_sesion(client, _OWNER)
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/events", json=_evento_body(), headers=_ATACANTE
    )
    assert resp.status_code == 403, resp.text
    assert await _eventos_de(db, sid) == []


async def test_evento_del_dueno_201(client: AsyncClient) -> None:
    """Happy path: el dueño postea su propio evento de detección."""
    sid = await _crear_sesion(client, _OWNER)
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/events", json=_evento_body(), headers=_OWNER
    )
    assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# IDOR en chat
# ---------------------------------------------------------------------------


async def test_leer_chat_de_otro_alumno_403(client: AsyncClient) -> None:
    sid = await _crear_sesion(client, _OWNER)
    resp = await client.get(f"{_BASE}/sessions/{sid}/chat", headers=_ATACANTE)
    assert resp.status_code == 403, resp.text


async def test_postear_chat_como_alumno_en_sesion_ajena_403(client: AsyncClient) -> None:
    sid = await _crear_sesion(client, _OWNER)
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/chat",
        json={"autor": "alumno", "texto": "hola"},
        headers=_ATACANTE,
    )
    assert resp.status_code == 403, resp.text


async def test_postear_chat_como_tutor_sin_supervision_403(client: AsyncClient) -> None:
    """Un alumno no puede hacerse pasar por 'tutor' en el chat de otra sesión."""
    sid = await _crear_sesion(client, _OWNER)
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/chat",
        json={"autor": "tutor", "texto": "hola"},
        headers=_ATACANTE,
    )
    assert resp.status_code == 403, resp.text


async def test_dueno_lee_su_propio_chat_200(client: AsyncClient) -> None:
    sid = await _crear_sesion(client, _OWNER)
    resp = await client.get(f"{_BASE}/sessions/{sid}/chat", headers=_OWNER)
    assert resp.status_code == 200, resp.text
    assert resp.json() == []


async def test_supervision_institucional_no_se_rompe(client: AsyncClient) -> None:
    """No regresión: el rol de alcance institucional sigue pudiendo leer el chat y
    postear como 'tutor'. La supervisión en vivo real no se rompe al cerrar el IDOR."""
    sid = await _crear_sesion(client, _OWNER)
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/chat",
        json={"autor": "tutor", "texto": "hola desde coordinación"},
        headers=_ADMIN,
    )
    assert resp.status_code == 201, resp.text

    leer = await client.get(f"{_BASE}/sessions/{sid}/chat", headers=_ADMIN)
    assert leer.status_code == 200, leer.text
    assert len(leer.json()) == 1


async def test_coordinador_fuera_de_sus_materias_no_entra_al_chat(
    client: AsyncClient,
) -> None:
    """c-79: el coordinador dejó de ser institucional. Sobre una sesión que no
    cuelga de sus materias es tan ajeno como cualquiera, y recibe 403."""
    sid = await _crear_sesion(client, _OWNER)
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/chat",
        json={"autor": "tutor", "texto": "hola"},
        headers=_COORDINADOR,
    )
    assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# IDOR en pausas
# ---------------------------------------------------------------------------


async def test_solicitar_pausa_en_sesion_ajena_403(client: AsyncClient) -> None:
    sid = await _crear_sesion(client, _OWNER)
    resp = await client.post(
        f"{_BASE}/sessions/{sid}/pausas", json={"motivo": "corte de luz"}, headers=_ATACANTE
    )
    assert resp.status_code == 403, resp.text


async def test_listar_pausas_de_sesion_ajena_403(client: AsyncClient) -> None:
    sid = await _crear_sesion(client, _OWNER)
    resp = await client.get(f"{_BASE}/sessions/{sid}/pausas", headers=_ATACANTE)
    assert resp.status_code == 403, resp.text


async def test_dueno_solicita_y_lista_su_propia_pausa(client: AsyncClient) -> None:
    sid = await _crear_sesion(client, _OWNER)
    crear = await client.post(
        f"{_BASE}/sessions/{sid}/pausas", json={"motivo": "corte de luz"}, headers=_OWNER
    )
    assert crear.status_code == 201, crear.text

    listar = await client.get(f"{_BASE}/sessions/{sid}/pausas", headers=_OWNER)
    assert listar.status_code == 200, listar.text
    assert len(listar.json()) == 1


async def test_finalizar_pausa_de_sesion_ajena_403(client: AsyncClient) -> None:
    """El atacante conoce el pausa_id (por fuerza bruta o filtración) pero no
    puede finalizar la pausa de la sesión de otro alumno."""
    sid = await _crear_sesion(client, _OWNER)
    crear = await client.post(
        f"{_BASE}/sessions/{sid}/pausas", json={"motivo": "corte de luz"}, headers=_OWNER
    )
    pausa_id = crear.json()["id"]

    resp = await client.patch(
        f"{_BASE}/pausas/{pausa_id}/finalizar", headers=_ATACANTE
    )
    assert resp.status_code == 403, resp.text
