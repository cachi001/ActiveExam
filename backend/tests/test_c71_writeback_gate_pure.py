"""Regla pura del gate de write-back a Moodle por estado de revisión (c-71 D15).

`writeback_en_hold(flaggeada, decision, resolucion)`:
- anulado_por_fraude → hold permanente (nunca se envía);
- caso_descartado → release (resuelta limpia);
- sin_hallazgos / aprobado → release (revisión limpia);
- caso_abierto → hold (hay algo que resolver);
- sin decisión → hold si flaggeada (en_cola_revision), release si no.
"""

from __future__ import annotations

from app.domain.review.decision import (
    DecisionResolucion,
    DecisionRevision,
    writeback_en_hold,
)


def test_anulado_por_fraude_siempre_en_hold() -> None:
    assert (
        writeback_en_hold(
            flaggeada=True,
            decision=DecisionRevision.CASO_ABIERTO,
            resolucion=DecisionResolucion.ANULADO_POR_FRAUDE,
        )
        is True
    )


def test_caso_descartado_libera() -> None:
    assert (
        writeback_en_hold(
            flaggeada=True,
            decision=DecisionRevision.CASO_ABIERTO,
            resolucion=DecisionResolucion.CASO_DESCARTADO,
        )
        is False
    )


def test_revision_limpia_libera() -> None:
    assert (
        writeback_en_hold(
            flaggeada=True, decision=DecisionRevision.SIN_HALLAZGOS, resolucion=None
        )
        is False
    )
    assert (
        writeback_en_hold(
            flaggeada=True, decision=DecisionRevision.APROBADO, resolucion=None
        )
        is False
    )


def test_caso_abierto_sin_resolver_en_hold() -> None:
    assert (
        writeback_en_hold(
            flaggeada=True, decision=DecisionRevision.CASO_ABIERTO, resolucion=None
        )
        is True
    )


def test_sin_decision_hold_si_flaggeada_release_si_no() -> None:
    # Flaggeada (en_cola_revision) sin revisar aún → hold.
    assert (
        writeback_en_hold(
            flaggeada=True, decision=DecisionRevision.PENDIENTE, resolucion=None
        )
        is True
    )
    # Nunca flaggeada (score bajo el umbral) → se envía.
    assert (
        writeback_en_hold(
            flaggeada=False, decision=DecisionRevision.PENDIENTE, resolucion=None
        )
        is False
    )
