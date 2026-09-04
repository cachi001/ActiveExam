"""Contract test del esquema de evento versionado (C-10, RN-EV-05).

Snapshot del contrato que C-11..C-15 consumen: campos obligatorios, tipos del
dominio, severidades y version. Si el contrato cambia de forma incompatible, este
test lo detecta (rompe a los downstream). Logica pura, sin DB.
"""

from __future__ import annotations

from app.domain.events.schema import (
    SCHEMA_VERSION_ACTUAL,
    SCHEMA_VERSIONS_SOPORTADAS,
    Severidad,
    TipoEvento,
)

# Snapshot del contrato (orden de campos del mensaje canonico firmado, RN-EV-05).
from app.domain.events.signature import mensaje_canonico
from app.domain.events.schema import construir_entrante


def test_tipos_del_dominio_son_los_de_rn_ev_04() -> None:
    esperados = {
        "rostro_ausente",
        "multiples_rostros",
        "mirada_desviada",
        "postura",
        "cambio_pestana",
        "monitor_adicional",
        "posible_cambio_identidad",
        "evidencia_corrupta",
        "tampering_camara_virtual",
        "corte_conectividad",
        "heartbeat",
        # C-72 sección 5: reanudación de una rendición clasificada por la duración
        # de la ausencia (medida server-side).
        "recarga_pagina",
        "reanudacion_tardia",
        # C-76 bloque 5: screenshots durante una pausa APROBADA. Nacen BASELINE a
        # propósito (L2.5, regla dura #5): son insumo de la revisión humana y no
        # suman solos al score. La ausencia de captura tampoco es un veredicto.
        "captura_pausa",
        "pausa_sin_captura",
    }
    assert {t.value for t in TipoEvento} == esperados


def test_severidades_del_dominio() -> None:
    # `baja` ya existía en la DB (CHECK de evento_score_config), en la tabla de
    # pesos y en el catálogo del cliente; faltaba en el enum, así que el enum no
    # describía el vocabulario real. Está acá porque el contrato es esa lista, no
    # la que había cuando se escribió este test.
    assert {s.value for s in Severidad} == {"baseline", "baja", "media", "alta", "critica"}


def test_version_actual_esta_soportada() -> None:
    assert SCHEMA_VERSION_ACTUAL in SCHEMA_VERSIONS_SOPORTADAS


def test_mensaje_canonico_orden_estable() -> None:
    # El orden de campos del mensaje firmado es parte del CONTRATO con el cliente:
    # si cambia, cliente y backend dejan de coincidir. Snapshot del orden.
    ev = construir_entrante(
        {
            "id": "ID", "session_id": "SES", "exam_id": "EXA",
            "tipo": "heartbeat", "severidad": "baseline",
            "ts_client": "TS", "payload": {}, "firma": "x", "schema_version": 1,
        }
    )
    assert mensaje_canonico(ev).decode("utf-8") == "ID|SES|EXA|heartbeat|baseline|TS|1"
