"""Schemas Pydantic para endpoints de biometria de proctoring slim.

Todos con extra='forbid' (regla dura de codigo).
Ley 25.326: embedding es dato sensible.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GuardarBiometriaIn(BaseModel):
    """Body de POST /sessions/{id}/biometria.

    embedding es dato sensible (Ley 25.326). PRODUCCION: cifrar con KMS
    antes de persistir; purgar al egreso del estudiante (DD-13, DSR).
    """

    model_config = ConfigDict(extra="forbid")

    liveness_ok: bool = Field(..., description="True si el liveness challenge paso")
    retos_resueltos: list[str] = Field(
        default_factory=list,
        description="Lista de retos de liveness resueltos",
    )
    embedding: str | None = Field(
        None,
        description=(
            "Embedding facial (dato sensible, Ley 25.326). "
            "PRODUCCION: cifrar con KMS; purgar al egreso (DSR)."
        ),
    )
    resultado: str = Field(
        ...,
        description="'verificado' | 'rechazado' | 'pendiente'",
    )


class BiometriaOut(BaseModel):
    """Respuesta de POST /sessions/{id}/biometria → 200."""

    model_config = ConfigDict(extra="forbid")

    ok: bool = True


class VerificarIdentidadIn(BaseModel):
    """Body de POST /biometria/verificar.

    Ambos embeddings son dato sensible (Ley 25.326).
    """

    model_config = ConfigDict(extra="forbid")

    embedding_vivo: list[float] = Field(
        ..., description="Embedding facial capturado en vivo (dato sensible, Ley 25.326)"
    )
    embedding_referencia: list[float] = Field(
        ..., description="Embedding facial de referencia (dato sensible, Ley 25.326)"
    )
    umbral: float | None = Field(
        None,
        description="Umbral de distancia coseno. Si es None se usa UMBRAL_COSENO_DEFECTO (0.35)",
    )


class VerificarIdentidadOut(BaseModel):
    """Respuesta de POST /biometria/verificar."""

    model_config = ConfigDict(extra="forbid")

    distancia: float = Field(..., description="Distancia coseno entre embeddings (en [0, 2])")
    es_match: bool = Field(..., description="True si distancia < umbral (RN-BIO-03)")
    umbral: float = Field(..., description="Umbral usado para la comparacion")
