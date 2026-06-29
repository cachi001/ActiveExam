"""Schemas Pydantic para los endpoints de exam_content (C-69).

Todos con extra='forbid' (regla dura de código).
D3: es_correcta NO aparece en ningún schema de respuesta al cliente.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OmitidaItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: str
    nombre: str
    motivo: str = ""


class ImportReporteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    examen_id: str
    importadas: int
    omitidas: list[OmitidaItemResponse]


# ---------------------------------------------------------------------------
# Schema de catálogo para el alumno — D3: es_correcta AUSENTE
# ---------------------------------------------------------------------------


class ExamenContenidoResumenResponse(BaseModel):
    """Resumen de examen para el catálogo del alumno/admin.

    Metadatos: id, titulo, cantidad de preguntas y, si el examen tiene comisión
    asociada (D11, NULLABLE), comision_id/comision_nombre/materia_nombre.
    D3: es_correcta AUSENTE — opciones y preguntas no viajan en el listado.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    titulo: str
    cantidad_preguntas: int
    comision_id: str | None = None
    comision_nombre: str | None = None
    materia_nombre: str | None = None


class ExamenesContenidoPaginadosResponse(BaseModel):
    """Catálogo de exámenes paginado (C-69 admin-sync, tarea 4).

    Forma estándar de paginación serverside: la página de items + el total global
    filtrado (no solo el de la página). El frontend usa `items`; `total` permite
    construir el paginador. D3: es_correcta AUSENTE en cada item.
    """

    model_config = ConfigDict(extra="forbid")

    items: list[ExamenContenidoResumenResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Schemas de rendición — D3: es_correcta AUSENTE en todos (nunca viaja al cliente)
# ---------------------------------------------------------------------------


class OpcionRendicionResponse(BaseModel):
    """Opción de respuesta para la rendición del alumno (sin es_correcta — D3)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    texto: str
    orden: int
    # D3: es_correcta AUSENTE — la opción correcta NUNCA viaja al cliente


class PreguntaRendicionResponse(BaseModel):
    """Pregunta para la rendición del alumno."""

    model_config = ConfigDict(extra="forbid")

    id: str
    enunciado: str
    tipo: str
    orden: int
    opciones: list[OpcionRendicionResponse]


class ExamenRendicionResponse(BaseModel):
    """Examen de contenido proyectado para la rendición del alumno."""

    model_config = ConfigDict(extra="forbid")

    id: str
    titulo: str
    preguntas: list[PreguntaRendicionResponse]


# ---------------------------------------------------------------------------
# Materia + comisión (C-69 sección 6, D11) — endpoints admin
# ---------------------------------------------------------------------------


class MateriaInlineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str
    nombre: str


class ComisionInlineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str
    nombre: str
    periodo: str | None = None
    anio: int | None = None


class AltaInlineRequest(BaseModel):
    """Alta inline de materia + comisión; opcionalmente asocia un examen."""

    model_config = ConfigDict(extra="forbid")

    materia: MateriaInlineRequest
    comision: ComisionInlineRequest
    examen_id: str | None = None


class MateriaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    codigo: str
    nombre: str


class ComisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    materia_id: str
    codigo: str
    nombre: str
    periodo: str | None = None
    anio: int | None = None


class AltaInlineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    materia: MateriaResponse
    comision: ComisionResponse
    examen_id: str | None = None


class AsociarComisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comision_id: str


class AsociarComisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    examen_id: str
    comision_id: str


# ---------------------------------------------------------------------------
# Destino del write-back a Moodle POR EXAMEN (C-69, D12 parte B)
# ---------------------------------------------------------------------------


class MoodleTargetRequest(BaseModel):
    """Body para fijar el destino de write-back de un examen.

    Ambos NULLABLE: enviar null limpia el destino y vuelve al fallback global.
    extra='forbid' (regla dura de código).
    """

    model_config = ConfigDict(extra="forbid")

    moodle_courseid: int | None = None
    moodle_cmid: int | None = None


class MoodleTargetResponse(BaseModel):
    """Destino de write-back a Moodle de un examen (estado actual tras el update)."""

    model_config = ConfigDict(extra="forbid")

    examen_id: str
    moodle_courseid: int | None = None
    moodle_cmid: int | None = None


# ---------------------------------------------------------------------------
# Resultados del examen + sincronización a Moodle (C-69 admin-sync, tareas 2-3)
# ---------------------------------------------------------------------------


class ResultadoAlumnoResponse(BaseModel):
    """Fila de resultados de un examen para el admin.

    L2.5 / D3: NUNCA incluye es_correcta ni respuestas — solo identidad del alumno,
    nota académica y estado del envío a Moodle.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str
    alumno_idnumber: str | None = None
    alumno_email: str | None = None
    alumno_nombre: str | None = None
    nota: float | None = None
    estado_moodle: str  # pendiente | enviado | fallido | sin_token
    actualizado_en: datetime | None = None


class ResultadosExamenPaginadosResponse(BaseModel):
    """Resultados de un examen paginados (forma estándar { items, total, page, page_size })."""

    model_config = ConfigDict(extra="forbid")

    items: list[ResultadoAlumnoResponse]
    total: int
    page: int
    page_size: int


class SincronizarMoodleResponse(BaseModel):
    """Resultado de la sincronización manual de notas a Moodle disparada por el admin."""

    model_config = ConfigDict(extra="forbid")

    enviadas: int
    fallidas: int
    sin_token: int
    total: int
    mensaje: str | None = None


# ---------------------------------------------------------------------------
# "Mis notas" del alumno (C-69, student-facing)
# ---------------------------------------------------------------------------


class MiNotaResponse(BaseModel):
    """Una nota finalizada del alumno + estado de envío a Moodle + estado L2.5.

    ``en_cola_revision`` (L2.5): True si el score de proctoring de la sesión supera
    el umbral de cola de revisión (``score >= umbral_revision``). El score PRIORIZA
    la revisión humana; NUNCA es una sanción.
    L2.5 / D3: NUNCA incluye es_correcta ni respuestas.
    """

    model_config = ConfigDict(extra="forbid")

    examen_id: str
    examen_titulo: str
    nota: float | None = None
    estado_moodle: str  # pendiente | enviado | fallido | sin_token
    en_cola_revision: bool
    score: float | None = None
    umbral_revision: float | None = None
    eventos: int
    finalizada_en: datetime | None = None


class MisNotasResponse(BaseModel):
    """Notas finalizadas del alumno autenticado (forma { items, total })."""

    model_config = ConfigDict(extra="forbid")

    items: list[MiNotaResponse]
    total: int
