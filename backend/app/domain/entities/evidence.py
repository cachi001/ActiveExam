"""Entidad de dominio Evidencia (PURA): cadena de custodia completa.

Modela los hashes y firmas de la cadena de custodia (cliente -> backend -> clave
maestra -> re-inferencia) y el ``uri_bucket`` al binario en el storage WORM
(`04` Evidencia). La captura/firma maestra y el bucket WORM concretos son scope
de C-12; aqui se modelan las columnas del contrato. Sin SQLAlchemy (dominio puro
/ D1).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Evidencia:
    """Evidencia con cadena de custodia (`04` Evidencia)."""

    session_id: str
    uri_bucket: str
    hash_cliente: str | None = None
    firma_cliente: str | None = None
    hash_backend: str | None = None
    firma_maestra: str | None = None
    output_reinferencia: dict[str, str] = field(default_factory=dict)
    meta: dict[str, str] = field(default_factory=dict)
    id: str | None = None
