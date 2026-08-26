"""Schemas Pydantic para endpoints de eventos de proctoring activeexam.

Todos con extra='forbid' (regla dura de codigo).
Ley 25.326: screenshot_base64 es dato sensible.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.events.schema import Severidad

# La severidad del borde HTTP es EL MISMO enum que el del dominio. Antes habia aca
# un enum propio con el vocabulario en MASCULINO (bajo/medio/alto/critico) mientras
# el resto del sistema — dominio, ``evento_score_config``, el catalogo del cliente y
# las tablas de peso — habla en FEMENINO (baja/media/alta/critica). El cliente
# posteaba "alta" y este borde respondia 422: NINGUN evento de deteccion del cliente
# llegaba a persistirse. Un solo enum compartido hace imposible que las dos capas
# se separen otra vez.
SeveridadEnum = Severidad

# Alias historicos aceptados SOLO en la entrada, para no rechazar a un cliente que
# todavia mande el vocabulario viejo. Se normalizan al canonico antes de validar, asi
# nada masculino entra a la base.
_ALIAS_SEVERIDAD: dict[str, str] = {
    "bajo": Severidad.BAJA.value,
    "medio": Severidad.MEDIA.value,
    "alto": Severidad.ALTA.value,
    "critico": Severidad.CRITICA.value,
}


class IngestEventoIn(BaseModel):
    """Body de POST /sessions/{id}/events.

    El campo screenshot_base64 es dato sensible (Ley 25.326).
    face_count_cliente: conteo de rostros reportado por el cliente; si viene,
    el servidor lo compara con la re-inferencia MediaPipe para producir el veredicto.
    """

    model_config = ConfigDict(extra="forbid")

    tipo: str = Field(..., description="Tipo de evento (ej. 'FACE_ABSENT', 'MULTIPLE_FACES')")
    severidad: Severidad = Field(..., description="Severidad del evento")

    @field_validator("severidad", mode="before")
    @classmethod
    def _normalizar_severidad(cls, v: Any) -> Any:
        """Traduce los alias masculinos historicos al vocabulario canonico."""
        if isinstance(v, str):
            return _ALIAS_SEVERIDAD.get(v, v)
        return v
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
    screenshot_sha256_cliente: str | None = Field(
        None,
        description=(
            "Hash SHA-256 de la IMAGEN calculado por el cliente (cadena de custodia C-49, D5). "
            "Opcional — no bloquea la ingestión si está ausente. "
            "Desde c-78 (migración 0096) se PERSISTE y se contrasta contra el hash que "
            "recalcula el servidor: el veredicto queda en `custodia_cliente` "
            "('coincide' | 'discrepancia' | 'no_verificable'). L2.5: una discrepancia "
            "nunca rechaza el evento ni sanciona — es señal para el revisor humano."
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
