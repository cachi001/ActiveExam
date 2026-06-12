"""Value objects que describen el resultado de una corrida del motor.

``RetentionDeletion`` es una fila del reporte: "se borro X de tipo Y por razon Z
en el momento T". ``RetentionRunReport`` agrega las filas + las sesiones cuyo
borrado se difirio por hold, junto con la politica aplicada.

Ambos son frozen dataclasses — son value objects de salida, no entidades.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.retention.policy import RetentionPolicy


@dataclass(frozen=True)
class RetentionDeletion:
    """Una entrada del reporte: que se borro, de que tipo, por que razon."""

    target_id: str
    target_kind: str  # "session" | "embedding_referencia" | "foto_referencia"
    reason: str  # "age_exceeded" | "user_egress"
    at: datetime


@dataclass(frozen=True)
class RetentionRunReport:
    """Resultado de una corrida del motor de retencion."""

    policy_applied: RetentionPolicy
    deletions: list[RetentionDeletion] = field(default_factory=list)
    holds_deferred: list[str] = field(default_factory=list)
    run_at: datetime = field(default_factory=lambda: datetime.now())

    @property
    def total_deletions(self) -> int:
        return len(self.deletions)

    @property
    def total_holds_deferred(self) -> int:
        return len(self.holds_deferred)

    def count_by_kind(self, kind: str) -> int:
        """Cuenta borrados por tipo (session / embedding_referencia / foto_referencia)."""
        return sum(1 for d in self.deletions if d.target_kind == kind)
