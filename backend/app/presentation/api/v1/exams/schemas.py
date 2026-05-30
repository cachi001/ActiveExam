"""Schemas Pydantic de la API de configuracion de examen (C-07).

Todos con ``extra='forbid'`` (regla dura): un campo no declarado -> 422. Estos
schemas solo DESERIALIZAN; la validacion de reglas de negocio (ventana coherente,
catalogo de detectores, rango de umbral) vive en la capa de aplicacion (D4).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExamCreateRequest(_Strict):
    nombre: str = Field(min_length=1, max_length=255)
    inicio: str
    fin: str
    umbral_score: float
    detectores: list[str] = Field(default_factory=list)
    umbrales_detector: dict[str, float] = Field(default_factory=dict)
    politica_retencion: str = "estandar"
    exige_biometria: bool = True


class ExamResponse(_Strict):
    id: str | None
    nombre: str
    umbral_score: float
    detectores: list[str]
    ventana: dict[str, str]
    retencion: dict[str, str]
    parametros: dict


class EnabledStudentsRequest(_Strict):
    estudiantes: list[str]


class EnabledStudentsResponse(_Strict):
    estudiantes: list[str]


class AssignProctorsRequest(_Strict):
    proctores: list[str]


class AssignProctorsResponse(_Strict):
    proctores: list[str]


class ReferencePhotoRequest(_Strict):
    estudiante_id: str
    precomputada: bool = False
    hash_binario: str | None = None


class ReferencePhotoResponse(_Strict):
    estudiante_id: str
    precomputada: bool
    upload_url: str | None = None
    object_key: str | None = None
    expires_in: int | None = None
