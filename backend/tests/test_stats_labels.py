"""Etiquetas normalizadas para reportes/gráficos — nada de snake_case a la vista.

Fija el contrato de app/application/stats/labels.py: todo TipoEvento tiene etiqueta
legible, ninguna etiqueta lleva guion bajo, y un código desconocido se humaniza
(no se muestra crudo).
"""

from __future__ import annotations

from app.application.stats.labels import (
    ETIQUETA_EVENTO,
    ETIQUETA_ESTADO_MOODLE,
    etiqueta_decision,
    etiqueta_estado_moodle,
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
    assert etiqueta_decision("anulado") == "Anulado por fraude"
    assert "_" not in etiqueta_decision("estado_inventado")


def test_etiqueta_estado_moodle_pendiente():
    # El NOMBRE del estado, no una frase: el porqué va aparte, como motivo. Una
    # columna de estado que dice "Falta conectar el campus" no dice en qué estado
    # está la entrega, dice por qué no avanzó.
    assert etiqueta_estado_moodle("pendiente") == "Pendiente"


def test_etiqueta_estado_moodle_enviado():
    assert etiqueta_estado_moodle("enviado") == "Enviado"


def test_sin_token_no_habla_en_jerga():
    # "Sin token" es el nombre de la variable. Al docente hay que decirle qué le
    # falta hacer.
    assert etiqueta_estado_moodle("sin_token") == "Falta conectar el campus"


def test_etiqueta_estado_moodle_desconocido_se_devuelve_tal_cual():
    assert etiqueta_estado_moodle("estado_raro") == "estado_raro"


def test_todos_los_estados_moodle_cubiertos():
    # Se DERIVA del enum real (WritebackEstado + los alias de display 'sin_token' y
    # 'manual'). Antes esta lista estaba escrita a mano acá, así que el test pasaba
    # justamente por no haberse enterado de que c-78 D14 agregó 'manual': congelaba
    # el conjunto viejo en vez de comparar contra la fuente.
    # La cobertura completa vive en tests/test_estados_moodle_fuente_unica.py.
    from app.application.moodle.resultados_query import ESTADO_MANUAL, ESTADO_SIN_TOKEN
    from app.application.moodle.writeback_service import WritebackEstado

    esperados = {e.value for e in WritebackEstado} | {ESTADO_SIN_TOKEN, ESTADO_MANUAL}
    assert set(ETIQUETA_ESTADO_MOODLE) == esperados
