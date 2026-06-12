"""Router de revision (c-16 slim).

POST /api/v1/review/session/{session_id}/decide
  Body: { decision: 'descartada' | 'escalada' | 'derivada', observaciones?: str }
  Roles: revisor | coordinador | admin_sistema | proctor

Persiste la decision en proctoring_session (columnas decision/decision_actor/
decision_at/decision_observaciones agregadas en migracion 0013). Inmutable
una vez seteada (RN-RV-07): segundo intento → 409 Conflict.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.review.service import (
    DecisionAlreadyMadeError,
    ReviewDecisionService,
)
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol
from app.domain.review.decision import DecisionTerminal
from app.infrastructure.persistence.repositories.review import (
    SqlReviewAuditor,
    SqlSessionReviewRepository,
)
from app.presentation.api.v1.auth.dependencies import require_roles

router = APIRouter()

_require_revisor = require_roles(
    Rol.REVISOR, Rol.COORDINADOR, Rol.ADMIN_SISTEMA, Rol.PROCTOR
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class DecideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str  # 'descartada' | 'escalada' | 'derivada'
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
                "descartada, escalada, derivada."
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
