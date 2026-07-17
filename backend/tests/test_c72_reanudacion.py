"""C-72 sección 5 — Clasificación de la reanudación (dominio puro).

Corre SIN base de datos. La duración de ausencia (medida server-side) decide si
la reapertura es una recarga rápida o una reanudación tardía.
"""

from __future__ import annotations

from app.domain.events.reanudacion import clasificar_reanudacion
from app.domain.events.schema import TipoEvento


def test_ausencia_corta_es_recarga():
    # por debajo del umbral → recarga_pagina (recargó y volvió enseguida)
    assert clasificar_reanudacion(10, umbral_seg=30) == TipoEvento.RECARGA_PAGINA


def test_ausencia_larga_es_reanudacion_tardia():
    # por encima del umbral → reanudacion_tardia (estuvo ausente un rato)
    assert clasificar_reanudacion(120, umbral_seg=30) == TipoEvento.REANUDACION_TARDIA


def test_borde_en_el_umbral_es_tardia():
    # exactamente en el umbral → tardía (borde inclusivo hacia "tardía")
    assert clasificar_reanudacion(30, umbral_seg=30) == TipoEvento.REANUDACION_TARDIA
