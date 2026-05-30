"""Tests del contrato de evento versionado (C-10, logica pura, RN-EV-04/05)."""

from __future__ import annotations

import pytest

from app.domain.events.schema import (
    SCHEMA_VERSION_ACTUAL,
    EventoMalFormadoError,
    Severidad,
    TipoEvento,
    VersionNoSoportadaError,
    construir_entrante,
    es_anomalia,
    severidad_de,
    validar_version,
)


def _datos_validos(**over) -> dict:
    base = {
        "id": "evt-1",
        "session_id": "s1",
        "exam_id": "e1",
        "tipo": "multiples_rostros",
        "severidad": "alta",
        "ts_client": "2026-05-30T10:00:00Z",
        "payload": {"rostros": 2},
        "firma": "deadbeef",
        "schema_version": 1,
    }
    base.update(over)
    return base


def test_mapeo_tipo_severidad_rn_ev_04() -> None:
    assert severidad_de(TipoEvento.MULTIPLES_ROSTROS) == Severidad.ALTA
    assert severidad_de(TipoEvento.POSIBLE_CAMBIO_IDENTIDAD) == Severidad.CRITICA
    assert severidad_de(TipoEvento.ROSTRO_AUSENTE) == Severidad.MEDIA
    assert severidad_de(TipoEvento.HEARTBEAT) == Severidad.BASELINE


def test_heartbeat_no_es_anomalia() -> None:
    assert es_anomalia(TipoEvento.HEARTBEAT) is False
    assert es_anomalia(TipoEvento.MULTIPLES_ROSTROS) is True


def test_construye_evento_valido() -> None:
    ev = construir_entrante(_datos_validos())
    assert ev.tipo == TipoEvento.MULTIPLES_ROSTROS
    assert ev.severidad == Severidad.ALTA
    assert ev.schema_version == SCHEMA_VERSION_ACTUAL


def test_falta_campo_obligatorio_es_mal_formado() -> None:
    for campo in ("firma", "schema_version", "session_id", "id"):
        datos = _datos_validos()
        del datos[campo]
        with pytest.raises(EventoMalFormadoError):
            construir_entrante(datos)


def test_campo_obligatorio_none_es_mal_formado() -> None:
    with pytest.raises(EventoMalFormadoError):
        construir_entrante(_datos_validos(firma=None))


def test_version_soportada_se_acepta() -> None:
    validar_version(1)  # no lanza


def test_version_no_soportada_se_rechaza() -> None:
    with pytest.raises(VersionNoSoportadaError):
        validar_version(99)
    with pytest.raises(VersionNoSoportadaError):
        construir_entrante(_datos_validos(schema_version=99))


def test_tipo_o_severidad_invalido_es_mal_formado() -> None:
    with pytest.raises(EventoMalFormadoError):
        construir_entrante(_datos_validos(tipo="inexistente"))


def test_ts_backend_no_es_campo_del_cliente() -> None:
    # El cliente NO envia ts_backend; el evento se construye sin el (lo pone el
    # backend al recibir). No debe ser obligatorio en la entrada.
    datos = _datos_validos()
    assert "ts_backend" not in datos
    construir_entrante(datos)  # valido sin ts_backend
