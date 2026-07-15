"""Router de revision (c-16 slim, modelo evolucionado c-71 slice 2 D6).

POST /api/v1/review/session/{session_id}/decide
  Body: { decision: 'sin_hallazgos' | 'aprobado' | 'caso_abierto', observaciones?: str }
  Roles: revisor | coordinador | admin_sistema | proctor

Persiste la decision de REVISION (fase 1) en proctoring_session (columnas
decision/decision_actor/decision_at/decision_observaciones agregadas en
migracion 0013). Inmutable una vez seteada (RN-RV-07): segundo intento →
409 Conflict. `caso_abierto` NO valida ni anula la nota: solo deriva el
caso para la fase 2 (resolucion, `resolver_caso`, `POST .../resolve`).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.review.resolution_service import (
    CasoNoAbiertoError,
    EvidenciaRequeridaError,
    MotivoRequeridoError,
    ResolucionAlreadyMadeError,
    ReviewResolutionService,
)
from app.application.review.service import (
    DecisionAlreadyMadeError,
    ReviewDecisionService,
)
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.review.decision import DecisionResolucion, DecisionTerminal
from app.infrastructure.persistence.repositories.review import (
    SqlReviewAuditor,
    SqlSessionReviewRepository,
)
from app.presentation.api.v1.auth.dependencies import require_capability

router = APIRouter()

# D8: gating por capacidad config-driven, no por lista de roles hardcodeada.
# El proctor sigue con acceso de lectura a la cola (fuera de este endpoint de
# escritura); el `decide` (fase 1) exige `revisar_sesion`; el `resolve` (fase 2,
# veredicto) exige `resolver_caso` — hoy ambas concentradas en el revisor.
_require_revisor = require_capability("revisar_sesion")
_require_resolver = require_capability("resolver_caso")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class DecideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str  # 'sin_hallazgos' | 'aprobado' | 'caso_abierto'
    observaciones: str | None = None


class DecideResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    previous: str
    new: str
    actor: str
    decision_at: str
    nota_legal: str


_NOTA = (
    "Decision terminal del revisor (RN-RV-07 — INMUTABLE). El sistema NUNCA "
    "sanciona automaticamente (L2.5): este endpoint registra el juicio humano "
    "sobre la sesion. Cambios posteriores requieren un nuevo proceso (apelacion)."
)


class ResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolucion: str  # 'anulado_por_fraude' | 'caso_descartado'
    motivo: str  # obligatorio no vacio (D11)
    evidencia_ref: str | None = None  # obligatorio si anulado_por_fraude (D11)


class ResolveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    resolucion: str
    actor: str
    resolucion_at: str
    nota_anulada: bool
    nota_legal: str


_NOTA_RESOLVE = (
    "Veredicto de resolucion (RN-RV-06/07 — INMUTABLE, capacidad resolver_caso). "
    "El sistema NUNCA anula automaticamente (L2.5, regla #5): la anulacion es un "
    "acto humano explicito. El efecto sobre la nota es reversible por acto "
    "compensatorio append-only (hook c-18)."
)


def _parse_resolucion(value: str) -> DecisionResolucion:
    try:
        return DecisionResolucion(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"resolucion invalida: {value!r}. Validas: "
                "anulado_por_fraude, caso_descartado."
            ),
        ) from exc


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


def _parse_decision(value: str) -> DecisionTerminal:
    try:
        return DecisionTerminal(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"decision invalida: {value!r}. Validas: "
                "sin_hallazgos, aprobado, caso_abierto."
            ),
        ) from exc


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/session/{session_id}/decide",
    response_model=DecideResponse,
    summary="Decision terminal del revisor (inmutable) — c-16 slim",
)
async def decide_session(
    session_id: str,
    body: DecideRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(_require_revisor),
) -> DecideResponse:
    decision = _parse_decision(body.decision)
    actor = principal.subject or "unknown"

    factory = _get_session_factory(request)
    async with factory() as s:
        svc = ReviewDecisionService(
            repo=SqlSessionReviewRepository(s),
            auditor=SqlReviewAuditor(s),
        )
        try:
            result = await svc.decide(
                session_id,
                decision=decision,
                actor=actor,
                observaciones=body.observaciones,
            )
        except DecisionAlreadyMadeError as exc:
            # Audit del intento ya quedo dentro del service
            await s.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc
        except ValueError as exc:
            await s.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND
                if "no encontrada" in str(exc)
                else status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        await s.commit()

    return DecideResponse(
        session_id=result.session_id,
        previous=result.previous.value,
        new=result.new.value,
        actor=result.actor,
        decision_at=result.decision_at,
        nota_legal=_NOTA,
    )


@router.post(
    "/session/{session_id}/resolve",
    response_model=ResolveResponse,
    summary="Veredicto de resolucion (capacidad resolver_caso) — c-71 slice 2",
)
async def resolve_session(
    session_id: str,
    body: ResolveRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(_require_resolver),
) -> ResolveResponse:
    resolucion = _parse_resolucion(body.resolucion)
    actor = principal.subject or "unknown"

    factory = _get_session_factory(request)
    async with factory() as s:
        svc = ReviewResolutionService(
            repo=SqlSessionReviewRepository(s),
            auditor=SqlReviewAuditor(s),
        )
        try:
            result = await svc.resolve(
                session_id,
                resolucion=resolucion,
                actor=actor,
                motivo=body.motivo,
                evidencia_ref=body.evidencia_ref,
            )
        except ResolucionAlreadyMadeError as exc:
            await s.commit()  # el intento quedo auditado dentro del service
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc
        except CasoNoAbiertoError as exc:
            await s.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc
        except (MotivoRequeridoError, EvidenciaRequeridaError) as exc:
            await s.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        except ValueError as exc:
            await s.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND
                if "no encontrada" in str(exc)
                else status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        await s.commit()

    return ResolveResponse(
        session_id=result.session_id,
        resolucion=result.resolucion.value,
        actor=result.actor,
        resolucion_at=result.resolucion_at,
        nota_anulada=result.nota_anulada,
        nota_legal=_NOTA_RESOLVE,
    )
