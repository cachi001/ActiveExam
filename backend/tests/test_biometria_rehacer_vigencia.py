"""Lógica de vigencia para el gate de re-captura biométrica (pedido del dueño).

`_referencia_sigue_vigente(fecha_captura)` decide si la referencia previa sigue
vigente (→ bloquear rehacer salvo override admin) o ya venció (→ permitir rehacer).
Puro, sin DB ni FastAPI.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.application.enrollment.guardar_embedding_referencia import (
    BIOMETRIC_VALIDITY_MONTHS,
    _referencia_sigue_vigente,
    _sumar_meses,
)


def test_referencia_recien_capturada_sigue_vigente() -> None:
    """Una captura de hoy sigue vigente → bloquea rehacer."""
    assert _referencia_sigue_vigente(datetime.now(timezone.utc)) is True


def test_referencia_vencida_no_sigue_vigente() -> None:
    """Una captura más vieja que la vigencia ya venció → permite rehacer."""
    vieja = _sumar_meses(datetime.now(timezone.utc), -(BIOMETRIC_VALIDITY_MONTHS + 1))
    assert _referencia_sigue_vigente(vieja) is False


def test_sin_fecha_captura_no_bloquea() -> None:
    """Sin fecha de captura no hay nada vigente que proteger."""
    assert _referencia_sigue_vigente(None) is False


def test_naive_datetime_se_asume_utc() -> None:
    """Un timestamp sin tz (naive) no debe romper: se asume UTC."""
    naive_reciente = datetime.now(timezone.utc).replace(tzinfo=None)
    assert _referencia_sigue_vigente(naive_reciente) is True


def test_sumar_meses_clamp_fin_de_mes() -> None:
    """Sumar meses respeta el fin de mes (31 ene + 1 mes → 28/29 feb)."""
    assert _sumar_meses(datetime(2026, 1, 31, tzinfo=timezone.utc), 1).date().isoformat() == "2026-02-28"


def test_justo_en_el_borde_de_vencimiento() -> None:
    """Una captura de exactamente la vigencia + 1 día atrás ya venció."""
    borde = _sumar_meses(datetime.now(timezone.utc), -BIOMETRIC_VALIDITY_MONTHS) - timedelta(days=1)
    assert _referencia_sigue_vigente(borde) is False
