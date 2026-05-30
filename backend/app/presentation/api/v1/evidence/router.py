"""Router de la cadena de custodia de evidencia (C-12).

- ``POST /presign-upload``: URL firmada de PUT para subir el clip DIRECTO al storage
  (no transita el backend, RN-CC-04).
- ``POST /notify``: notificacion de evidencia subida (etapa 2): valida firma HMAC del
  cliente, re-hashea (2.a verificacion), deposita en WORM, audita y encola la firma.
  Hash divergente -> 409 + evento critico propagado (RN-CC-03, no silencio).
- ``POST /{evidencia_id}/download``: URL firmada de GET (expira 15 min, RN-CC-05) con
  PROPOSITO declarado, auditada como acceso.

El binario para la 2.a verificacion se re-descarga del storage WORM (el backend no
recibe el binario en el POST). L2.5: el endpoint persiste/propaga senal, no sanciona.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Request, status

from app.application.evidence.service import (
    FirmaClienteInvalidaError,
    NotificacionEvidencia,
)
from app.domain.audit_chain import AuditEntry
from app.domain.evidence.custody_chain import ManipulacionDetectada
from app.presentation.api.v1.evidence.dependencies import build_custody_service
from app.presentation.api.v1.evidence.schemas import (
    EvidenceNotifyRequest,
    EvidenceNotifyResponse,
    PresignDownloadResponse,
    PresignUploadResponse,
)

router = APIRouter()


@router.post("/presign-upload", response_model=PresignUploadResponse)
async def presign_upload(
    request: Request, object_key: str = Body(..., embed=True)
) -> PresignUploadResponse:
    """Emite la URL firmada de PUT para subir el clip directo al storage (RN-CC-04)."""
    presign = getattr(request.app.state, "presign_service", None)
    if presign is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Storage no inicializado (presign_service).",
        )
    up = presign.presign_upload(object_key=object_key)
    return PresignUploadResponse(
        upload_url=up.url, object_key=up.object_key, expires_in=up.expires_in
    )


@router.post("/notify", response_model=EvidenceNotifyResponse)
async def notify_evidence(
    request: Request, body: EvidenceNotifyRequest
) -> EvidenceNotifyResponse:
    """Etapa 2: valida firma + re-hash + WORM + audit + encola (Flujo 4)."""
    factory = getattr(request.app.state, "session_factory", None)
    worm = getattr(request.app.state, "worm_storage", None)
    if factory is None or worm is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Subsistema de evidencia no inicializado.",
        )

    # El backend re-descarga el binario del storage para re-hashear (no lo recibe).
    clip_bytes = worm.fetch(object_key=body.object_key)
    retain_until = _retain_until(request)

    async with factory() as session:
        service = build_custody_service(request, session)
        notif = NotificacionEvidencia(
            session_id=body.session_id,
            exam_id=body.exam_id,
            object_key=body.object_key,
            hash_cliente=body.hash_cliente,
            firma_cliente=body.firma_cliente,
        )
        try:
            ev = await service.recibir_notificacion(
                notif,
                clip_bytes=clip_bytes,
                retain_until=retain_until,
                actor="backend",
                ip=request.client.host if request.client else "",
                user_agent=request.headers.get("user-agent", ""),
            )
            await session.commit()
        except FirmaClienteInvalidaError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
            ) from exc
        except ManipulacionDetectada as exc:
            # El evento critico ya se persistio/propago dentro del servicio; aqui se
            # confirma la transaccion de la traza forense y se devuelve 409 explicito.
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="evidencia corrupta o manipulada (hash divergente, RN-CC-03)",
            ) from exc

    return EvidenceNotifyResponse(
        evidencia_id=ev.id or "", hash_backend=ev.hash_backend or "", encolada=True
    )


@router.post("/{evidencia_id}/download", response_model=PresignDownloadResponse)
async def download_evidence(
    request: Request, evidencia_id: str, proposito: str = Body(..., embed=True)
) -> PresignDownloadResponse:
    """URL firmada de GET (15 min, RN-CC-05) con proposito declarado, auditada."""
    factory = getattr(request.app.state, "session_factory", None)
    presign = getattr(request.app.state, "presign_service", None)
    if factory is None or presign is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Subsistema de evidencia no inicializado.",
        )
    async with factory() as session:
        from app.infrastructure.persistence.repositories.audit_log import (
            AuditLogSqlRepository,
        )
        from app.infrastructure.persistence.repositories.transactional import (
            EvidenceSqlRepository,
        )

        ev = await EvidenceSqlRepository(session).get(evidencia_id)
        if ev is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evidencia inexistente")
        object_key = ev.meta.get("object_key", evidencia_id)
        down = presign.presign_download(object_key=object_key)
        # Auditoria del acceso con PROPOSITO declarado (RN-CC-07).
        await AuditLogSqlRepository(session).append(
            AuditEntry(
                actor=_actor(request),
                timestamp="",
                ip=request.client.host if request.client else "",
                user_agent=request.headers.get("user-agent", ""),
                accion="acceso_evidencia",
                evidencia_id=evidencia_id,
                proposito=proposito,
            )
        )
        await session.commit()
    return PresignDownloadResponse(
        download_url=down.url, object_key=down.object_key, expires_in=down.expires_in
    )


def _retain_until(request: Request) -> str:
    """Retain-until por politica (placeholder: la politica de retencion es C-19)."""
    return getattr(
        getattr(request.app.state, "settings", None),
        "evidence_retain_until",
        "2099-12-31T00:00:00Z",
    )


def _actor(request: Request) -> str:
    """Actor del acceso (identidad del JWT cuando este cableado; backend por defecto)."""
    return getattr(request.state, "actor", "backend")
