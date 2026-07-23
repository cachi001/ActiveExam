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

import logging

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

_log = logging.getLogger(__name__)

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
    # Efecto del hook c-18 en Moodle. Distingue tres casos que NO son lo mismo:
    #   True  → Moodle confirmo el 0 en la libreta.
    #   False → se intento y no se pudo (sin identidad, Moodle caido): queda
    #           'fallido' y hay que reintentar la sincronizacion.
    #   None  → no aplicaba (la resolucion no anula, o Moodle no esta configurado).
    # Sin esta distincion, la UI no puede avisar que la nota sigue viva en Moodle.
    nota_anulada_en_moodle: bool | None = None
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

    # Hook c-18: si el veredicto anula la nota, el efecto tiene que llegar a Moodle.
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
                        motivo=body.motivo.strip(),
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

    return ResolveResponse(
        session_id=result.session_id,
        resolucion=result.resolucion.value,
        actor=result.actor,
        resolucion_at=result.resolucion_at,
        nota_anulada=result.nota_anulada,
        nota_anulada_en_moodle=nota_anulada_en_moodle,
        nota_legal=_NOTA_RESOLVE,
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
    summary="Revierte una anulacion y devuelve la nota (capacidad resolver_caso)",
)
async def restituir_nota(
    session_id: str,
    body: RestituirRequest,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(_require_resolver),
) -> RestituirResponse:
    """Restituye la nota de un examen anulado — la via de la APELACION.

    Existia `revertir_anulacion` en el servicio pero sin endpoint: si a un alumno se
    le daba la razon, no habia por donde devolverle la nota. Es el espejo del hook
    de anulacion, y sin el la anulacion era irreversible en los hechos.
    """
    actor = principal.subject or "unknown"
    factory = _get_session_factory(request)

    async with factory() as s:
        svc = ReviewResolutionService(
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
