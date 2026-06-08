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
    HabilitarAlternativaRequest,
    HabilitarAlternativaResponse,
    PendienteItem,
    PendientesResponse,
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
    """Elige la via alternativa sin biometria; escala a proctor, NO aborta (D3).

    C-63: registra la solicitud con estado pendiente_proctor y retorna
    puede_rendir=False hasta que el proctor habilite.
    """
    now = _now_iso()
    mensaje_id = await service.choose_alternative(
        user_id=principal.id_institucional,
        exam_id=body.exam_id,
        timestamp=now,
    )
    return AlternativeResponse(
        exam_id=body.exam_id,
        via_alternativa=True,
        escalado_a_proctor=True,
        mensaje_id=mensaje_id,
        estado="pendiente_proctor",
        puede_rendir=False,
    )


@router.post(
    "/alternative/{user_id}/habilitar",
    response_model=HabilitarAlternativaResponse,
)
async def habilitar_alternativa(
    user_id: str,
    body: HabilitarAlternativaRequest,
    service: ConsentService = Depends(get_consent_service),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> HabilitarAlternativaResponse:
    """Habilita la solicitud de via alternativa de un alumno (proctor/admin).

    C-63 D-06: solo accesible por roles proctor o admin.
    Transiciona pendiente_proctor -> habilitado_por_proctor.
    404 si no existe solicitud para el par (user_id, exam_id).
    403 si el principal no tiene rol proctor ni admin.
    """
    roles = set(getattr(principal, "roles", []))
    if not roles.intersection({"proctor", "admin", "admin_sistema"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol proctor o admin para habilitar la via alternativa.",
        )
    try:
        solicitud = await service.habilitar_alternativa(
            user_id=user_id,
            exam_id=body.exam_id,
            habilitado_por=principal.id_institucional,
            timestamp=_now_iso(),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return HabilitarAlternativaResponse(
        user_id=solicitud.user_id,
        exam_id=solicitud.exam_id,
        estado=solicitud.estado.value,
        habilitado_por=solicitud.habilitado_por,
        timestamp_habilitacion=solicitud.timestamp_habilitacion,
    )


@router.get("/alternative/pendientes", response_model=PendientesResponse)
async def listar_pendientes(
    service: ConsentService = Depends(get_consent_service),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> PendientesResponse:
    """Lista solicitudes de via alternativa pendientes de habilitacion (proctor/admin).

    C-63 D-06: solo accesible por roles proctor o admin. Sin paginacion (D-08 Open Q).
    """
    roles = set(getattr(principal, "roles", []))
    if not roles.intersection({"proctor", "admin", "admin_sistema"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol proctor o admin para ver las solicitudes pendientes.",
        )
    solicitudes = await service.listar_pendientes()
    return PendientesResponse(
        items=[
            PendienteItem(
                user_id=s.user_id,
                exam_id=s.exam_id,
                timestamp_solicitud=s.timestamp_solicitud,
            )
            for s in solicitudes
        ]
    )


@router.get("/gate", response_model=GateResponse)
async def gate(
    service: ConsentService = Depends(get_consent_service),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    exam_id: str = Query(...),
) -> GateResponse:
    """Estado del gate de consentimiento (consumible por C-09, D4).

    C-63: VIA_ALTERNATIVA_PENDIENTE -> puede_avanzar=False (gate cerrado hasta habilitacion).
    VIA_ALTERNATIVA_HABILITADA -> puede_avanzar=True (proctor habilito; biometria no requerida).
    """
    resolucion = await service.resolve(
        user_id=principal.id_institucional, exam_id=exam_id
    )
    # Gate: puede avanzar solo si no es NO_RESUELTO ni PENDIENTE
    puede_avanzar = resolucion not in (
        ResolucionConsentimiento.NO_RESUELTO,
        ResolucionConsentimiento.VIA_ALTERNATIVA_PENDIENTE,
    )
    return GateResponse(
        exam_id=exam_id,
        resolucion=resolucion.value,
        puede_avanzar=puede_avanzar,
        biometria_habilitada=resolucion == ResolucionConsentimiento.CONSENTIDO,
    )
