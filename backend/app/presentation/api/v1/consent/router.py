"""Router del consentimiento informado (FastAPI, C-08).

Endpoints del estudiante autenticado (C-06 ``get_current_principal``). El acuse se
asocia al ``id_institucional`` del principal (no se confia en un user_id del body).
Errores de dominio -> 422 (falta accion afirmativa / version desconocida) y 403
(gate no resuelto).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.application.consent.service import ConsentService
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.consent_flow.errors import (
    ConsentNotResolvedError,
    MissingAffirmativeActionError,
    UnknownConsentVersionError,
)
from app.domain.consent_flow.rules import ResolucionConsentimiento
from app.presentation.api.v1.auth.dependencies import get_current_principal
from app.presentation.api.v1.consent.dependencies import get_consent_service
from app.presentation.api.v1.consent.schemas import (
    AlternativeRequest,
    AlternativeResponse,
    ConsentResponse,
    ConsentTextResponse,
    GateResponse,
    RecordConsentRequest,
)

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/text", response_model=ConsentTextResponse)
async def get_text(
    service: ConsentService = Depends(get_consent_service),
    version: str | None = Query(default=None),
    _principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> ConsentTextResponse:
    """Texto vigente del consentimiento (cinco bloques + version, RN-CO-01)."""
    try:
        vista = service.get_text_view(version)
    except UnknownConsentVersionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return ConsentTextResponse(
        version=vista.version, bloques=vista.bloques, hash_texto=vista.hash_texto
    )


@router.post("", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED)
async def record_consent(
    body: RecordConsentRequest,
    service: ConsentService = Depends(get_consent_service),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> ConsentResponse:
    """Registra el acuse inmutable; 422 si falta accion afirmativa (D2)."""
    try:
        acuse = await service.record_consent(
            user_id=principal.id_institucional,
            exam_id=body.exam_id,
            version_texto=body.version_texto,
            affirmative_action=body.affirmative_action,
            timestamp=_now_iso(),
        )
    except (MissingAffirmativeActionError, UnknownConsentVersionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return ConsentResponse(
        id=acuse.id,
        user_id=acuse.user_id,
        exam_id=acuse.exam_id,
        version_texto=acuse.version_texto,
        timestamp=acuse.timestamp,
        hash=acuse.hash,
    )


@router.post("/alternative", response_model=AlternativeResponse)
async def choose_alternative(
    body: AlternativeRequest,
    service: ConsentService = Depends(get_consent_service),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> AlternativeResponse:
    """Elige la via alternativa sin biometria; escala a proctor, NO aborta (D3)."""
    mensaje_id = await service.choose_alternative(
        user_id=principal.id_institucional,
        exam_id=body.exam_id,
        timestamp=_now_iso(),
    )
    return AlternativeResponse(
        exam_id=body.exam_id,
        via_alternativa=True,
        escalado_a_proctor=True,
        mensaje_id=mensaje_id,
    )


@router.get("/gate", response_model=GateResponse)
async def gate(
    service: ConsentService = Depends(get_consent_service),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    exam_id: str = Query(...),
) -> GateResponse:
    """Estado del gate de consentimiento (consumible por C-09, D4)."""
    resolucion = await service.resolve(
        user_id=principal.id_institucional, exam_id=exam_id
    )
    puede_avanzar = resolucion != ResolucionConsentimiento.NO_RESUELTO
    return GateResponse(
        exam_id=exam_id,
        resolucion=resolucion.value,
        puede_avanzar=puede_avanzar,
        biometria_habilitada=resolucion == ResolucionConsentimiento.CONSENTIDO,
    )
