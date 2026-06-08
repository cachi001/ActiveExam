"""Tests de integracion para c-64 — persistencia de eventos, biometria y sesion.

Cubre:
  3.1 - PATCH /sessions/{id}/finalizar: sesion existente, inexistente, idempotencia.
  3.2 - POST /sessions/{id}/events con screenshot_sha256_cliente → 201 (no 422).

Requiere Postgres real (DATABASE_URL). Sin mocks de DB (regla dura de codigo).
Tests corren contra create_proctoring_router con postgres:16-alpine via TestClient sincrono.

Para correr:
    DATABASE_URL=postgresql+asyncpg://... pytest tests/test_c64_persistencia_eventos.py -v
"""

from __future__ import annotations

import asyncio
import os

import pytest


# ---------------------------------------------------------------------------
# Config del entorno de test
# ---------------------------------------------------------------------------


def _get_test_db_url() -> str | None:
    return os.environ.get("DATABASE_URL")


def _setup_db_tables(url: str) -> None:
    """Crea las tablas slim en la DB de test (drop CASCADE + create)."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.infrastructure.persistence.models.proctoring import (  # noqa: F401
        ProctoringBiometriaModel,
        ProctoringEventModel,
        ProctoringSessionModel,
    )

    async def _run() -> None:
        engine = create_async_engine(url, pool_pre_ping=True, future=True)
        async with engine.begin() as conn:
            await conn.execute(text("DROP TABLE IF EXISTS proctoring_biometria CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS proctoring_event CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS proctoring_session CASCADE"))
            await conn.run_sync(ProctoringSessionModel.__table__.create)
            await conn.run_sync(ProctoringEventModel.__table__.create)
            await conn.run_sync(ProctoringBiometriaModel.__table__.create)
        await engine.dispose()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_url_c64() -> str:
    url = _get_test_db_url()
    if not url:
        pytest.skip(
            "DATABASE_URL no esta seteada. "
            "Para tests de integracion: DATABASE_URL=postgresql+asyncpg://... pytest tests/test_c64_persistencia_eventos.py"
        )
    # Setup tablas una sola vez por modulo
    _setup_db_tables(url)
    return url


@pytest.fixture
def client(db_url_c64: str):
    """TestClient sincrono con engine fresco por test.

    Cada test crea su propio engine para evitar el problema de event loop
    cerrado entre tests (anyio crea/destruye el loop por TestClient).
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.infrastructure.persistence.session_slim import create_slim_session_factory
    from app.infrastructure.reinferencia.mediapipe_adapter import MediaPipeReinferencia
    from app.presentation.api.v1.proctoring.router import create_proctoring_router
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.testclient import TestClient

    engine = create_async_engine(db_url_c64, pool_pre_ping=True, future=True)
    factory = create_slim_session_factory(engine)
    reinferencia = MediaPipeReinferencia()
    proctoring_router = create_proctoring_router(
        session_factory=factory,
        reinferencia=reinferencia,
    )
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(proctoring_router, prefix="/api/v1/proctoring")

    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _crear_sesion(client) -> str:
    resp = client.post(
        "/api/v1/proctoring/sessions",
        json={"modo": "examen", "etiqueta": "test-c64"},
    )
    assert resp.status_code == 201, f"No se pudo crear sesion: {resp.text}"
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Tests 3.1 — PATCH /sessions/{id}/finalizar
# ---------------------------------------------------------------------------


def test_finalizar_sesion_existente_200(client) -> None:
    """PATCH /sessions/{id}/finalizar → 200 con id y finalizada_en seteado."""
    session_id = _crear_sesion(client)

    resp = client.patch(f"/api/v1/proctoring/sessions/{session_id}/finalizar")
    assert resp.status_code == 200, f"Esperado 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["id"] == session_id
    assert data["finalizada_en"] is not None, "finalizada_en debe quedar seteado"


