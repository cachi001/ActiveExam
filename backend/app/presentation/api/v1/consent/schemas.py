"""Schemas Pydantic del consentimiento (C-08). Todos con ``extra='forbid'``."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConsentTextResponse(_Strict):
    version: str
    bloques: dict[str, str]
    hash_texto: str


class RecordConsentRequest(_Strict):
    exam_id: str
    version_texto: str | None = None
    # Sin default True: la accion afirmativa debe enviarse explicita (sin
    # premarcado server-side). El backend la valida (D2).
    affirmative_action: bool = False


class ConsentResponse(_Strict):
    id: str | None
    user_id: str
    exam_id: str
    version_texto: str
    timestamp: str
    hash: str


class AlternativeRequest(_Strict):
    exam_id: str


class AlternativeResponse(_Strict):
    exam_id: str
    via_alternativa: bool
    escalado_a_proctor: bool
    mensaje_id: str
    estado: str = "pendiente_proctor"
    puede_rendir: bool = False


# --- C-63: schemas del flujo de habilitacion por proctor ----------------------


class HabilitarAlternativaRequest(_Strict):
    exam_id: str


class HabilitarAlternativaResponse(_Strict):
    user_id: str
    exam_id: str
    estado: str
    habilitado_por: str | None
    timestamp_habilitacion: str | None


class PendienteItem(_Strict):
    user_id: str
    exam_id: str
    timestamp_solicitud: str


class PendientesResponse(_Strict):
    items: list[PendienteItem]


class GateResponse(_Strict):
    exam_id: str
    resolucion: str
    puede_avanzar: bool
    biometria_habilitada: bool
