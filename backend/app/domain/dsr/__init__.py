"""Dominio del DSR (Data Subject Rights) — c-17 slim.

Implementa los 4 derechos del titular bajo Ley 25.326:
- ACCESS (acceso a sus datos)
- RECTIFICATION (rectificacion)
- ERASURE (eliminacion / derecho al olvido)
- PORTABILITY (portabilidad en JSON)

Slim reutiliza el ``HoldVerifier`` de c-19 (NullHoldVerifier default). Cuando
llegue c-69 con tabla ``caso_disciplinario``, se inyecta ``SqlHoldVerifier``
sin tocar este servicio.
"""

from app.domain.dsr.ports import DsrAuditor, UserDsrRepository
from app.domain.dsr.report import (
    DsrAccessResponse,
    DsrErasureReport,
    DsrPortabilityResponse,
    DsrType,
)

__all__ = [
    "DsrAccessResponse",
    "DsrAuditor",
    "DsrErasureReport",
    "DsrPortabilityResponse",
    "DsrType",
    "UserDsrRepository",
]
