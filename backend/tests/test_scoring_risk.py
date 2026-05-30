"""Tests del score de riesgo incremental (C-13, dominio PURO).

Cubre: ponderacion por severidad; persistencia (sostenido > pico aislado);
correlacion (coincidentes > suma de partes); decision de encolado por umbral
(flaggeada/archivada); y la garantia inviolable: ningun path emite veredicto/sancion
(solo prioridad ordinal + estado).
"""

from __future__ import annotations

from app.domain.scoring.risk_score import (
    DecisionEncolado,
    EventoScore,
    PesosScore,
    decidir_encolado,
    peso_evento,
    score_correlacionado,
    score_incremental,
)


def test_severidad_modula_el_peso() -> None:
    critica = peso_evento(EventoScore(tipo="multiples_rostros", severidad="critica", ts_ms=0))
    media = peso_evento(EventoScore(tipo="mirada", severidad="media", ts_ms=0))
    baseline = peso_evento(EventoScore(tipo="heartbeat", severidad="baseline", ts_ms=0))
    assert critica > media > baseline
    assert baseline == 0.0


def test_patron_sostenido_pesa_mas_que_pico_aislado() -> None:
    pico = EventoScore(tipo="mirada", severidad="alta", ts_ms=0, persistencia=1)
    sostenido = EventoScore(tipo="mirada", severidad="alta", ts_ms=0, persistencia=8)
    assert peso_evento(sostenido) > peso_evento(pico)


def test_frecuencia_acumula_score() -> None:
    uno = [EventoScore(tipo="mirada", severidad="media", ts_ms=0)]
    tres = [EventoScore(tipo="mirada", severidad="media", ts_ms=i * 100) for i in range(3)]
    assert score_incremental(tres) > score_incremental(uno)


def test_correlacion_supera_la_suma_de_partes() -> None:
    # Mirada desviada + perdida de foco simultaneas (distinto tipo, misma ventana).
    correlacionados = [
        EventoScore(tipo="mirada_desviada", severidad="media", ts_ms=0),
        EventoScore(tipo="perdida_de_foco", severidad="media", ts_ms=500),
    ]
    suma_simple = score_incremental(correlacionados)
    con_correlacion = score_correlacionado(correlacionados)
    assert con_correlacion > suma_simple


def test_eventos_fuera_de_ventana_no_correlacionan() -> None:
    # Mismos eventos pero separados mas alla de la ventana de correlacion: no hay bono.
    pesos = PesosScore(ventana_correlacion_ms=1000)
    separados = [
        EventoScore(tipo="mirada_desviada", severidad="media", ts_ms=0),
        EventoScore(tipo="perdida_de_foco", severidad="media", ts_ms=5000),
    ]
    assert score_correlacionado(separados, pesos) == score_incremental(separados, pesos)


def test_mismo_tipo_no_recibe_bono_de_correlacion() -> None:
    # Dos eventos del MISMO tipo coincidentes: frecuencia, no correlacion (no es
    # coincidencia de senales independientes).
    mismos = [
        EventoScore(tipo="mirada", severidad="media", ts_ms=0),
        EventoScore(tipo="mirada", severidad="media", ts_ms=200),
    ]
    assert score_correlacionado(mismos) == score_incremental(mismos)


def test_decision_por_umbral_flaggea_sobre_umbral() -> None:
    res = decidir_encolado(10.0, umbral=5.0)
    assert res.decision is DecisionEncolado.FLAGGEADA
    assert res.score_final == 10.0


def test_decision_por_umbral_archiva_bajo_umbral() -> None:
    res = decidir_encolado(2.0, umbral=5.0)
    assert res.decision is DecisionEncolado.ARCHIVADA


def test_umbral_es_configurable() -> None:
    # El mismo score decide distinto segun el umbral institucional (RN-SC-05).
    assert decidir_encolado(4.0, umbral=3.0).decision is DecisionEncolado.FLAGGEADA
    assert decidir_encolado(4.0, umbral=10.0).decision is DecisionEncolado.ARCHIVADA


def test_score_nunca_emite_veredicto_solo_prioridad() -> None:
    # La salida es prioridad ordinal (score_final) + estado (flaggeada/archivada).
    # NINGUN campo de sancion/veredicto/culpa/bloqueo (L2.5, RN-SC-01, RN-RV-07).
    res = decidir_encolado(100.0, umbral=1.0)
    campos = set(res.__slots__)
    assert campos == {"score_final", "decision"}
    assert not hasattr(res, "sancion")
    assert not hasattr(res, "veredicto")
    assert not hasattr(res, "culpa")
    # Las unicas decisiones posibles son encolar (prioridad) o archivar; jamas sancion.
    assert {d.value for d in DecisionEncolado} == {"flaggeada", "archivada"}
