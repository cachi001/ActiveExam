"""Schemas Pydantic para endpoints de sesiones de proctoring slim.

Todos con extra='forbid' (regla dura de codigo).
Ley 25.326: screenshot_base64 y biometria son datos sensibles.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FinalizarSesionOut(BaseModel):
    """Respuesta de PATCH /sessions/{id}/finalizar → 200."""

    model_config = ConfigDict(extra="forbid")

    id: str
    finalizada_en: Any  # datetime o str segun el ORM


class CrearSesionIn(BaseModel):
    """Body de POST /sessions."""

    model_config = ConfigDict(extra="forbid")

    modo: str = Field(..., description="'test' o 'examen'")
    exam_id: str | None = Field(None, description="ID del examen (referencia externa)")
    etiqueta: str | None = Field(None, description="Etiqueta libre para la sesion")


class CrearSesionOut(BaseModel):
    """Respuesta de POST /sessions → 201."""

    model_config = ConfigDict(extra="forbid")

    id: str
    creada_en: Any  # datetime o str segun el ORM


class EventoDetalle(BaseModel):
    """Detalle de un evento de deteccion para GET /sessions/{id}.

    Incluye screenshot base64, sha256, veredicto de re-inferencia y conteos
    de rostros (cliente vs servidor) para la revision humana del proctor.

    PRODUCCION: screenshot_base64 es dato sensible (Ley 25.326).
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    tipo: str
    severidad: str
    ts_cliente: Any
    ts_backend: Any
    payload: dict | None = None
    screenshot_base64: str | None = None
    screenshot_sha256: str | None = None
    face_count_cliente: int | None = None
    face_count_servidor: int | None = None
    veredicto_reinferencia: str


class BiometriaDetalle(BaseModel):
    """Resultado biometrico para GET /sessions/{id}."""

    model_config = ConfigDict(extra="forbid")

    liveness_ok: bool
    retos_resueltos: list
    resultado: str
    registrada_en: Any


class SesionResumen(BaseModel):
    """Resumen de sesion para GET /sessions (lista)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    modo: str
    etiqueta: str | None = None
    creada_en: Any
    total_eventos: int
    total_discrepancias: int
    score: int


class SesionDetalle(BaseModel):
    """Detalle completo de sesion para GET /sessions/{id} — vista del proctor."""

    model_config = ConfigDict(extra="forbid")

    id: str
    modo: str
    etiqueta: str | None = None
    creada_en: Any
    finalizada_en: Any = None
    score: int
    eventos: list[EventoDetalle]
    biometria: BiometriaDetalle | None = None
