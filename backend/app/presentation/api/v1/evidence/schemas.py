"""Schemas Pydantic de la cadena de custodia de evidencia (C-12, extra='forbid').

El cliente sube el binario por URL firmada (custodia inicial, RN-CC-04) y luego
POSTea la NOTIFICACION (referencia + hash + firma HMAC de sesion). El backend
re-hashea y valida (etapa 2); el binario NO transita el backend. ``extra='forbid'``
rechaza campos no declarados (regla dura de codigo).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PresignUploadResponse(BaseModel):
    """URL firmada de PUT para subir el clip de evidencia directo al storage."""

    model_config = ConfigDict(extra="forbid")

    upload_url: str
    object_key: str
    expires_in: int


class EvidenceNotifyRequest(BaseModel):
    """Notificacion de evidencia subida: metadata + hash + firma del cliente."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    exam_id: str
    object_key: str
    hash_cliente: str = Field(..., min_length=64, max_length=64)
    firma_cliente: str = Field(..., min_length=1)


class EvidenceNotifyResponse(BaseModel):
    """Resultado de la etapa 2: evidencia persistida + encolada para firma."""

    model_config = ConfigDict(extra="forbid")

    evidencia_id: str
    hash_backend: str
    encolada: bool


class PresignDownloadResponse(BaseModel):
    """URL firmada de GET para descargar un clip (expira 15 min, RN-CC-05)."""

    model_config = ConfigDict(extra="forbid")

    download_url: str
    object_key: str
    expires_in: int
