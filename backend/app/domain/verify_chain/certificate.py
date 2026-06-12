"""Value objects del certificado de verificación de cadena (c-18 slim).

El certificado emitido es **autoportante**: incluye hashes + algoritmo + sello
temporal sin exponer el binario crudo ni PII. Un perito independiente puede
recomputar SHA-256 del screenshot original (que vive en `proctoring_event`,
solo accesible con autorización) y comparar contra `actual` para confirmar
que la verificación fue honesta.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class ChainVerificationStatus(str, enum.Enum):
    """Resultado global del verify-chain."""

    INTACT = "intact"  # todos los stages coinciden — evidencia sostenida
    BROKEN = "broken"  # algun stage no coincide — evidencia NO sostenida
    MATERIAL_MISSING = "material_missing"  # falta material (screenshot o hash null)


@dataclass(frozen=True)
class ChainStageResult:
    """Resultado de una etapa de verificación.

    En slim el unico stage es 'screenshot_recorded' (SHA-256 del binario
    actual vs hash registrado al ingerir). c-68 agrega 4 etapas full:
    'client_hmac', 'backend_rehash', 'master_signature', 'reinference'.
    """

    stage: str
    expected: str  # hash/firma registrado
    actual: str  # hash/firma re-calculado
    match: bool


@dataclass(frozen=True)
class CustodyChainCertificate:
    """Certificado autoportante del verify-chain.

    Diseñado para que un perito externo lo pueda validar sin necesidad de
    re-llamar a la API: incluye event_id, status global, algoritmo usado,
    detalle por stage y timestamp en formato ISO 8601 UTC.

    NO incluye: el binario del screenshot, PII del titular, contenido del
    evento. Solo hashes + metadatos verificables criptográficamente.
    """

    event_id: str
    status: ChainVerificationStatus
    algorithm: str
    stages: list[ChainStageResult]
    verified_at: str  # ISO 8601 UTC
