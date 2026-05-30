"""Score de riesgo incremental (PURO, RN-SC-01..RN-SC-05, DD-01).

Materializa la ponderacion del score como dominio puro (stdlib):
- ``peso_evento``: combina SEVERIDAD x FRECUENCIA x PERSISTENCIA (RN-SC-02). Un
  patron sostenido pesa mas que un pico aislado (la persistencia distingue ruido de
  senal).
- ``score_correlacionado``: eventos de distinto tipo coincidentes en una ventana
  temporal contribuyen MAS que la suma de sus partes (RN-SC-03) — la coincidencia de
  senales independientes es mas sospechosa que cada una por separado.
- ``decidir_encolado``: si ``score_final > umbral`` -> FLAGGEADA (cola de revision);
  si no -> ARCHIVADA. NUNCA emite veredicto/sancion (RN-SC-01, RN-RV-07, RN-DSR-04):
  la unica salida es una PRIORIDAD ordinal + un estado, jamas una decision
  disciplinaria. La decision terminal es HUMANA (C-16).

PUREZA (D1): sin framework ni infra. El continuous aggregate de TimescaleDB (insumo
de datos) vive en la migracion; aqui esta el ALGORITMO de ponderacion, testeable sin
DB. Los pesos por severidad y el umbral son CONFIGURABLES (RN-SC-03/RN-SC-05).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum

# Peso base por severidad (RN-EV-04 x RN-SC-02). Conservadores: baseline/baja casi no
# suman; critica domina. Configurables por institucion (override en ``PesosScore``).
_PESO_SEVERIDAD_DEFAULT: dict[str, float] = {
    "baseline": 0.0,
    "baja": 0.5,
    "media": 1.0,
    "alta": 3.0,
    "critica": 6.0,
}

# Bono de persistencia por cada fotograma/minuto consecutivo sostenido (RN-SC-03).
_BONO_PERSISTENCIA_DEFAULT = 0.5
# Factor de correlacion: cuanto MAS que la suma aporta cada par coincidente (>1.0).
_FACTOR_CORRELACION_DEFAULT = 1.5


@dataclass(frozen=True, slots=True)
class PesosScore:
    """Configuracion de pesos del score (configurable por institucion, RN-SC-05)."""

    severidad: dict[str, float] = field(
        default_factory=lambda: dict(_PESO_SEVERIDAD_DEFAULT)
    )
    bono_persistencia: float = _BONO_PERSISTENCIA_DEFAULT
    factor_correlacion: float = _FACTOR_CORRELACION_DEFAULT
    # Ventana de correlacion en milisegundos: eventos de distinto tipo dentro de esta
    # ventana se consideran coincidentes (RN-SC-03).
    ventana_correlacion_ms: int = 2000


@dataclass(frozen=True, slots=True)
class EventoScore:
    """Vista minima de un evento para el score (proyeccion de la hypertable)."""

    tipo: str
    severidad: str
    ts_ms: int
    # Fotogramas/intervalos consecutivos que sostuvo el patron (1 = pico aislado).
    persistencia: int = 1


def peso_evento(ev: EventoScore, pesos: PesosScore = PesosScore()) -> float:
    """Peso de un evento: severidad x (1 + bono por persistencia sostenida).

    Un pico aislado (persistencia=1) pesa su severidad base; un patron sostenido
    (persistencia>1) pesa mas, escalado por el bono (RN-SC-02/RN-SC-03)."""
    base = pesos.severidad.get(ev.severidad, 0.0)
    sostenido = 1.0 + pesos.bono_persistencia * max(0, ev.persistencia - 1)
    return base * sostenido


def score_incremental(
    eventos: Sequence[EventoScore], pesos: PesosScore = PesosScore()
) -> float:
    """Suma ponderada SIN correlacion (frecuencia: mas eventos -> mas score).

    Es el score base por acumulacion; la correlacion se agrega en
    ``score_correlacionado``. La FRECUENCIA entra naturalmente: cada evento suma su
    peso, de modo que mas eventos del mismo tipo elevan el score."""
    return sum(peso_evento(ev, pesos) for ev in eventos)


def score_correlacionado(
    eventos: Sequence[EventoScore], pesos: PesosScore = PesosScore()
) -> float:
    """Score con correlacion: eventos de DISTINTO tipo coincidentes en la ventana
    temporal aportan un bono ADICIONAL, de modo que el total supera la suma simple
    (RN-SC-03). El bono se aplica una vez por par de tipos distintos coincidentes."""
    base = score_incremental(eventos, pesos)
    bono = 0.0
    ordenados = sorted(eventos, key=lambda e: e.ts_ms)
    n = len(ordenados)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = ordenados[i], ordenados[j]
            if b.ts_ms - a.ts_ms > pesos.ventana_correlacion_ms:
                break  # fuera de ventana; los siguientes estan aun mas lejos
            if a.tipo != b.tipo:
                # Coincidencia de senales independientes: bono sobre el menor de los
                # pesos (la coincidencia agrega informacion, no duplica el evento).
                par = min(peso_evento(a, pesos), peso_evento(b, pesos))
                bono += par * (pesos.factor_correlacion - 1.0)
    return base + bono


class DecisionEncolado(str, Enum):
    """Resultado de la decision por umbral. NUNCA es un veredicto (RN-SC-01)."""

    FLAGGEADA = "flaggeada"  # prioridad para revision humana (cola C-16)
    ARCHIVADA = "archivada"  # bajo umbral: no entra a la cola


@dataclass(frozen=True, slots=True)
class ResultadoScore:
    """Salida del score: PRIORIDAD ordinal + decision de encolado. SIN veredicto.

    ``decision`` es flaggeada/archivada (estado de sesion), NUNCA una sancion. El
    score es un numero ordinal para ordenar la cola, no una culpa (D4, RN-SC-01)."""

    score_final: float
    decision: DecisionEncolado


def decidir_encolado(score_final: float, *, umbral: float) -> ResultadoScore:
    """Decide el encolado por umbral institucional configurable (RN-SC-04, D6).

    ``score_final > umbral`` -> FLAGGEADA (cola de revision); en caso contrario ->
    ARCHIVADA. Esta funcion NO sanciona: produce solo una prioridad y un estado; la
    decision disciplinaria es exclusivamente humana (L2.5, RN-RV-07)."""
    decision = (
        DecisionEncolado.FLAGGEADA
        if score_final > umbral
        else DecisionEncolado.ARCHIVADA
    )
    return ResultadoScore(score_final=score_final, decision=decision)
