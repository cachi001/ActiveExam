"""Regla pura del gate de write-back a Moodle por estado de revisión (c-71 D15,
modelo de un solo paso).

`writeback_en_hold(flaggeada, decision)`:
- anulado → hold permanente (nunca se envía);
- aprobado → release (revisión limpia, no hay segunda instancia que esperar);
- sin decisión (pendiente) → hold si flaggeada (en_cola_revision), release si no.
"""

from __future__ import annotations

from app.domain.review.decision import DecisionSesion, writeback_en_hold


def test_anulado_siempre_en_hold() -> None:
    assert (
        writeback_en_hold(flaggeada=True, decision=DecisionSesion.ANULADO) is True
    )
    assert (
        writeback_en_hold(flaggeada=False, decision=DecisionSesion.ANULADO) is True
    )


def test_aprobado_libera() -> None:
    assert (
        writeback_en_hold(flaggeada=True, decision=DecisionSesion.APROBADO) is False
    )


def test_sin_decision_hold_si_flaggeada_release_si_no() -> None:
    # Flaggeada (en_cola_revision) sin revisar aún → hold.
    assert (
        writeback_en_hold(flaggeada=True, decision=DecisionSesion.PENDIENTE) is True
    )
    # Nunca flaggeada (score bajo el umbral) → se envía.
    assert (
        writeback_en_hold(flaggeada=False, decision=DecisionSesion.PENDIENTE)
        is False
    )
