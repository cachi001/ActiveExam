"""Value objects de la decision del revisor (c-16)."""

from __future__ import annotations

import enum
from dataclasses import dataclass


class DecisionTerminal(str, enum.Enum):
    """Decision terminal del revisor (RN-RV-07).

    Pendiente NO es terminal (es el estado inicial). Las 3 decisiones reales
    son descartada / escalada / derivada — cada una INMUTABLE una vez
    persistida.
    """

    PENDIENTE = "pendiente"  # estado pre-decision
    DESCARTADA = "descartada"  # revisor: nada relevante
    ESCALADA = "escalada"  # subir a coordinador (segunda opinion)
    DERIVADA = "derivada"  # iniciar proceso disciplinario formal


_TERMINALES = frozenset(
    {DecisionTerminal.DESCARTADA, DecisionTerminal.ESCALADA, DecisionTerminal.DERIVADA}
)


def es_terminal(d: DecisionTerminal) -> bool:
    return d in _TERMINALES


@dataclass(frozen=True)
class ReviewDecisionRecord:
    """Snapshot de la decision actualmente persistida en una sesion."""

    session_id: str
    decision: DecisionTerminal
    actor: str | None
    decision_at: str | None  # ISO 8601 o None
    observaciones: str | None


@dataclass(frozen=True)
class ReviewDecisionResult:
    """Resultado del comando ``decide_session``: estado anterior + nuevo."""

    session_id: str
    previous: DecisionTerminal
    new: DecisionTerminal
    actor: str
    decision_at: str