def test_finalizar_sesion_inexistente_404(client) -> None:
    """PATCH /sessions/{id}/finalizar con id inexistente → 404."""
    resp = client.patch(
        "/api/v1/proctoring/sessions/00000000-0000-0000-0000-000000000000/finalizar"
    )
    assert resp.status_code == 404, f"Esperado 404, got {resp.status_code}: {resp.text}"


def test_finalizar_sesion_idempotente(client) -> None:
    """PATCH /sessions/{id}/finalizar llamado dos veces → 200 ambas veces, misma finalizada_en."""
    session_id = _crear_sesion(client)

    # Primera llamada: setea finalizada_en
    resp1 = client.patch(f"/api/v1/proctoring/sessions/{session_id}/finalizar")
    assert resp1.status_code == 200
    finalizada_en_1 = resp1.json()["finalizada_en"]
    assert finalizada_en_1 is not None

    # Segunda llamada: idempotente — retorna 200 con el mismo finalizada_en
    resp2 = client.patch(f"/api/v1/proctoring/sessions/{session_id}/finalizar")
    assert resp2.status_code == 200, f"Segunda llamada esperada 200, got {resp2.status_code}"
    finalizada_en_2 = resp2.json()["finalizada_en"]
    # El timestamp no debe cambiar (idempotencia)
    assert finalizada_en_2 == finalizada_en_1, (
        f"finalizada_en cambio entre llamadas: {finalizada_en_1!r} -> {finalizada_en_2!r}"
    )


# ---------------------------------------------------------------------------
# Tests 3.2 — POST /sessions/{id}/events acepta screenshot_sha256_cliente
# ---------------------------------------------------------------------------


def test_evento_con_screenshot_sha256_cliente_acepta_201(client) -> None:
    """POST /events con screenshot_sha256_cliente → 201 (no 422).

    El campo se acepta en el schema (extra='forbid' no lo rechaza) aunque
    ProctoringEventModel no tenga esa columna — el servicio lo ignora (C-64 D2).
    """
    session_id = _crear_sesion(client)
    resp = client.post(
        f"/api/v1/proctoring/sessions/{session_id}/events",
        json={
            "tipo": "FACE_ABSENT",
            "severidad": "alto",
            "ts_cliente": "2026-06-08T10:00:00Z",
            "face_count_cliente": 0,
            "screenshot_sha256_cliente": "a" * 64,  # SHA-256 hex simulado
        },
    )
    assert resp.status_code == 201, (
        f"Esperado 201 (campo aceptado), got {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert "evento_id" in data
    assert data["veredicto_reinferencia"] in ("coincide", "discrepancia", "no_evaluado")


def test_evento_con_screenshot_sha256_cliente_none_acepta_201(client) -> None:
    """POST /events con screenshot_sha256_cliente=null → 201 (campo opcional)."""
    session_id = _crear_sesion(client)
    resp = client.post(
        f"/api/v1/proctoring/sessions/{session_id}/events",
        json={
            "tipo": "GAZE_DEVIATION",
            "severidad": "bajo",
            "ts_cliente": "2026-06-08T10:01:00Z",
            "screenshot_sha256_cliente": None,
        },
    )
    assert resp.status_code == 201, (
        f"Esperado 201 con campo null, got {resp.status_code}: {resp.text}"
    )


def test_evento_sin_screenshot_sha256_cliente_acepta_201(client) -> None:
    """POST /events sin screenshot_sha256_cliente → 201 (campo completamente ausente)."""
    session_id = _crear_sesion(client)
    resp = client.post(
        f"/api/v1/proctoring/sessions/{session_id}/events",
        json={
            "tipo": "MULTIPLE_FACES",
            "severidad": "critico",
            "ts_cliente": "2026-06-08T10:02:00Z",
            "face_count_cliente": 3,
        },
    )
    assert resp.status_code == 201, (
        f"Esperado 201 sin el campo, got {resp.status_code}: {resp.text}"
    )
