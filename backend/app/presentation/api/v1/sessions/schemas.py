"""Schemas Pydantic del cierre de sesion (C-13, extra='forbid')."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FinishSessionResponse(BaseModel):
    """Respuesta de POST /sessions/{id}/finish: cierre encolado (no bloqueante).

    El score final lo calcula la tarea asincrona; aqui solo se confirma el encolado
    (RN-SC-04). El estudiante NO recibe veredicto alguno (L2.5)."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    estado: str
    consolidacion_encolada: bool
