"""Schemas Pydantic de la verificacion biometrica (C-09, extra='forbid').

El cliente sube el clip por URL firmada (custodia inicial) y luego POSTea la
REFERENCIA al clip (uri + hash) + sus senales (liveness/camara virtual). El
backend re-infiere server-side: las senales del cliente son SENAL, no verdad
(RN-GLB-01). Pydantic ``extra='forbid'`` rechaza campos no declarados (regla dura).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ClientSignals(BaseModel):
    """Senales reportadas por el cliente (NO son la fuente de verdad, RN-GLB-01).

    Sirven para telemetria/diagnostico; el backend re-infiere sobre el clip y
    decide con su propio resultado. ``camara_virtual`` es la heuristica de
    integridad del cliente (DD-18)."""

    model_config = ConfigDict(extra="forbid")

    liveness_cliente_ok: bool = False
    camara_virtual: bool = False
    retos_resueltos: list[str] = Field(default_factory=list)


class VerifyIdentityRequest(BaseModel):
    """Solicitud de verificacion: referencia al clip bajo custodia + senales."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    clip_uri: str
    clip_hash: str = Field(..., min_length=64, max_length=64)
    client_signals: ClientSignals = Field(default_factory=ClientSignals)


class VerifyIdentityResponse(BaseModel):
    """Resultado del intento: veredicto re-inferido server-side."""

    model_config = ConfigDict(extra="forbid")

    veredicto: str
    distancia: float | None
    reintentos_restantes: int
    clave_sesion_emitida: bool
    escalado_a_proctor: bool
    intentos_fallidos: int


class PresignClipResponse(BaseModel):
    """URL firmada para subir el clip de verificacion (custodia inicial)."""

    model_config = ConfigDict(extra="forbid")

    upload_url: str
    object_key: str
    expires_in: int
