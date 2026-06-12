"""Router DSR slim (c-17).

POST /api/v1/dsr/access            -> devuelve datos del usuario autenticado
POST /api/v1/dsr/rectification     -> corrige email/nombre/apellido
POST /api/v1/dsr/erasure           -> borra biometria, sesiones sin hold, anonimiza
POST /api/v1/dsr/portability       -> exporta JSON estructurado

El titular ejecuta sobre SU PROPIO usuario (subject del JWT). Admin puede
operar sobre cualquiera (auditado con propopsito declarado).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dsr.service import DsrService
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol
from app.domain.dsr.report import (
    DsrAccessResponse,
    DsrErasureReport,
    DsrPortabilityResponse,
)
from app.infrastructure.persistence.repositories.dsr import (
    SqlDsrAuditor,
    SqlUserDsrRepository,
)
from app.infrastructure.retention.null_hold_verifier import NullHoldVerifier
from app.presentation.api.v1.auth.dependencies import get_current_principal

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TargetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usuario_id: str | None = None  # si None, opera sobre el subject del JWT


class RectificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usuario_id: str | None = None
    email: str | None = None
    nombre: str | None = None
    apellido: str | None = None


class AccessResponseDto(BaseModel):
    model_config = ConfigDict(extra="forbid")
    usuario_id: str
    id_institucional: str
    email: str
    nombre: str | None
    apellido: str | None
    roles: list[str]
    eliminado_en: str | None


class PortabilityResponseDto(BaseModel):
    model_config = ConfigDict(extra="forbid")
    usuario_id: str
    id_institucional: str
    email: str
    nombre: str | None
    apellido: str | None
    roles: list[str]
    session_ids: list[str]


class ErasureReportDto(BaseModel):
    model_config = ConfigDict(extra="forbid")
    usuario_id: str
    embeddings_deleted: int
    fotos_deleted: int
    sessions_deleted: list[str]
    sessions_deferred: list[str]
    anonimizado: bool
    nota_legal: str  # plazo legal + alcance slim


_NOTA_LEGAL = (
    "DSR atendida bajo Ley 25.326 art. 27 (plazo legal: 10 dias habiles). "
    "Slim: la asociacion usuario↔sesiones es heuristica (la FK formal vive "
    "en c-69 sucesor). Erasure conserva id_institucional como seudonimo "
    "irreversible. Sesiones con caso disciplinario abierto se difieren."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de datos no disponible.",
        )
    return factory


def _resolve_target(
    body_target: str | None, principal: AuthenticatedPrincipal
) -> str:
    """Si body trae usuario_id explicito → solo admin_sistema puede usarlo.
    Sino, se usa el subject del JWT (el propio titular).
    """
    if body_target is None:
        if principal.subject is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Falta usuario_id y el token no tiene subject.",
            )
        return principal.subject

    # Cross-user: solo admin_sistema
    roles = {r for r in (principal.roles or [])}
    if Rol.ADMIN_SISTEMA.value not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo admin_sistema puede operar DSR sobre otro usuario.",
        )
    return body_target


def _build_service(session: AsyncSession) -> DsrService:
    return DsrService(
        repo=SqlUserDsrRepository(session),
        hold_verifier=NullHoldVerifier(),
        auditor=SqlDsrAuditor(session),
    )


def _access_to_dto(r: DsrAccessResponse) -> AccessResponseDto:
    return AccessResponseDto(
        usuario_id=r.usuario_id,
        id_institucional=r.id_institucional,
        email=r.email,
        nombre=r.nombre,
        apellido=r.apellido,
        roles=r.roles,
        eliminado_en=r.eliminado_en,
    )


def _portability_to_dto(r: DsrPortabilityResponse) -> PortabilityResponseDto:
    return PortabilityResponseDto(
        usuario_id=r.usuario_id,
        id_institucional=r.id_institucional,
        email=r.email,
        nombre=r.nombre,
        apellido=r.apellido,
        roles=r.roles,
        session_ids=r.session_ids,
    )


def _erasure_to_dto(r: DsrErasureReport) -> ErasureReportDto:
    return ErasureReportDto(
        usuario_id=r.usuario_id,
        embeddings_deleted=r.embeddings_deleted,
        fotos_deleted=r.fotos_deleted,
        sessions_deleted=r.sessions_deleted,
        sessions_deferred=r.sessions_deferred,
        anonimizado=r.anonimizado,
        nota_legal=_NOTA_LEGAL,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/access", response_model=AccessResponseDto)
async def access(
    request: Request,
    body: TargetRequest | None = None,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> AccessResponseDto:
    target = _resolve_target((body.usuario_id if body else None), principal)
    actor = f"{principal.subject or 'unknown'}:dsr"
    factory = _get_session_factory(request)
    async with factory() as s:
        svc = _build_service(s)
        try:
            r = await svc.access(target, actor=actor)
        except ValueError as exc:
            await s.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        await s.commit()
    return _access_to_dto(r)


@router.post("/rectification", response_model=AccessResponseDto)
async def rectification(
    request: Request,
    body: RectificationRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> AccessResponseDto:
    target = _resolve_target(body.usuario_id, principal)
    actor = f"{principal.subject or 'unknown'}:dsr"
    factory = _get_session_factory(request)
    async with factory() as s:
        svc = _build_service(s)
        try:
            r = await svc.rectification(
                target,
                actor=actor,
                email=body.email,
                nombre=body.nombre,
                apellido=body.apellido,
            )
        except ValueError as exc:
            await s.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        await s.commit()
    return _access_to_dto(r)


@router.post("/portability", response_model=PortabilityResponseDto)
async def portability(
    request: Request,
    body: TargetRequest | None = None,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> PortabilityResponseDto:
    target = _resolve_target((body.usuario_id if body else None), principal)
    actor = f"{principal.subject or 'unknown'}:dsr"
    factory = _get_session_factory(request)
    async with factory() as s:
        svc = _build_service(s)
        try:
            r = await svc.portability(target, actor=actor)
        except ValueError as exc:
            await s.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        await s.commit()
    return _portability_to_dto(r)


@router.post("/erasure", response_model=ErasureReportDto)
async def erasure(
    request: Request,
    body: TargetRequest | None = None,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> ErasureReportDto:
    target = _resolve_target((body.usuario_id if body else None), principal)
    actor = f"{principal.subject or 'unknown'}:dsr"
    factory = _get_session_factory(request)
    async with factory() as s:
        svc = _build_service(s)
        try:
            r = await svc.erasure(target, actor=actor)
        except ValueError as exc:
            await s.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        await s.commit()
    return _erasure_to_dto(r)
