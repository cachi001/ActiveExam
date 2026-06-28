"""Schemas Pydantic para los endpoints de exam_content (C-69).

Todos con extra='forbid' (regla dura de código).
D3: es_correcta NO aparece en ningún schema de respuesta al cliente.
"""

from __future__ import annotations

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
