"""c-78 — Si el coordinador aprueba una sesión en riesgo, la nota SE PUEDE mandar.

Pedido del dueño (26/8/2026):

    "tambien si esta en riesgo y no deja subirle la nota, si el coordinador
     aprueba la nota, deberia dejarle sincronizar la nota"

Es el freno de integridad (D15) y su salida. El sistema **nunca sanciona solo**:
si una sesión quedó marcada por riesgo, la nota espera. Pero cuando una persona
la revisa y dice "falso positivo", el freno tiene que soltarse — si no, un error
de detección le arruina la nota a alguien para siempre.

Los tres estados que importan:

  - marcada y sin revisar → **retenida** (nadie decidió todavía)
  - marcada y APROBADA (falso positivo) → **se puede mandar**
  - ANULADA por fraude → retenida, y no la suelta nadie: esa nota no va

Contra DB REAL, sin mocks (regla dura de código).
"""

from __future__ import annotations

import pytest

from app.domain.review.decision import DecisionSesion, writeback_en_hold


def test_marcada_y_sin_revisar_queda_retenida():
    """El caso que motivó el gate: nadie decidió, la nota no sale sola."""
    assert writeback_en_hold(flaggeada=True, decision=DecisionSesion.PENDIENTE) is True


def test_el_coordinador_la_aprueba_y_la_nota_se_libera():
    """LA PREGUNTA DEL DUEÑO. Falso positivo revisado: la nota tiene que poder ir."""
    assert writeback_en_hold(flaggeada=True, decision=DecisionSesion.APROBADO) is False


def test_anulada_por_fraude_sigue_retenida():
    """Triangulación: aprobar libera, anular NO. Si anular también soltara la
    nota, el veredicto disciplinario no tendría efecto."""
    assert writeback_en_hold(flaggeada=True, decision=DecisionSesion.ANULADO) is True


def test_una_sesion_limpia_nunca_estuvo_retenida():
    assert writeback_en_hold(flaggeada=False, decision=DecisionSesion.PENDIENTE) is False


def test_aprobar_una_sesion_limpia_no_cambia_nada():
    assert writeback_en_hold(flaggeada=False, decision=DecisionSesion.APROBADO) is False


def test_anular_una_sesion_limpia_igual_retiene():
    """Se puede anular por algo que no vino de la detección automática (una
    denuncia, un acta). El veredicto humano manda sobre el flag."""
    assert writeback_en_hold(flaggeada=False, decision=DecisionSesion.ANULADO) is True


@pytest.mark.parametrize(
    "flaggeada, decision, esperado",
    [
        (True, DecisionSesion.PENDIENTE, True),
        (True, DecisionSesion.APROBADO, False),
        (True, DecisionSesion.ANULADO, True),
        (False, DecisionSesion.PENDIENTE, False),
        (False, DecisionSesion.APROBADO, False),
        (False, DecisionSesion.ANULADO, True),
    ],
)
def test_la_tabla_completa_de_decisiones(flaggeada, decision, esperado):
    """Las seis combinaciones, juntas, para que se lea la regla de un vistazo."""
    assert writeback_en_hold(flaggeada=flaggeada, decision=decision) is esperado
