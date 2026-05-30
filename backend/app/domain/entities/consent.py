"""Entidad de dominio Consentimiento (PURA, INMUTABLE).

Registro de acuse del consentimiento informado (`04` Consentimiento): version del
texto, timestamp y hash. Es INMUTABLE por diseno (DD-13, trazabilidad legal Ley
25.326): no expone ninguna mutacion, y su repositorio no ofrece ``update``. Sin
SQLAlchemy (dominio puro / D1).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Consentimiento:
    """Acuse inmutable de consentimiento informado (`04` Consentimiento)."""

    user_id: str
    exam_id: str
    version_texto: str
    timestamp: str
    hash: str
    id: str | None = None

    @staticmethod
    def calcular_hash(*, user_id: str, exam_id: str, version_texto: str, timestamp: str) -> str:
        """Hash determinista del acuse, para sellar el contenido del consentimiento."""
        payload = "|".join([user_id, exam_id, version_texto, timestamp])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
