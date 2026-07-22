"""Etiquetas normalizadas para reportes/gráficos — nada de snake_case a la vista.

Fija el contrato de app/application/stats/labels.py: todo TipoEvento tiene etiqueta
legible, ninguna etiqueta lleva guion bajo, y un código desconocido se humaniza
(no se muestra crudo).
"""

from __future__ import annotations

from app.application.stats.labels import (
    ETIQUETA_EVENTO,
    etiqueta_decision,
    etiqueta_evento,
    humanizar,
)
from app.domain.events.schema import TipoEvento


def test_todos_los_tipos_de_evento_tienen_etiqueta():
    faltantes = [t.value for t in TipoEvento if t.value not in ETIQUETA_EVENTO]
    assert not faltantes, f"tipos de evento sin etiqueta: {faltantes}"


def test_ninguna_etiqueta_de_evento_es_snake_case():
    for etiqueta in ETIQUETA_EVENTO.values():
        assert "_" not in etiqueta, f"etiqueta con guion bajo: {etiqueta!r}"


def test_codigo_desconocido_se_humaniza_sin_guion_bajo():
    assert etiqueta_evento("codigo_raro_nuevo") == "Codigo raro nuevo"
    assert "_" not in etiqueta_evento("otro_codigo_desconocido")


def test_humanizar_vacio_no_rompe():
    assert humanizar("") == ""


def test_etiqueta_decision_conocida_y_desconocida():
    assert etiqueta_decision("caso_abierto") == "Caso abierto"
    assert "_" not in etiqueta_decision("estado_inventado")
