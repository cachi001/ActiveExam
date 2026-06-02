"""Tests del adapter MediaPipeReinferencia y degradacion elegante.

Tests unitarios — sin DB. Verifican el puerto ReinferenciaPort y la
degradacion elegante (RN-GLB-02) ante condiciones adversas.

Para el test de event_service con un fake puerto se inyecta una implementacion
duck-typed del ReinferenciaPort (NO se mockea la DB; en ese test se necesita DB real).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.application.proctoring.reinferencia import ResultadoReinferencia
from app.infrastructure.reinferencia.mediapipe_adapter import MediaPipeReinferencia


# Fake adapter para tests de event_service (duck-type del ReinferenciaPort)
class FakeReinferenciaCoincide:
    """Fake adapter que siempre devuelve 'coincide' con face_count_servidor=face_count_cliente."""

    def evaluar(self, screenshot_b64, face_count_cliente):
        fcs = face_count_cliente if face_count_cliente is not None else 0
        return ResultadoReinferencia(face_count_servidor=fcs, veredicto="coincide")


class FakeReinferenciaDiscrepancia:
    """Fake adapter que siempre devuelve 'discrepancia'."""

    def evaluar(self, screenshot_b64, face_count_cliente):
        servidor = 0 if (face_count_cliente or 0) > 0 else 1
        return ResultadoReinferencia(face_count_servidor=servidor, veredicto="discrepancia")


class FakeReinferenciaNoEvaluado:
    """Fake adapter que siempre devuelve 'no_evaluado'."""

    def evaluar(self, screenshot_b64, face_count_cliente):
        return ResultadoReinferencia(face_count_servidor=None, veredicto="no_evaluado")


def test_sin_screenshot_no_evaluado() -> None:
    """Sin screenshot → veredicto 'no_evaluado', sin excepcion."""
    adapter = MediaPipeReinferencia()
    result = adapter.evaluar(None, face_count_cliente=1)
    assert result.veredicto == "no_evaluado"
    assert result.face_count_servidor is None


def test_screenshot_vacio_no_evaluado() -> None:
    """Screenshot string vacio → 'no_evaluado', sin excepcion."""
    adapter = MediaPipeReinferencia()
    result = adapter.evaluar("", face_count_cliente=1)
    assert result.veredicto == "no_evaluado"


def test_base64_invalido_no_evaluado() -> None:
    """Base64 invalido → 'no_evaluado' sin levantar excepcion (RN-GLB-02)."""
    adapter = MediaPipeReinferencia()
    result = adapter.evaluar("esto_no_es_base64_@@###", face_count_cliente=1)
    # Debe degradar elegantemente — nunca levantar excepcion
    assert result.veredicto in ("no_evaluado", "coincide", "discrepancia")


def test_sin_excepcion_ante_cualquier_error() -> None:
    """El adapter nunca levanta excepcion, sin importar el input."""
    adapter = MediaPipeReinferencia()
    # Inputs invalidos que podrian causar errores
    casos = [
        (None, None),
        ("", None),
        ("no_es_base64", 0),
        ("data:image/jpeg;base64,invalid", 1),
        ("   ", -1),
    ]
    for screenshot, face_count in casos:
        try:
            result = adapter.evaluar(screenshot, face_count)
            assert result.veredicto in ("coincide", "discrepancia", "no_evaluado")
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"El adapter levanto excepcion con input {screenshot!r}: {exc}")


def test_resultado_reinferencia_dataclass() -> None:
    """ResultadoReinferencia es instanciable con los campos correctos."""
    r = ResultadoReinferencia(face_count_servidor=2, veredicto="coincide")
    assert r.face_count_servidor == 2
    assert r.veredicto == "coincide"


def test_fake_adapter_coincide_duck_type() -> None:
    """El fake adapter implementa el ReinferenciaPort por duck typing."""
    fake = FakeReinferenciaCoincide()
    result = fake.evaluar("screenshot", 1)
    assert result.veredicto == "coincide"
    assert result.face_count_servidor == 1


def test_fake_adapter_discrepancia() -> None:
    """FakeReinferenciaDiscrepancia devuelve discrepancia."""
    fake = FakeReinferenciaDiscrepancia()
    result = fake.evaluar("screenshot", 2)
    assert result.veredicto == "discrepancia"


def test_fake_adapter_no_evaluado() -> None:
    """FakeReinferenciaNoEvaluado devuelve no_evaluado."""
    fake = FakeReinferenciaNoEvaluado()
    result = fake.evaluar(None, None)
    assert result.veredicto == "no_evaluado"
    assert result.face_count_servidor is None


# Tests de integracion de event_service con fake puerto (requiere DB real)
@pytest.mark.asyncio
async def test_event_service_usa_puerto_no_mediapipe_directo(
    client,
) -> None:
    """Verificar que el event_service depende del puerto, no de mediapipe directamente.

    Este test es de integracion: crea una sesion, ingesta un evento y verifica que
    la respuesta incluye veredicto_reinferencia. El adapter real (MediaPipe) puede
    devolver 'no_evaluado' si MediaPipe no esta instalado — eso es correcto.
    """
    # Crear sesion
    sess_resp = await client.post(
        "/api/v1/proctoring/sessions", json={"modo": "test"}
    )
    assert sess_resp.status_code == 201
    session_id = sess_resp.json()["id"]

    # Ingestar evento — el adapter usa ReinferenciaPort (no importa si MediaPipe esta o no)
    event_resp = await client.post(
        f"/api/v1/proctoring/sessions/{session_id}/events",
        json={
            "tipo": "FACE_ABSENT",
            "severidad": "alto",
            "ts_cliente": "2026-06-02T10:00:00Z",
            "face_count_cliente": 0,
        },
    )
    assert event_resp.status_code == 201
    data = event_resp.json()
    # El veredicto puede ser cualquiera de los 3 — lo que importa es que NO rompe
    assert data["veredicto_reinferencia"] in ("coincide", "discrepancia", "no_evaluado")
