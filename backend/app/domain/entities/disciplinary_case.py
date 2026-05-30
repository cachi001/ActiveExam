"""Entidad de dominio Caso disciplinario (PURA).

Caso derivado de una sesion flaggeada (`04` Caso disciplinario). Mientras esta
abierto, EXTIENDE la retencion (hold): difiere la eliminacion de evidencia y
embedding (regla dura de dominio #7). La decision disciplinaria es SIEMPRE humana
(L2.5). Sin SQLAlchemy (dominio puro / D1).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CasoDisciplinario:
    """Caso disciplinario con hold de retencion (`04`)."""

    session_id: str
    estado: str
    refs_evidencia: tuple[str, ...] = ()
    decisiones: tuple[str, ...] = ()
    vinculo_externo: str | None = None
    hold: bool = True
    id: str | None = None
