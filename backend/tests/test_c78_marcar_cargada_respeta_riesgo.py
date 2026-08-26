"""Una nota RETENIDA no se puede marcar como cargada a mano (c-78).

## El hueco

`PATCH /{examen_id}/resultados/{session_id}/marcar-cargada` existe para el campus
sin API: la nota se carga a mano y alguien afirma que ya la cargó, para que la fila
deje de decir "pendiente" para siempre.

Pero no miraba la RETENCIÓN. El sincronizado automático sí la respeta —
`_motivos_retencion` marca `en_riesgo` (superó el umbral y nadie la revisó) y
`anulada` (anulada por fraude), y apretar "Sincronizar" no las manda—, así que se
podía marcar a mano exactamente lo que el sistema se niega a mandar solo.

Eso rompe la regla dura #5 por la puerta de atrás: el sistema retiene la nota
esperando una decisión humana sobre la integridad, y esta acción la daba por
entregada sin que esa decisión existiera. Peor todavía: deja registrado que una
persona afirmó haberla cargado en el campus, o sea que la nota de alguien bajo
sospecha ya está puesta.

## La regla

Se reusa el motivo que YA calcula `_motivos_retencion` en vez de inventar otro
criterio — que es como se desincronizan las reglas. Si hay motivo, 409 y se dice
cuál. Cuando el revisor decide, la retención desaparece sola y la acción se
habilita.

Ojo con lo que NO bloquea: `sin_destino` y `sin_credencial_docente` retienen el
envío AUTOMÁTICO por falta de camino al campus, y son justamente los casos en que
cargar a mano es lo correcto. Bloquear esos seria romper la funcionalidad.
"""

from __future__ import annotations

import pytest

from app.application.moodle.marcado_manual import (
    MOTIVOS_QUE_BLOQUEAN_MARCADO,
    puede_marcarse_cargada,
)


def test_una_nota_sin_retencion_se_puede_marcar() -> None:
    assert puede_marcarse_cargada(None) is True


def test_EN_RIESGO_no_se_puede_marcar() -> None:
    """Superó el umbral y nadie la revisó: la decisión humana todavía no existe."""
    assert puede_marcarse_cargada("en_riesgo") is False


def test_ANULADA_no_se_puede_marcar() -> None:
    """Anulada por fraude: afirmar que se cargó es afirmar lo contrario del acto."""
    assert puede_marcarse_cargada("anulada") is False


def test_SIN_DESTINO_si_se_puede_marcar() -> None:
    """El examen no tiene curso/actividad en el campus. Es EXACTAMENTE el caso que
    la carga a mano viene a resolver: bloquearlo rompería la funcionalidad."""
    assert puede_marcarse_cargada("sin_destino") is True


def test_SIN_CREDENCIAL_si_se_puede_marcar() -> None:
    """Idem: no hay camino automático al campus, por eso se carga a mano."""
    assert puede_marcarse_cargada("sin_credencial_docente") is True


def test_un_motivo_nuevo_NO_bloquea_por_defecto() -> None:
    """Se listan los que bloquean, no los que dejan pasar.

    Un motivo nuevo suele ser "no hay camino al campus" (como los dos de arriba),
    y en ese caso cargar a mano es la salida. Bloquear por defecto rompería la
    funcionalidad en silencio; los dos que bloquean son sobre la INTEGRIDAD y se
    nombran de forma explícita.
    """
    assert puede_marcarse_cargada("un_motivo_que_no_existe_todavia") is True


def test_los_motivos_que_bloquean_son_los_de_integridad() -> None:
    assert MOTIVOS_QUE_BLOQUEAN_MARCADO == frozenset({"en_riesgo", "anulada"})
