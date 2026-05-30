"""Entidad de dominio Asignacion (PURA): relacion *—* proctor↔examen.

Materializa la tabla de union entre Usuario(proctor) y Examen (`04`). Un proctor
puede estar asignado a muchos examenes y un examen a muchos proctores.
Sin SQLAlchemy (dominio puro / D1).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Asignacion:
    """Asignacion proctor↔examen (tabla de union, `04`)."""

    proctor_id: str
    exam_id: str
    id: str | None = None
