"""Schemas Pydantic para endpoints de sesiones de proctoring slim.

Todos con extra='forbid' (regla dura de codigo).
Ley 25.326: screenshot_base64 y biometria son datos sensibles.
"""

from __future__ import annotations

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
    # C-69: vinculo REAL con el examen de contenido importado de Moodle XML.
    # NULLABLE — sesion sin contenido (modo 'test' o examen sin contenido) sigue valida.
    examen_contenido_id: str | None = Field(
        None, description="FK a examen_contenido(id). NULL = sesion sin contenido vinculado."
    )


class CrearSesionOut(BaseModel):
    """Respuesta de POST /sessions → 201."""

    model_config = ConfigDict(extra="forbid")

    id: str
    creada_en: Any  # datetime o str segun el ORM
    # C-69: eco del vinculo persistido. El front lo usa para confirmar contra qué
    # examen_contenido quedó atada la sesion (round-trip por la sesion real).
    examen_contenido_id: str | None = None


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
    # C-15 (6.4): True si el evento cayo dentro de una ventana de pausa autorizada.
    # El score del detalle EXCLUYE estos eventos (L2.5: contextualiza, no borra).
    en_pausa_autorizada: bool = False


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
    # ID del examen (referencia externa). La Cola de revision lo usa para vincular
    # la sesion con la materia/comision/examen. Sin esto, la cola descarta la sesion.
    exam_id: str | None = None
    etiqueta: str | None = None
    creada_en: Any
    finalizada_en: Any = None
    # ts del ultimo evento (o creada_en si no hubo eventos). La UI lo usa para
    # distinguir actividad reciente de sesiones calmas/abandonadas.
    ultimo_evento_en: Any = None
    total_eventos: int
    total_discrepancias: int
    score: int


class SesionDetalle(BaseModel):
    """Detalle completo de sesion para GET /sessions/{id} — vista del proctor."""

    model_config = ConfigDict(extra="forbid")

    id: str
    modo: str
    etiqueta: str | None = None
    # C-69: contra qué examen_contenido (Moodle XML) rindió el alumno. NULL si la
    # sesion no tiene contenido vinculado.
    examen_contenido_id: str | None = None
    creada_en: Any
    finalizada_en: Any = None
    score: int
    eventos: list[EventoDetalle]
    biometria: BiometriaDetalle | None = None
    # C-15 (3.3): cierre forzado (operativo, NO disciplinario). Se exponen para que
    # la UI del proctor refleje el estado al RECARGAR el detalle (no solo en la
    # accion). NULL si la sesion no fue cerrada de forma forzada.
    cierre_forzado_en: Any = None
    cierre_forzado_motivo: str | None = None


# --- C-15 (3.2): observaciones del proctor (insumo de C-16) ---


class ObservacionIn(BaseModel):
    """Body de POST /sessions/{id}/observaciones (proctor)."""

    model_config = ConfigDict(extra="forbid")

    texto: str = Field(..., min_length=1, max_length=2000)
    proctor_actor: str | None = Field(
        None, description="Subject del JWT del proctor que escribe (audit trail)."
    )


class ObservacionOut(BaseModel):
    """Observacion del proctor (respuesta de POST y elemento del GET)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    texto: str
    proctor_actor: str | None = None
    creada_en: Any


# --- C-15 (3.3): cierre forzado de sesion (operativo, NO disciplinario) ---


class CerrarForzadoIn(BaseModel):
    """Body de PATCH /sessions/{id}/cerrar-forzado (proctor).

    ``motivo`` es OBLIGATORIO (operativo): por que el proctor cierra la sesion.
    NO es un veredicto disciplinario (regla dura #5).
    """

    model_config = ConfigDict(extra="forbid")

    motivo: str = Field(..., min_length=1, max_length=500)
    proctor_actor: str | None = Field(
        None, description="Subject del JWT del proctor que fuerza el cierre (audit trail)."
    )


class CerrarForzadoOut(BaseModel):
    """Respuesta de PATCH /sessions/{id}/cerrar-forzado → 200."""

    model_config = ConfigDict(extra="forbid")

    id: str
    finalizada_en: Any
    cierre_forzado_en: Any
    cierre_forzado_por: str | None = None
    cierre_forzado_motivo: str | None = None


# --- C-69 sección 7: respuestas del alumno + write-back de nota ---


class RespuestaItem(BaseModel):
    """Respuesta del alumno para una pregunta (C-69 D8, sección 7)."""

    model_config = ConfigDict(extra="forbid")

    pregunta_id: str
    opcion_elegida_id: str


class SubmitRespuestasIn(BaseModel):
    """Body de POST /sessions/{id}/respuestas.

    El alumno envía sus respuestas antes de finalizar.

    Seguridad (H4): NO se aceptan campos de identidad del cliente. La identidad
    del alumno se persiste server-side al CREAR la sesión (desde el JWT) y es la
    única fuente para el write-back de la nota. Con ``extra='forbid'`` cualquier
    ``alumno_idnumber``/``alumno_email`` enviado por el cliente es rechazado (422)
    para cerrar la superficie de spoofing de identidad de la nota.
    """

    model_config = ConfigDict(extra="forbid")

    respuestas: list[RespuestaItem]


class SubmitRespuestasOut(BaseModel):
    """Respuesta de POST /sessions/{id}/respuestas → 201."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    respuestas_guardadas: int
