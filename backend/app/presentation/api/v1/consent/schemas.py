"""Schemas Pydantic del consentimiento (C-08). Todos con ``extra='forbid'``."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BloqueConsentimiento(_Strict):
    """Un bloque informativo del texto de consentimiento (titulo + cuerpo)."""
    titulo: str
    cuerpo: str


class ConsentTextResponse(_Strict):
    """Respuesta del texto de consentimiento — puede ser dict legacy o lista de bloques.

    Para la ruta GET /text sin version (legacy): bloques como dict[str, str].
    Para la ruta GET /text con texto versionado en DB: bloques como list[BloqueConsentimiento].
    Usamos ``Any`` para compatibilidad durante la transicion; los tests validan la forma.
    """
    version: str
    bloques: list[BloqueConsentimiento] | dict[str, str]
    hash_texto: str


# ---------------------------------------------------------------------------
# Schemas de version de texto (admin)
# ---------------------------------------------------------------------------


class ConsentVersionListItem(_Strict):
    """Item del listado de versiones disponibles (admin)."""
    version: str
    hash_texto: str
    created_at: datetime


class ConsentVersionCreate(_Strict):
    """Request para crear una nueva version del texto."""
    version: str
    bloques: list[BloqueConsentimiento]


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
    escalado_a_coordinador: bool
    mensaje_id: str
    estado: str = "pendiente_coordinador"
    puede_rendir: bool = False


# --- C-63: schemas del flujo de habilitacion por coordinador -------------------


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
