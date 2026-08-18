"""C-76 sección 15 — evidencia de eventos sin captura (cambio_pestana / copiar_pegar).

Decidido con el dueño (ver `openspec/changes/c-76-panel-supervision-en-vivo/tasks.md`
sección 15): estos dos eventos ahora activan `trigger_evidence` en el cliente
(`stateTransitionRules.ts`), pero el screenshot que disparan NO prueba que el
evento ocurrió — es CONTEXTO VISUAL (a diferencia de `multiples_rostros`/
`rostro_ausente`, donde el servidor re-infiere la MISMA imagen). La evidencia
REAL nueva es el hash SHA-256 (`clipboard_sha256`) de lo pegado en `copiar_pegar`
— NUNCA el contenido en claro (Ley 25.326).

Este test cubre el lado backend (15.3/15.4):
  1. `payload.clipboard_sha256` se acepta y persiste tal cual (JSONB libre, sin
     migración — `payload` ya es `dict | None` en el modelo).
  2. La sola presencia de esa evidencia NUEVA (screenshot / clipboard_sha256) NO
     cambia el score: `calcular_score` (application/proctoring/scoring.py) y
     `peso_evento`/`score_incremental` (domain/scoring/risk_score.py) leen
     únicamente `tipo`/`severidad`/`persistencia` — nunca `payload` (doble red,
     mismo patrón que la tarea 5.3/5.4 de captura_pausa).

DB real (DATABASE_URL vía fixtures `client`/`db_session` del conftest). Sin
mocks de DB (regla dura #4).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring.scoring import calcular_score
from app.domain.scoring.risk_score import EventoScore, score_incremental
from app.infrastructure.persistence.models.proctoring import ProctoringEventModel

_CLIPBOARD_SHA256 = "b" * 64  # hash de ejemplo — nunca el contenido en claro


async def _crear_sesion(client: AsyncClient) -> str:
    resp = await client.post("/api/v1/proctoring/sessions", json={"modo": "test"})
    assert resp.status_code == 201
    return resp.json()["id"]


# --- 15.3: clipboard_sha256 se persiste en el payload, sin contenido ---------


@pytest.mark.asyncio
async def test_copiar_pegar_persiste_clipboard_sha256_en_payload(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    session_id = await _crear_sesion(client)
    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/events",
        json={
            "tipo": "copiar_pegar",
            "severidad": "media",
            "ts_cliente": "2026-08-17T10:00:00Z",
            "payload": {"accion": "paste", "clipboard_sha256": _CLIPBOARD_SHA256},
        },
    )
    assert resp.status_code == 201
    evento_id = resp.json()["evento_id"]

    persistido = await db_session.get(ProctoringEventModel, evento_id)
    assert persistido is not None
    assert persistido.payload is not None
    assert persistido.payload["clipboard_sha256"] == _CLIPBOARD_SHA256
    assert persistido.payload["accion"] == "paste"


@pytest.mark.asyncio
async def test_copiar_pegar_sin_clipboard_sha256_sigue_aceptandose(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Triangulación: el campo es OPCIONAL — un paste de imagen (sin text/plain
    en el evento) no debe romper la ingesta ni forzar el campo."""
    session_id = await _crear_sesion(client)
    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/events",
        json={
            "tipo": "copiar_pegar",
            "severidad": "media",
            "ts_cliente": "2026-08-17T10:00:00Z",
            "payload": {"accion": "paste"},
        },
    )
    assert resp.status_code == 201
    evento_id = resp.json()["evento_id"]

    persistido = await db_session.get(ProctoringEventModel, evento_id)
    assert persistido is not None
    assert "clipboard_sha256" not in (persistido.payload or {})


@pytest.mark.asyncio
async def test_cambio_pestana_con_screenshot_persiste_sha256_de_la_captura(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """cambio_pestana ahora puede adjuntar screenshot (C-76 15.1) — el backend lo
    re-hashea igual que a cualquier otro evento (regla dura #6, cliente = sensor
    no confiable)."""
    png_1x1_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGA"
        "WjR9awAAAABJRU5ErkJggg=="
    )
    session_id = await _crear_sesion(client)
    resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/events",
        json={
            "tipo": "cambio_pestana",
            "severidad": "media",
            "ts_cliente": "2026-08-17T10:00:00Z",
            "screenshot_base64": png_1x1_b64,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["screenshot_sha256"] is not None
    assert len(data["screenshot_sha256"]) == 64


# --- 15.4: la evidencia nueva NO afecta el score automáticamente -------------


@pytest.mark.asyncio
async def test_score_on_the_fly_ignora_clipboard_sha256(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """calcular_score (vista del proctor) da el MISMO resultado con o sin
    clipboard_sha256 en el payload — el score depende solo de tipo/severidad."""
    session_id = await _crear_sesion(client)
    await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/events",
        json={
            "tipo": "copiar_pegar",
            "severidad": "media",
            "ts_cliente": "2026-08-17T10:00:00Z",
            "payload": {"accion": "paste", "clipboard_sha256": _CLIPBOARD_SHA256},
        },
    )
    result = await db_session.execute(
        select(ProctoringEventModel).where(ProctoringEventModel.session_id == session_id)
    )
    eventos = result.scalars().all()
    assert len(eventos) == 1

    score_con_hash = calcular_score(eventos)

    # Mismo evento, sin el hash en el payload -> mismo score.
    eventos[0].payload = {"accion": "paste"}
    score_sin_hash = calcular_score(eventos)

    assert score_con_hash == score_sin_hash


def test_score_incremental_puro_ignora_payload_no_solo_tipo_severidad() -> None:
    """Triangulación con datos DISTINTOS (dominio puro, sin DB): dos EventoScore
    con el mismo tipo/severidad pero que "representarían" payloads distintos
    (EventoScore ni siquiera tiene campo payload) pesan exactamente igual —
    prueba estructural de que el motor de cierre no puede leer evidencia nueva."""
    base = EventoScore(tipo="copiar_pegar", severidad="media", ts_ms=0, persistencia=1)
    otro = EventoScore(tipo="copiar_pegar", severidad="media", ts_ms=0, persistencia=1)
    assert score_incremental([base]) == score_incremental([otro])
    # Distinto severidad SÍ cambia el peso (control: el test no es una tautología).
    critico = EventoScore(tipo="copiar_pegar", severidad="critica", ts_ms=0, persistencia=1)
    assert score_incremental([critico]) > score_incremental([base])
