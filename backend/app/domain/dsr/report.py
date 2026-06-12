"""Value objects del DSR (access / rectification / erasure / portability)."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class DsrType(str, enum.Enum):
    """Tipos de derecho del titular (Ley 25.326 art. 27)."""

    ACCESS = "access"
    RECTIFICATION = "rectification"
    ERASURE = "erasure"
    PORTABILITY = "portability"


@dataclass(frozen=True)
class DsrAccessResponse:
    """Datos personales devueltos en ACCESS / RECTIFICATION."""

    usuario_id: str
    id_institucional: str
    email: str
    nombre: str | None
    apellido: str | None
    roles: list[str]
    eliminado_en: str | None  # ISO 8601 o None


@dataclass(frozen=True)
class DsrPortabilityResponse:
    """Estructura exportable JSON con datos del titular + IDs de sesiones."""

    usuario_id: str
    id_institucional: str
    email: str
    nombre: str | None
    apellido: str | None
    roles: list[str]
    session_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DsrErasureReport:
    """Resultado del ERASURE: que se borro, que se difirio por hold."""

    usuario_id: str
    embeddings_deleted: int
    fotos_deleted: int
    sessions_deleted: list[str]
    sessions_deferred: list[str]
    anonimizado: bool
