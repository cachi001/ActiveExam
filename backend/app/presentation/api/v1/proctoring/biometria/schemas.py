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
