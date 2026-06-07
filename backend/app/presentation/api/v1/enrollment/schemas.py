"""Schemas Pydantic de los endpoints de enrollment biometrico (C-56, task 6.1).

Regla dura del proyecto: ``model_config = ConfigDict(extra='forbid')`` en todos
los schemas. Todo campo no declarado es rechazado (evita inyeccion de campos
no esperados).
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class FotoPerfilRequest(BaseModel):
    """Request de subida de foto de perfil (endpoint POST /enrollment/foto-perfil).

    ``imagen_base64``: dataURL base64 de la foto (con o sin prefijo data:...).
    """

    model_config = ConfigDict(extra="forbid")

    imagen_base64: str


class FotoPerfilResponse(BaseModel):
    """Response de subida de foto de perfil exitosa.

    ``foto_referencia_id``: UUID opaco del registro creado en ``foto_referencia``.
    El cliente persiste este ID en el store (no el binario de la foto).
    """

    model_config = ConfigDict(extra="forbid")

    foto_referencia_id: UUID


class EmbeddingReferenciaRequest(BaseModel):
    """Request de persistencia del embedding biometrico de referencia.

    ``embedding``: vector de exactamente 128 floats (descriptor facial 128-d).
    DATO SENSIBLE (Ley 25.326): nunca se loguea. El backend lo cifra at-rest
    con Fernet antes de persistirlo.
    """

    model_config = ConfigDict(extra="forbid")

    embedding: list[float]

    @field_validator("embedding")
    @classmethod
    def validar_dimension(cls, v: list[float]) -> list[float]:
        """Valida que el embedding tenga exactamente 128 dimensiones."""
        if len(v) != 128:
            raise ValueError(
                f"El embedding debe tener exactamente 128 dimensiones, "
                f"recibido: {len(v)}."
            )
        return v


class EmbeddingReferenciaResponse(BaseModel):
    """Response de persistencia exitosa del embedding de referencia.

    ``referencia_id``: UUID opaco del registro creado en ``embedding_referencia``.
    El cliente persiste este ID en el store (no el embedding crudo).
    """

    model_config = ConfigDict(extra="forbid")

    referencia_id: UUID
