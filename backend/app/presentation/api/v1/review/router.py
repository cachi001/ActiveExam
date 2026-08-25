"""Router de revision — modelo de UN SOLO PASO (colapsa c-16 + c-71 slice 2).

POST /api/v1/review/session/{session_id}/decide
  Body: { decision: 'aprobado' | 'anulado', motivo?: str, evidencia_ids?: [str] }
  Gate: capacidad `revisar_sesion` (quienes la tienen sale de CAPABILITY_ROLES —
  c-76 elimino los roles 'revisor' y 'proctor', absorbidos por COORDINADOR)

Persiste la decision TERMINAL, en un unico acto, en proctoring_session
(columnas decision/decision_actor/decision_at/decision_motivo/decision_evidencia_ids).
Inmutable una vez seteada (RN-RV-07): segundo intento → 409 Conflict.

`anulado` exige motivo no vacio + al menos un `event_id` en `evidencia_ids`
(D11): sin esto no queda registrado NI por que NI con que se anulo una nota.
No existe una segunda fase de "resolucion" — el owner del proyecto lo
rechazo explicitamente ("no existe el caso abierto"): quien revisa decide,
en el mismo acto.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.review.service import (
    DecisionAlreadyMadeError,
    EvidenciaRequeridaError,
    MotivoRequeridoError,
    ReviewDecisionService,
)
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.review.decision import DecisionSesion
from app.infrastructure.persistence.repositories.review import (
    SqlReviewAuditor,
    SqlSessionReviewRepository,
)
from app.presentation.api.v1.auth.dependencies import require_capability

_log = logging.getLogger(__name__)

router = APIRouter()

# D8: gating por capacidad config-driven, no por lista de roles hardcodeada.
# `revisar_sesion` cubre TODO el acto — decidir y, si corresponde, anular —
# porque ya no hay una capacidad separada `resolver_caso` (no hay segunda
# instancia que gatear aparte).
_require_revisor = require_capability("revisar_sesion")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class DecideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str  # 'aprobado' | 'anulado'
    motivo: str | None = None  # obligatorio no vacio si decision='anulado' (D11)
    evidencia_ids: list[str] = []  # obligatoria no vacia si decision='anulado' (D11)


class DecideResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    previous: str
    new: str
    actor: str
    decision_at: str
    nota_anulada: bool
    # Efecto del hook c-18 en Moodle. Distingue tres casos que NO son lo mismo:
    #   True  → Moodle confirmo el 0 en la libreta.
    #   False → se intento y no se pudo (sin identidad, Moodle caido): queda
    #           'fallido' y hay que reintentar la sincronizacion.
    #   None  → no aplicaba (la decision no anula, o Moodle no esta configurado).
    nota_anulada_en_moodle: bool | None = None
    nota_legal: str


_NOTA = (
    "Decision terminal del revisor (RN-RV-07 — INMUTABLE, un solo acto, sin "
    "segunda instancia). El sistema NUNCA sanciona automaticamente (L2.5): este "
    "endpoint registra el juicio humano sobre la sesion. Cambios posteriores "
    "requieren un nuevo proceso (apelacion / restitucion)."
)


def _parse_decision(value: str) -> DecisionSesion:
    try:
        decision = DecisionSesion(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"decision invalida: {value!r}. Validas: aprobado, anulado.",
        ) from exc
    if decision is DecisionSesion.PENDIENTE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="decision invalida: 'pendiente' no es una decision terminal.",
        )
    return decision


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


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/session/{session_id}/decide",
    response_model=DecideResponse,
    summary="Decision terminal del revisor, un solo paso (inmutable)",
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
                motivo=body.motivo,
                evidencia_ids=body.evidencia_ids,
            )
        except DecisionAlreadyMadeError as exc:
            # Audit del intento ya quedo dentro del service
            await s.commit()
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

    # Hook c-18: si la decision anula la nota, el efecto tiene que llegar a Moodle.
    # Sin esto la anulacion vivia SOLO en ActiveExam y el alumno conservaba en la
    # libreta la nota ya sincronizada — se anulaba por fraude y el 10 seguia puesto.
    #
    # Va DESPUES del commit y en su propia transaccion a proposito: la decision
    # humana ya esta registrada y es inmutable (RN-RV-07), asi que un Moodle caido
    # no puede tumbarla ni dejarla a medias. Si el push falla, el estado queda
    # 'fallido' con el detalle y se reintenta desde la pantalla de sincronizacion.
    nota_anulada_en_moodle: bool | None = None
    if result.nota_anulada:
        writeback_svc = getattr(request.app.state, "writeback_svc", None)
        if writeback_svc is not None:
            async with factory() as s2:
                try:
                    nota_anulada_en_moodle = await writeback_svc.anular_nota(
                        db=s2,
                        session_id=session_id,
                        actor=actor,
                        motivo=(body.motivo or "").strip(),
                    )
                    await s2.commit()
                except Exception:  # noqa: BLE001 — el veredicto ya es firme
                    # Se LOGUEA: tragar el error dejaba el efecto sobre la nota
                    # fallando en silencio, y desde afuera solo se veia un False
                    # sin causa. El veredicto sigue firme; esto es diagnostico.
                    _log.exception(
                        "Fallo el efecto en Moodle al anular la sesion %s", session_id
                    )
                    await s2.rollback()
                    nota_anulada_en_moodle = False

    return DecideResponse(
        session_id=result.session_id,
        previous=result.previous.value,
        new=result.new.value,
        actor=result.actor,
        decision_at=result.decision_at,
        nota_anulada=result.nota_anulada,
        nota_anulada_en_moodle=nota_anulada_en_moodle,
        nota_legal=_NOTA,
    )


class RestituirRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    motivo: str  # obligatorio: por que se revierte (apelacion, error, etc.)


class RestituirResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    actor: str
    nota_restituida: float | None
    nota_restituida_en_moodle: bool
    nota_legal: str


_NOTA_RESTITUIR = (
    "Acto compensatorio APPEND-ONLY (RN-RV-06): NO borra ni modifica la anulacion "
    "original — la cadena de custodia se rompe si se reescribe el pasado. Registra "
    "un acto nuevo; el estado efectivo de la nota se deriva del ULTIMO acto."
)


@router.post(
    "/session/{session_id}/restituir",
    response_model=RestituirResponse,
    summary="Revierte una anulacion y devuelve la nota (capacidad revisar_sesion)",
)
async def restituir_nota(
    session_id: str,
    body: RestituirRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(_require_revisor),
) -> RestituirResponse:
    """Restituye la nota de un examen anulado — la via de la APELACION.

    Es el espejo del hook de anulacion, y sin el la anulacion era irreversible
    en los hechos.
    """
    actor = principal.subject or "unknown"
    factory = _get_session_factory(request)

    async with factory() as s:
        svc = ReviewDecisionService(
            repo=SqlSessionReviewRepository(s),
            auditor=SqlReviewAuditor(s),
        )
        try:
            await svc.revertir_anulacion(session_id, actor=actor, motivo=body.motivo)
        except MotivoRequeridoError as exc:
            await s.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        except ValueError as exc:
            await s.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND
                if "no encontrada" in str(exc)
                else status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        await s.commit()

    # El efecto en Moodle va aparte del acto compensatorio, por lo mismo que en la
    # anulacion: el acto ya quedo asentado y es lo que define el estado efectivo.
    nota_restituida: float | None = None
    writeback_svc = getattr(request.app.state, "writeback_svc", None)
    if writeback_svc is not None:
        async with factory() as s2:
            try:
                nota_restituida = await writeback_svc.restituir_nota(
                    db=s2,
                    session_id=session_id,
                    actor=actor,
                    motivo=body.motivo.strip(),
                )
                await s2.commit()
            except Exception:  # noqa: BLE001 — la reversion ya es firme
                _log.exception(
                    "Fallo la restitucion de la nota en Moodle para la sesion %s",
                    session_id,
                )
                await s2.rollback()

    return RestituirResponse(
        session_id=session_id,
        actor=actor,
        nota_restituida=nota_restituida,
        nota_restituida_en_moodle=nota_restituida is not None,
        nota_legal=_NOTA_RESTITUIR,
    )
