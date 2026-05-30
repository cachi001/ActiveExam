"""Entidad de dominio Usuario (PURA).

Provisionado just-in-time desde el IdP (Keycloak), sin seed masivo (`04` Usuario).
La autenticacion/RBAC es scope de C-06: aqui solo se modela la entidad y sus
atributos federados. Sin SQLAlchemy (dominio puro / D1).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Usuario:
    """Usuario provisionado JIT desde el IdP (`04` Usuario)."""

    id_institucional: str
    email: str
    roles: tuple[str, ...] = ()
    attrs_federados: dict[str, str] = field(default_factory=dict)
    id: str | None = None
