"""Contrato del evento de telemetria versionado (PURO, RN-EV-04/05, C-10).

Define los TIPOS y SEVERIDADES del dominio (RN-EV-04), el mapeo tipo->severidad,
el contrato VERSIONADO con compatibilidad hacia atras (RN-EV-05) y la validacion
de campos obligatorios. Es el contrato que C-11..C-15 consumen.

PUREZA (D1): solo enums/dataclasses/aritmetica; sin framework. La entidad de
persistencia ``Evento`` (C-05) ya existe; este modulo agrega el CONTRATO de
ingesta (validacion de campos, version, severidad) sin reabrir la entidad.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# Version actual del esquema. Las versiones soportadas (compatibilidad hacia atras,
# RN-EV-05) se enumeran en ``SCHEMA_VERSIONS_SOPORTADAS``.
SCHEMA_VERSION_ACTUAL = 1
SCHEMA_VERSIONS_SOPORTADAS: frozenset[int] = frozenset({1})


class TipoEvento(str, Enum):
    """Tipos de evento del dominio (RN-EV-04)."""

    ROSTRO_AUSENTE = "rostro_ausente"
    MULTIPLES_ROSTROS = "multiples_rostros"
    MIRADA_DESVIADA = "mirada_desviada"
    POSTURA = "postura"
    CAMBIO_PESTANA = "cambio_pestana"
    MONITOR_ADICIONAL = "monitor_adicional"
    POSIBLE_CAMBIO_IDENTIDAD = "posible_cambio_identidad"
    EVIDENCIA_CORRUPTA = "evidencia_corrupta"
    TAMPERING_CAMARA_VIRTUAL = "tampering_camara_virtual"
    CORTE_CONECTIVIDAD = "corte_conectividad"
    HEARTBEAT = "heartbeat"
    # C-72 sección 5 (H-4): reapertura de la rendición, emitidos SERVER-SIDE en el
    # resume (el cliente no los puede suprimir). Peso conservador — no son fraude
    # por sí solos, solo señal para el revisor humano.
    RECARGA_PAGINA = "recarga_pagina"
    REANUDACION_TARDIA = "reanudacion_tardia"
    # C-76 bloque 5: screenshots del alumno durante una ventana de pausa APROBADA.
    # BASELINE a proposito (L2.5, regla dura #5): la captura es insumo de revision
    # humana, NUNCA suma sola al score. La ausencia de captura tampoco es un
    # veredicto — solo una señal (ver PAUSA_SIN_CAPTURA) para que el revisor la vea.
    CAPTURA_PAUSA = "captura_pausa"
    PAUSA_SIN_CAPTURA = "pausa_sin_captura"


class Severidad(str, Enum):
    """Severidades del dominio (RN-EV-04).

    Vocabulario CANONICO del proyecto, en femenino. Es la MISMA lista que fijan el
    CHECK de ``evento_score_config``, ``PESOS_SEVERIDAD`` (application/proctoring/
    scoring.py) y el catalogo del cliente. Cualquier tabla de pesos se indexa por
    estos valores — escribirlos a mano en masculino ("alto", "medio") produce un
    score 0 silencioso, que es como la cola de revision quedo vacia.

    ``BAJA`` existia en la DB, en la config y en el cliente, pero faltaba aca: el
    enum no describia el vocabulario real.
    """

    BASELINE = "baseline"
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"


# Mapeo tipo -> severidad tipica (RN-EV-04). Es la severidad por DEFECTO del tipo;
# la capa de reglas de transicion (C-11) puede afinarla, pero el contrato fija esta.
_SEVERIDAD_POR_TIPO: dict[TipoEvento, Severidad] = {
    TipoEvento.ROSTRO_AUSENTE: Severidad.MEDIA,
    TipoEvento.MULTIPLES_ROSTROS: Severidad.ALTA,
    TipoEvento.MIRADA_DESVIADA: Severidad.MEDIA,
    TipoEvento.POSTURA: Severidad.MEDIA,
    TipoEvento.CAMBIO_PESTANA: Severidad.MEDIA,
    TipoEvento.MONITOR_ADICIONAL: Severidad.ALTA,
    TipoEvento.POSIBLE_CAMBIO_IDENTIDAD: Severidad.CRITICA,
    TipoEvento.EVIDENCIA_CORRUPTA: Severidad.ALTA,
    TipoEvento.TAMPERING_CAMARA_VIRTUAL: Severidad.ALTA,
    TipoEvento.CORTE_CONECTIVIDAD: Severidad.CRITICA,
    TipoEvento.HEARTBEAT: Severidad.BASELINE,
    # Recarga = baja (baseline): recargar la página es común y benigno. Reanudación
    # tardía = media: una ausencia larga merece una mirada, sin ser fraude por sí sola.
    TipoEvento.RECARGA_PAGINA: Severidad.BASELINE,
    TipoEvento.REANUDACION_TARDIA: Severidad.MEDIA,
    # C-76 bloque 5: ninguno de los dos suma solo (L2.5) — ambos BASELINE.
    TipoEvento.CAPTURA_PAUSA: Severidad.BASELINE,
    TipoEvento.PAUSA_SIN_CAPTURA: Severidad.BASELINE,
}


def severidad_de(tipo: TipoEvento) -> Severidad:
    """Severidad tipica del tipo de evento (RN-EV-04)."""
    return _SEVERIDAD_POR_TIPO[tipo]


def es_anomalia(tipo: TipoEvento) -> bool:
    """``False`` para el heartbeat (prueba de vida, no anomalia); ``True`` resto."""
    return tipo != TipoEvento.HEARTBEAT


class EventoMalFormadoError(ValueError):
    """Evento al que le falta un campo obligatorio del esquema (RN-EV-05)."""


class VersionNoSoportadaError(ValueError):
    """``schema_version`` no reconocido: se rechaza explicitamente (RN-EV-05)."""


# Campos obligatorios que el cliente DEBE enviar (``ts_backend`` lo completa el
# backend al recibir; por eso NO esta en esta lista, RN-EV-05).
_CAMPOS_OBLIGATORIOS = (
    "id",
    "session_id",
    "exam_id",
    "tipo",
    "severidad",
    "ts_client",
    "firma",
    "schema_version",
)


@dataclass(frozen=True, slots=True)
class EventoEntrante:
    """Evento crudo reportado por el cliente (entrada potencialmente hostil).

    ``ts_backend`` lo completa el backend al recibir (no el cliente). ``firma`` es
    el HMAC-SHA256 con la clave de sesion; se valida ANTES de persistir (C-10 D2)."""

    id: str
    session_id: str
    exam_id: str
    tipo: TipoEvento
    severidad: Severidad
    ts_client: str
    payload: dict[str, object] = field(default_factory=dict)
    firma: str | None = None
    schema_version: int = SCHEMA_VERSION_ACTUAL


def validar_version(schema_version: int) -> None:
    """Acepta versiones soportadas (compat. hacia atras); rechaza lo desconocido."""
    if schema_version not in SCHEMA_VERSIONS_SOPORTADAS:
        raise VersionNoSoportadaError(
            f"schema_version {schema_version} no soportado "
            f"(soportadas: {sorted(SCHEMA_VERSIONS_SOPORTADAS)})"
        )


def validar_campos(datos: dict[str, object]) -> None:
    """Valida que esten TODOS los campos obligatorios (RN-EV-05).

    Levanta ``EventoMalFormadoError`` si falta alguno (p. ej. ``firma`` o
    ``schema_version``); el caso de uso lo traduce a rechazo sin persistir."""
    faltantes = [c for c in _CAMPOS_OBLIGATORIOS if c not in datos or datos[c] is None]
    if faltantes:
        raise EventoMalFormadoError(f"faltan campos obligatorios: {faltantes}")


def construir_entrante(datos: dict[str, object]) -> EventoEntrante:
    """Construye un ``EventoEntrante`` validado desde el dict crudo del cliente.

    Valida campos + version + enums. NO valida la firma (eso es ``signature``) ni
    persiste; solo materializa el contrato. Levanta ``EventoMalFormadoError`` /
    ``VersionNoSoportadaError`` ante datos invalidos."""
    validar_campos(datos)
    validar_version(int(datos["schema_version"]))  # type: ignore[arg-type]
    try:
        tipo = TipoEvento(datos["tipo"])
        severidad = Severidad(datos["severidad"])
    except ValueError as exc:
        raise EventoMalFormadoError(f"tipo/severidad invalido: {exc}") from exc
    return EventoEntrante(
        id=str(datos["id"]),
        session_id=str(datos["session_id"]),
        exam_id=str(datos["exam_id"]),
        tipo=tipo,
        severidad=severidad,
        ts_client=str(datos["ts_client"]),
        payload=dict(datos.get("payload", {})),  # type: ignore[arg-type]
        firma=str(datos["firma"]),
        schema_version=int(datos["schema_version"]),  # type: ignore[arg-type]
    )
