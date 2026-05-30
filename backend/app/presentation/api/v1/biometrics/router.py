"""Router de verificacion biometrica de identidad (FastAPI, C-09).

Endpoints del estudiante autenticado (C-06 ``get_current_principal``):
- ``POST /presign-clip``: URL firmada para subir el clip bajo custodia inicial.
- ``POST /verify``: re-inferencia server-side + comparacion 1:1 + emision de clave
  / reintentos / escalacion. El veredicto del cliente NO decide (RN-GLB-01).

El contador de reintentos se persiste en ``Sesion.metadata['intentos_fallidos']``
para que cada request reconstruya el ``EstadoVerificacion`` (max 2 reintentos).
Errores de dominio -> 403 (sin consentimiento), 409 (sin referencia), 422 (clip).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.application.biometrics.service import (
    ReferenciaFaltanteError,
    VerifyIdentityService,
)
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.biometrics.retries import EstadoVerificacion
from app.domain.consent_flow.errors import ConsentNotResolvedError
from app.presentation.api.v1.auth.dependencies import get_current_principal
from app.presentation.api.v1.biometrics.dependencies import get_verify_service
from app.presentation.api.v1.biometrics.schemas import (
    PresignClipResponse,
    VerifyIdentityRequest,
    VerifyIdentityResponse,
)

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.post("/presign-clip", response_model=PresignClipResponse)
async def presign_clip(
    request: Request,
    session_id: str,
    _principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> PresignClipResponse:
    """Devuelve la URL firmada para subir el clip de verificacion (custodia inicial).

    El clip sube DIRECTO al storage por URL firmada, no transita el backend
    (RN-CC-04, RN-GLB-01). El hash + firma del clip los aporta el cliente y el
    backend los re-verifica al re-inferir."""
    presign = getattr(request.app.state, "presign_service", None)
    if presign is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Storage no inicializado (presign).",
        )
    object_key = f"verification-clips/{session_id}/{_now_iso()}"
    presigned = presign.presign_upload(object_key=object_key)
    return PresignClipResponse(
        upload_url=presigned.url,
        object_key=presigned.object_key,
        expires_in=presigned.expires_in,
    )


@router.post("/verify", response_model=VerifyIdentityResponse)
async def verify_identity(
    body: VerifyIdentityRequest,
    service: VerifyIdentityService = Depends(get_verify_service),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> VerifyIdentityResponse:
    """Verifica la identidad re-infiriendo server-side sobre el clip (RN-GLB-01)."""
    sesion = await service._sesiones.get(body.session_id)
    if sesion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sesion no encontrada."
        )
    # La sesion del estudiante autenticado: no se confia en un user_id del body.
    if sesion.user_id != principal.id_institucional:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Sesion ajena."
        )

    # Reconstruye el estado de reintentos desde la metadata de la sesion.
    fallidos = int(sesion.metadata.get("intentos_fallidos", "0"))
    cerrado = sesion.metadata.get("verificacion_cerrada") == "true"
    estado = EstadoVerificacion(intentos_fallidos=fallidos, cerrado=cerrado)

    try:
        nuevo_estado, outcome = await service.verify(
            sesion=sesion,
            estado=estado,
            clip_uri=body.clip_uri,
            clip_hash=body.clip_hash,
            timestamp=_now_iso(),
        )
    except ConsentNotResolvedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except ReferenciaFaltanteError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    return VerifyIdentityResponse(
        veredicto=outcome.veredicto.value,
        distancia=outcome.distancia,
        reintentos_restantes=outcome.reintentos_restantes,
        clave_sesion_emitida=outcome.clave_sesion_emitida,
        escalado_a_proctor=outcome.escalado_a_proctor,
        intentos_fallidos=outcome.intentos_fallidos,
    )
