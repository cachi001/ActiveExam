"""Value objects del modelo de decision de dos fases (c-16, evolucionado c-71
slice 2 D6/D7).

Fase 1 -- REVISION (capacidad ``revisar_sesion``): el revisor examina la
sesion flaggeada y emite una de las decisiones de ``DecisionRevision``.
``CASO_ABIERTO`` es terminal DE LA REVISION (no se puede volver a revisar),
pero NO valida ni anula la nota todavia: solo abre el caso para la fase 2.

Fase 2 -- RESOLUCION (capacidad ``resolver_caso``): solo aplicable si la
revision quedo en ``CASO_ABIERTO``. Emite una ``DecisionResolucion`` --
el veredicto real sobre la nota.

Mapeo desde el enum viejo (`descartada|escalada|derivada`, c-16 slim):

| Valor viejo  | Valor nuevo    | Nota                                  |
|--------------|----------------|----------------------------------------|
| ``pendiente``| ``pendiente``  | estado inicial, sin cambio             |
| ``descartada``| ``sin_hallazgos``| falso positivo, valida la nota      |
| ``derivada`` | ``caso_abierto``| derivo, sin resolver aun              |
| ``escalada`` | ``caso_abierto``| DROPEADO como valor propio (D6)       |

``escalada`` se elimina del modelo: no tenia consumidor aguas abajo. La
separacion de capacidad (D8) cubre "escalar a otra autoridad": el caso
``caso_abierto`` lo resuelve quien tenga ``resolver_caso``, sea el mismo
revisor u otra autoridad.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class DecisionRevision(str, enum.Enum):
    """Decision de la fase 1 (revision), c-71 slice 2 D6."""

    PENDIENTE = "pendiente"  # estado pre-decision
    SIN_HALLAZGOS = "sin_hallazgos"  # falso positivo; valida la nota
    APROBADO = "aprobado"  # senales revisadas y legitimas; valida la nota
    CASO_ABIERTO = "caso_abierto"  # derivacion: queda abierto para fase 2

    @classmethod
    def desde_valor_legado(cls, valor: str) -> "DecisionRevision":
        """Traduce un valor persistido con el enum viejo (c-16 slim) al nuevo.

        Usado por la migracion de datos y como fallback defensivo en lectura;
        NO es la via normal de escritura (D6)."""
        mapeo_legado = {
            "pendiente": cls.PENDIENTE,
            "descartada": cls.SIN_HALLAZGOS,
            "derivada": cls.CASO_ABIERTO,
            "escalada": cls.CASO_ABIERTO,
        }
        try:
            return mapeo_legado[valor]
        except KeyError as exc:
            raise ValueError(f"Valor legado desconocido: {valor!r}") from exc


class DecisionResolucion(str, enum.Enum):
    """Veredicto de la fase 2 (resolucion), solo valido sobre `caso_abierto`."""

    ANULADO_POR_FRAUDE = "anulado_por_fraude"  # anula la nota
    CASO_DESCARTADO = "caso_descartado"  # cierra el caso, valida la nota


# Alias de compatibilidad: el nombre historico del modulo (c-16) referenciaba
# `DecisionTerminal` para la fase de revision. Se mantiene como alias para no
# romper imports existentes fuera de este modulo mientras se migra el resto
# del codigo (router/servicio) a los nombres nuevos.
DecisionTerminal = DecisionRevision

_TERMINALES_REVISION = frozenset(
    {DecisionRevision.SIN_HALLAZGOS, DecisionRevision.APROBADO, DecisionRevision.CASO_ABIERTO}
)


def es_terminal(d: DecisionRevision) -> bool:
    """``True`` si ``d`` es una decision terminal de la fase de REVISION."""
    return d in _TERMINALES_REVISION


def es_caso_abierto(d: DecisionRevision) -> bool:
    """``True`` si la revision derivo el caso (precondicion de la fase 2)."""
    return d is DecisionRevision.CASO_ABIERTO


def valida_la_nota(d: DecisionRevision) -> bool:
    """``True`` si esta decision de revision, por si sola, valida la nota."""
    return d in (DecisionRevision.SIN_HALLAZGOS, DecisionRevision.APROBADO)


def resolucion_valida_la_nota(r: DecisionResolucion) -> bool:
    """``True`` si la resolucion valida la nota (en vez de anularla)."""
    return r is DecisionResolucion.CASO_DESCARTADO


def writeback_en_hold(
    *,
    flaggeada: bool,
    decision: DecisionRevision,
    resolucion: DecisionResolucion | None,
) -> bool:
    """``True`` si el write-back de la nota a Moodle debe RETENERSE (D15).

    Regla (evaluada antes del envío, sobre el estado de revisión de la sesión):
    - `anulado_por_fraude` → hold permanente (nunca se envía);
    - `caso_descartado` → release (resuelta limpia);
    - `sin_hallazgos` / `aprobado` → release (revisión limpia);
    - `caso_abierto` (sin resolver) → hold (hay algo que resolver);
    - sin decisión terminal aún → hold si la sesión está flaggeada
      (`en_cola_revision` = score ≥ umbral), release si nunca se flaggeó.
    """
    if resolucion is DecisionResolucion.ANULADO_POR_FRAUDE:
        return True
    if resolucion is DecisionResolucion.CASO_DESCARTADO:
        return False
    if decision in (DecisionRevision.SIN_HALLAZGOS, DecisionRevision.APROBADO):
        return False
    if decision is DecisionRevision.CASO_ABIERTO:
        return True
    # Sin decisión terminal (pendiente): el flag de priorización decide.
    return flaggeada


def nota_esta_anulada(
    resolucion: DecisionResolucion | None, hubo_restitucion: bool
) -> bool:
    """Estado efectivo de la nota DERIVADO del ultimo acto (D10b).

    La nota esta anulada si la resolucion fue `anulado_por_fraude` Y no hubo un
    acto compensatorio de restitucion posterior (`nota_restituida`). Nunca se
    lee el estado de un UPDATE: se deriva de los actos append-only."""
    return (
        resolucion is DecisionResolucion.ANULADO_POR_FRAUDE and not hubo_restitucion
    )


@dataclass(frozen=True)
class ReviewDecisionRecord:
    """Snapshot de la decision de REVISION actualmente persistida en una sesion."""

    session_id: str
    decision: DecisionRevision
    actor: str | None
    decision_at: str | None  # ISO 8601 o None
    observaciones: str | None


@dataclass(frozen=True)
class ReviewDecisionResult:
    """Resultado del comando ``decide_session``: estado anterior + nuevo."""

    session_id: str
    previous: DecisionRevision
    new: DecisionRevision
    actor: str
    decision_at: str


@dataclass(frozen=True)
class ResolutionRecord:
    """Snapshot de la fase 2 (resolucion) persistida sobre una sesion.

    ``decision`` refleja la fase 1 (para validar la precondicion `caso_abierto`);
    ``resolucion`` es None mientras el caso no se resuelva."""

    session_id: str
    decision: DecisionRevision
    resolucion: DecisionResolucion | None
    actor: str | None
    resolucion_at: str | None  # ISO 8601 o None
    motivo: str | None


@dataclass(frozen=True)
class ResolutionResult:
    """Resultado del comando ``resolve_session``."""

    session_id: str
    resolucion: DecisionResolucion
    actor: str
    resolucion_at: str
    nota_anulada: bool
