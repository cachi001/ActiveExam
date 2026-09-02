"""Schemas Pydantic del chat bidireccional + pausa autorizada (activeexam, C-15 tareas 6.x).

Todos con extra='forbid' (regla dura de codigo). Transporte REST + polling (el
activeexam NO monta el WS de eventos).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# --- Chat ---


class MensajeChatIn(BaseModel):
    """Body de POST /sessions/{id}/chat."""

    model_config = ConfigDict(extra="forbid")

    # C-76 bloque 6 (D4): el actor pasa de 'proctor' a 'tutor'. El alumno NO puede
    # iniciar el hilo — la regla se valida server-side en chat_pausa_service
    # (regla dura #6: el cliente es sensor no confiable, no se confia en que el
    # front oculte el boton).
    autor: Literal["alumno", "tutor"] = Field(
        ..., description="Quien envia el mensaje: 'alumno' o 'tutor'."
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
    tutor_actor: str | None = None
    motivo_rechazo: str | None = None
    inicio_en: Any = None
    fin_en: Any = None


class PausaPendiente(BaseModel):
    """Pausa pendiente para el poll de quien supervisa (GET /pausas/pendientes)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    session_id: str
    #: Etiqueta de la sesion, que la manda el CLIENTE. Queda como fallback: la
    #: identidad de verdad es `alumno_nombre`, resuelta contra `usuario`.
    etiqueta: str | None = None
    #: Nombre de quien pide la pausa, resuelto SERVER-SIDE. None si la sesion no
    #: matchea ningun usuario (la pantalla cae a la etiqueta).
    alumno_nombre: str | None = None
    motivo: str
    solicitada_en: Any


class PausaResolverIn(BaseModel):
    """Body de PATCH /pausas/{id} (aprobar | rechazar)."""

    model_config = ConfigDict(extra="forbid")

    accion: Literal["aprobar", "rechazar"] = Field(
        ..., description="'aprobar' abre ventana (inicio_en); 'rechazar' no."
    )
    tutor_actor: str | None = Field(
        None, description="Subject del JWT del tutor que resuelve (audit trail)."
    )
    motivo_rechazo: str | None = Field(
        None,
        max_length=500,
        description=(
            "Motivo del rechazo (se muestra al alumno). OBLIGATORIO y no vacio "
            "cuando accion='rechazar'; ignorado (no se persiste) cuando accion='aprobar'."
        ),
    )

    @model_validator(mode="after")
    def _validar_motivo_rechazo(self) -> "PausaResolverIn":
        """Al rechazar, el motivo es obligatorio y no puede ser vacio/blanco."""
        if self.accion == "rechazar":
            if self.motivo_rechazo is None or not self.motivo_rechazo.strip():
                raise ValueError(
                    "motivo_rechazo es obligatorio (y no vacio) cuando accion='rechazar'."
                )
        return self
