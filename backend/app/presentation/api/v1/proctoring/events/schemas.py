"""Schemas Pydantic para endpoints de eventos de proctoring slim.

Todos con extra='forbid' (regla dura de codigo).
Ley 25.326: screenshot_base64 es dato sensible.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SeveridadEnum(str, Enum):
    """Severidades validas para eventos de proctoring (alineadas con riskWeights del frontend)."""

    bajo = "bajo"
    medio = "medio"
    alto = "alto"
    critico = "critico"


class IngestEventoIn(BaseModel):
    """Body de POST /sessions/{id}/events.

    El campo screenshot_base64 es dato sensible (Ley 25.326).
    face_count_cliente: conteo de rostros reportado por el cliente; si viene,
    el servidor lo compara con la re-inferencia MediaPipe para producir el veredicto.
    """

    model_config = ConfigDict(extra="forbid")

    tipo: str = Field(..., description="Tipo de evento (ej. 'FACE_ABSENT', 'MULTIPLE_FACES')")
    severidad: SeveridadEnum = Field(..., description="Severidad del evento")
    ts_cliente: datetime = Field(..., description="Timestamp del cliente (no confiable)")
    payload: dict | None = Field(None, description="Datos adicionales del evento")
    screenshot_base64: str | None = Field(
        None,
        description=(
            "Screenshot en base64 (dato sensible, Ley 25.326). "
            "PRODUCCION: mover a MinIO/S3 WORM con cifrado at-rest."
        ),
    )
    face_count_cliente: int | None = Field(
        None,
        description=(
            "Conteo de rostros detectados por el cliente. "
            "El servidor re-detecta con MediaPipe (mismo motor) y produce veredicto."
        ),
    )


class IngestEventoOut(BaseModel):
    """Respuesta de POST /sessions/{id}/events → 201.

    Incluye el veredicto de re-inferencia server-side (coincide/discrepancia/no_evaluado)
    y el sha256 del screenshot para integridad liviana (D9).
    """

    model_config = ConfigDict(extra="forbid")

    evento_id: str
    veredicto_reinferencia: str = Field(
        ...,
        description="'coincide' | 'discrepancia' | 'no_evaluado'. L2.5: solo informativo.",
    )
    face_count_servidor: int | None = Field(
        None,
        description="Conteo re-detectado server-side. None si 'no_evaluado'.",
    )
    screenshot_sha256: str | None = Field(
        None,
        description="SHA-256 hex del screenshot (integridad liviana, D9). None si no habia screenshot.",
    )
