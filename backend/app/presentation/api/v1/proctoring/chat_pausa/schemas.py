"""Schemas Pydantic del chat bidireccional + pausa autorizada (slim, C-15 tareas 6.x).

Todos con extra='forbid' (regla dura de codigo). Transporte REST + polling (el
slim NO monta el WS de eventos).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# --- Chat ---


class MensajeChatIn(BaseModel):
    """Body de POST /sessions/{id}/chat."""

    model_config = ConfigDict(extra="forbid")

    autor: Literal["alumno", "proctor"] = Field(
        ..., description="Quien envia el mensaje: 'alumno' o 'proctor'."
    )
    texto: str = Field(..., min_length=1, max_length=2000)


class MensajeChatOut(BaseModel):
    """Mensaje de chat (respuesta de POST y elemento del GET)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    autor: str
    texto: str
    creado_en: Any  # datetime o str segun el ORM


# --- Pausa autorizada ---


class PausaSolicitudIn(BaseModel):
    """Body de POST /sessions/{id}/pausas."""

    model_config = ConfigDict(extra="forbid")

    motivo: str = Field(..., min_length=1, max_length=500)


class PausaSolicitudOut(BaseModel):
    """Respuesta de POST /sessions/{id}/pausas → 201 (pausa recien solicitada)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    estado: str  # 'solicitada'
    motivo: str
    solicitada_en: Any


class PausaDetalle(BaseModel):
    """Pausa completa (poll del alumno: GET /sessions/{id}/pausas)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    motivo: str
    estado: str
    solicitada_en: Any
    resuelta_en: Any = None
    proctor_actor: str | None = None
    inicio_en: Any = None
    fin_en: Any = None


class PausaPendiente(BaseModel):
    """Pausa pendiente para el poll del proctor (GET /pausas/pendientes)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    session_id: str
    etiqueta: str | None = None
    motivo: str
    solicitada_en: Any


class PausaResolverIn(BaseModel):
    """Body de PATCH /pausas/{id} (aprobar | rechazar)."""

    model_config = ConfigDict(extra="forbid")

    accion: Literal["aprobar", "rechazar"] = Field(
        ..., description="'aprobar' abre ventana (inicio_en); 'rechazar' no."
    )
    proctor_actor: str | None = Field(
        None, description="Subject del JWT del proctor que resuelve (audit trail)."
    )
