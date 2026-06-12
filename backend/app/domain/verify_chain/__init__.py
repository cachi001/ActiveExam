"""Dominio del verificador de cadena de custodia (c-18 slim).

Slim: re-verifica la integridad del screenshot guardado en `proctoring_event`
recalculando SHA-256 y comparando con `screenshot_sha256` registrado al
ingerir el evento. La cadena de 4 etapas full (cliente HMAC, backend,
worker firma maestra, re-inferencia) se difiere a c-68 cuando llegue la
tabla `evidencia`.
"""

from app.domain.verify_chain.certificate import (
    ChainStageResult,
    ChainVerificationStatus,
    CustodyChainCertificate,
)
from app.domain.verify_chain.ports import ChainVerificationAuditor, EventMaterialRepository

__all__ = [
    "ChainStageResult",
    "ChainVerificationAuditor",
    "ChainVerificationStatus",
    "CustodyChainCertificate",
    "EventMaterialRepository",
]
