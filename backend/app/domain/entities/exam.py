"""Entidad de dominio Examen (PURA).

Configuracion de monitoreo de un examen: detectores activos, umbral de score,
ventana temporal y politica de retencion (`04` Examen). La configuracion
operativa concreta es scope de C-07; aqui se modela la entidad base.
Sin SQLAlchemy (dominio puro / D1).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Examen:
    """Examen configurado por el administrador (`04` Examen)."""

    nombre: str
    umbral_score: float
    parametros: dict[str, str] = field(default_factory=dict)
    detectores: tuple[str, ...] = ()
    ventana: dict[str, str] = field(default_factory=dict)
    retencion: dict[str, str] = field(default_factory=dict)
    id: str | None = None
