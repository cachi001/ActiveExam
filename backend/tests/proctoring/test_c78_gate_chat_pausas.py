"""Los interruptores de chat y pausas TIENEN que valer server-side (c-78).

## El bug

`chat_habilitado` y `pausas_habilitadas` eran **solo visuales**: `Examen.tsx`
escondia el recuadro, y los 7 endpoints de `chat_pausa/router.py` no consultaban
la config en ningun lado (verificado con grep: cero referencias). O sea que
apagarlos NO apagaba nada — cualquier cliente seguia escribiendo y polleando.

Rompia la regla dura #6 (el cliente no es confiable: la regla la hace valer el
backend) y hacia que la decision de capacidad "chat apagado por defecto" no
tuviera efecto real sobre la carga.

## De donde sale el valor: del SNAPSHOT, no de la config viva

Decision del dueño: la config del sistema NO se refresca a mitad del examen —
para eso existe `proctoring_session.config_snapshot`. Si el gate leyera la config
VIVA, un cambio a mitad del examen alteraria una rendicion en curso, que es
exactamente lo que el snapshot existe para impedir.

Entonces el snapshot pasa a congelar tambien los dos interruptores, y el gate lee
de ahi. Una sesion vieja sin esos campos en su foto cae a la config viva
(degradacion, igual que el resto de los lectores del snapshot).
"""

from __future__ import annotations

import pytest

from app.application.proctoring.scoring import (
    chat_habilitado_de_snapshot,
    construir_config_snapshot,
    pausas_habilitadas_de_snapshot,
)


def _snapshot(**kwargs):
    base = dict(
        umbral_cola_revision=70,
        pesos_por_tipo={},
        tipos_desactivados=frozenset(),
        chat_habilitado=False,
        pausas_habilitadas=True,
    )
    base.update(kwargs)
    return construir_config_snapshot(**base)


def test_el_snapshot_congela_los_dos_interruptores() -> None:
    """Sin esto el gate no tendria de donde leer sin romper la regla del snapshot."""
    foto = _snapshot(chat_habilitado=True, pausas_habilitadas=False)
    assert foto["chat_habilitado"] is True
    assert foto["pausas_habilitadas"] is False


def test_el_snapshot_sigue_congelando_lo_de_scoring() -> None:
    """No se rompe lo que ya congelaba (umbral y pesos): es la misma foto."""
    foto = _snapshot(umbral_cola_revision=55, pesos_por_tipo={"cambio_pestana": 9})
    assert foto["umbral_cola_revision"] == 55
    assert foto["scoring_weights"] == {"cambio_pestana": 9}


def test_manda_el_snapshot_por_encima_de_la_config_viva() -> None:
    """El punto del snapshot: un cambio de config a mitad del examen NO altera una
    rendicion en curso. El gate tiene que respetar eso igual que el scoring."""
    foto = _snapshot(chat_habilitado=False)
    # La config viva dice que SI, pero la sesion arranco con el chat apagado.
    assert chat_habilitado_de_snapshot(foto, vivo=True) is False

    foto = _snapshot(pausas_habilitadas=False)
    assert pausas_habilitadas_de_snapshot(foto, vivo=True) is False


def test_una_sesion_vieja_sin_esos_campos_cae_a_la_config_viva() -> None:
    """Sesiones creadas antes de este change: su foto no tiene los interruptores.
    Igual que el resto de los lectores del snapshot, degradan a la config viva en
    vez de inventar un default."""
    foto_vieja = {"umbral_cola_revision": 70, "scoring_weights": {}}
    assert chat_habilitado_de_snapshot(foto_vieja, vivo=True) is True
    assert chat_habilitado_de_snapshot(foto_vieja, vivo=False) is False
    assert pausas_habilitadas_de_snapshot(foto_vieja, vivo=True) is True


def test_sin_snapshot_cae_a_la_config_viva() -> None:
    """`config_snapshot` NULL (sesion pre-migracion 0083)."""
    assert chat_habilitado_de_snapshot(None, vivo=True) is True
    assert chat_habilitado_de_snapshot(None, vivo=False) is False
    assert pausas_habilitadas_de_snapshot(None, vivo=False) is False


def test_los_dos_lectores_no_se_confunden_entre_si() -> None:
    """Un interruptor no puede leer el estado del otro."""
    foto = _snapshot(chat_habilitado=False, pausas_habilitadas=True)
    assert chat_habilitado_de_snapshot(foto, vivo=True) is False
    assert pausas_habilitadas_de_snapshot(foto, vivo=False) is True


def test_el_chat_y_las_pausas_vienen_PRENDIDOS_por_defecto() -> None:
    """Migracion 0098 (revierte la 0095): el sistema viene con la funcionalidad
    completa y el techo de capacidad lo decide la prueba de carga, no un
    supuesto. El dataclass tiene que coincidir con la base: cuando no coinciden,
    el que gana es el que llega ultimo y el comportamiento depende de si el dato
    viajo o no."""
    from app.application.config.service import ConfigEfectiva

    campos = ConfigEfectiva.__dataclass_fields__
    assert campos["chat_habilitado"].default is True
    assert campos["pausas_habilitadas"].default is True
