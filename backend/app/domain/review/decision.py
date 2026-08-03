"""Value objects del modelo de decision de UN SOLO PASO (c-16, evolucionado
c-71 slice 2, colapsado por decision explicita del owner del proyecto).

El modelo de DOS FASES (c-71 slice 2: `DecisionRevision` + `DecisionResolucion`,
con `caso_abierto` como derivacion a una segunda instancia de resolucion) fue
RECHAZADO por el owner del proyecto: "no existe el caso abierto, nunca dije
que era un estado y no lo va a ser". Confirmado explicitamente: "si, un solo
paso: quien revisa decide", SIN segunda instancia de validacion.

Modelo vigente -- UN UNICO enum, UN SOLO ACTO (capacidad ``revisar_sesion``):

    PENDIENTE -- estado inicial, sin revisar todavia.
    APROBADO  -- las senales son falso positivo o no ameritan sancion. Colapsa
                 lo que en el modelo de dos fases eran dos nombres para lo
                 mismo (`sin_hallazgos` + `aprobado`, fase 1) y el cierre
                 limpio de la fase 2 (`caso_descartado`). Valida la nota.
    ANULADO   -- el revisor determino fraude EN ESE MISMO ACTO (sin segunda
                 instancia), con motivo y evidencia estructurada obligatorios
                 (ver `app.application.review.service`). Anula la nota.
                 Reemplaza `anulado_por_fraude` de la fase 2.

`caso_abierto` y `caso_descartado` DESAPARECEN del modelo. No quedan como
valor legado a mapear: no hay datos reales persistidos con el modelo viejo
(produccion en 0 filas al momento de este cambio), asi que no hace falta
compatibilidad hacia atras -- todo el codigo habla el modelo nuevo.

La RESTITUCION (acto compensatorio posterior a un `ANULADO`, D10b) sigue
existiendo tal cual: revierte el efecto sobre la nota sin reescribir el acto
original (append-only en el audit log), preservando la cadena de custodia.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class DecisionSesion(str, enum.Enum):
    """Decision terminal, en un solo paso, sobre una sesion flaggeada."""

    PENDIENTE = "pendiente"  # estado pre-decision
    APROBADO = "aprobado"  # senales revisadas: falso positivo o no amerita sancion; valida la nota
    ANULADO = "anulado"  # fraude determinado en el mismo acto; anula la nota


# Alias de compatibilidad: nombre historico (c-16) del enum de decision, y
# nombre usado durante c-71 slice 2 para la fase de revision. Se mantiene
# como alias transicional mientras el resto del codigo termina de migrar a
# `DecisionSesion`; NO introduce un significado nuevo.
DecisionTerminal = DecisionSesion
DecisionRevision = DecisionSesion

_TERMINALES = frozenset({DecisionSesion.APROBADO, DecisionSesion.ANULADO})


def es_terminal(d: DecisionSesion) -> bool:
    """``True`` si ``d`` es una decision terminal (ya se revisó, en un solo acto)."""
    return d in _TERMINALES


def valida_la_nota(d: DecisionSesion) -> bool:
    """``True`` si esta decision, por si sola, valida la nota."""
    return d is DecisionSesion.APROBADO


def writeback_en_hold(*, flaggeada: bool, decision: DecisionSesion) -> bool:
    """``True`` si el write-back de la nota a Moodle debe RETENERSE (D15).

    Regla (evaluada antes del envío, sobre el estado de revisión de la sesión):
    - `anulado` → hold permanente (nunca se envía);
    - `aprobado` → release (revisión limpia, no hay segunda instancia que esperar);
    - sin decisión aún (`pendiente`) → hold si la sesión está flaggeada
      (`en_cola_revision` = score ≥ umbral), release si nunca se flaggeó.
    """
    if decision is DecisionSesion.ANULADO:
        return True
    if decision is DecisionSesion.APROBADO:
        return False
    # Sin decisión (pendiente): el flag de priorización decide.
    return flaggeada


def nota_esta_anulada(decision: DecisionSesion, hubo_restitucion: bool) -> bool:
    """Estado efectivo de la nota DERIVADO del ultimo acto (D10b).

    La nota esta anulada si la decision fue `anulado` Y no hubo un acto
    compensatorio de restitucion posterior (`nota_restituida`). Nunca se lee
    el estado de un UPDATE: se deriva de los actos append-only."""
    return decision is DecisionSesion.ANULADO and not hubo_restitucion


@dataclass(frozen=True)
class ReviewDecisionRecord:
    """Snapshot de la decision actualmente persistida en una sesion."""

    session_id: str
    decision: DecisionSesion
    actor: str | None
    decision_at: str | None  # ISO 8601 o None
    motivo: str | None
    evidencia_ids: tuple[str, ...]


@dataclass(frozen=True)
class ReviewDecisionResult:
    """Resultado del comando ``decide_session``: estado anterior + nuevo."""

    session_id: str
    previous: DecisionSesion
    new: DecisionSesion
    actor: str
    decision_at: str
    nota_anulada: bool
