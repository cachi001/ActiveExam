"""Endpoints admin del motor de retencion (c-19) — solo ``admin_sistema``.

Triggers manuales del motor: se invocan via HTTP para poder testear el ciclo
end-to-end sin necesidad de un scheduler. En produccion el scheduler externo
(cron de Railway / GitHub Action) llama a estos endpoints en frecuencia
configurable, p.ej. una vez al dia.

Endpoints:
  POST /api/v1/admin/retention/session    -> aplica retencion de sesiones
  POST /api/v1/admin/retention/biometric  -> aplica eliminacion al egreso
  POST /api/v1/admin/retention/capturas   -> borra la IMAGEN de capturas vencidas
  GET  /api/v1/admin/retention/policy     -> devuelve la politica default

Cada llamada:
  * exige rol ``admin_sistema`` (Bearer JWT) via ``require_roles``
  * abre una session SQL por request (patron session-per-request)
  * llama al RetentionEngine con los adaptadores SQL activeexam cableados
  * commit explicito al final para que el cascade DELETE viaje a la DB
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.audit.acciones import (
    AccionAuditoria,
    EntidadAuditoria,
    ModuloAuditoria,
)
from app.application.audit.service import registrar_seguro
from app.application.compliance.retencion_capturas import purgar_capturas_vencidas
from app.application.retention.engine import RetentionEngine
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol
from app.domain.retention.policy import RetentionPolicy
from app.domain.retention.report import RetentionRunReport
from app.infrastructure.persistence.repositories.config_sistema import (
    ConfiguracionSistemaSqlRepository,
)
from app.infrastructure.persistence.repositories.retention import (
    SqlEmbeddingDeleter,
    SqlFotoDeleter,
    SqlRetentionAuditor,
    SqlSessionAgingRepository,
    SqlSessionDeleter,
    SqlUserEgressRepository,
)
from app.infrastructure.retention.null_hold_verifier import NullHoldVerifier
from app.presentation.api.v1.auth.dependencies import require_roles

router = APIRouter()

_require_admin = require_roles(Rol.ADMIN_SISTEMA)


# ---------------------------------------------------------------------------
# Schemas (extra='forbid' — regla dura del proyecto)
# ---------------------------------------------------------------------------


class RetentionPolicyRequest(BaseModel):
    """Politica override opcional para una corrida manual."""

    model_config = ConfigDict(extra="forbid")

    session_max_age_days: int | None = Field(
        default=None,
        gt=0,
        description=(
            "Si se omite, usa la default (180 dias). Override util en tests "
            "para no esperar 180 dias reales."
        ),
    )
    audit_log_retention_years: int | None = Field(
        default=None,
        gt=0,
        description="Si se omite, usa la default (5 anios).",
    )


class RetentionDeletionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_id: str
    target_kind: str
    reason: str
    at: str  # ISO 8601


class RetentionRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy: dict
    deletions: list[RetentionDeletionResponse]
    holds_deferred: list[str]
    run_at: str
    total_deletions: int
    total_holds_deferred: int


class RetentionPolicyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_max_age_days: int
    audit_log_retention_years: int


class PurgarCapturasResponse(BaseModel):
    """Resultado del purgado de capturas. IRREVERSIBLE (ver el endpoint)."""

    model_config = ConfigDict(extra="forbid")

    capturas_purgadas: int
    retencion_capturas_dias: int


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


def _resolve_policy(body: RetentionPolicyRequest | None) -> RetentionPolicy:
    default = RetentionPolicy.default()
    if body is None:
        return default
    return RetentionPolicy(
        session_max_age_days=(
            body.session_max_age_days
            if body.session_max_age_days is not None
            else default.session_max_age_days
        ),
        audit_log_retention_years=(
            body.audit_log_retention_years
            if body.audit_log_retention_years is not None
            else default.audit_log_retention_years
        ),
    )


def _report_to_response(report: RetentionRunReport) -> RetentionRunResponse:
    return RetentionRunResponse(
        policy={
            "session_max_age_days": report.policy_applied.session_max_age_days,
            "audit_log_retention_years": (
                report.policy_applied.audit_log_retention_years
            ),
        },
        deletions=[
            RetentionDeletionResponse(
                target_id=d.target_id,
                target_kind=d.target_kind,
                reason=d.reason,
                at=d.at.isoformat(),
            )
            for d in report.deletions
        ],
        holds_deferred=list(report.holds_deferred),
        run_at=report.run_at.isoformat(),
        total_deletions=report.total_deletions,
        total_holds_deferred=report.total_holds_deferred,
    )


def _build_engine(session: AsyncSession) -> RetentionEngine:
    return RetentionEngine(
        aging_repo=SqlSessionAgingRepository(session),
        egress_repo=SqlUserEgressRepository(session),
        hold_verifier=NullHoldVerifier(),
        session_deleter=SqlSessionDeleter(session),
        embedding_deleter=SqlEmbeddingDeleter(session),
        foto_deleter=SqlFotoDeleter(session),
        auditor=SqlRetentionAuditor(session),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/retention/policy",
    response_model=RetentionPolicyResponse,
    summary="Devuelve la politica de retencion por defecto",
)
async def get_default_policy(
    _principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> RetentionPolicyResponse:
    """Endpoint de introspeccion: que politica aplica un trigger sin body."""
    default = RetentionPolicy.default()
    return RetentionPolicyResponse(
        session_max_age_days=default.session_max_age_days,
        audit_log_retention_years=default.audit_log_retention_years,
    )


@router.post(
    "/retention/session",
    response_model=RetentionRunResponse,
    summary="Aplica retencion sobre sesiones (borra sesiones aged sin hold)",
)
async def run_session_retention(
    request: Request,
    principal: AuthenticatedPrincipal = Depends(_require_admin),
    body: RetentionPolicyRequest | None = None,
) -> RetentionRunResponse:
    """Ejecuta una pasada del motor sobre las sesiones aged.

    Para cada sesion mas vieja que ``policy.session_max_age_days``:
      - si el HoldVerifier reporta NO_HOLD -> DELETE (cascade a eventos)
      - si reporta HOLD -> se difiere y queda en el audit log
    """
    policy = _resolve_policy(body)
    actor = f"admin:{principal.subject}"

    session_factory = _get_session_factory(request)
    async with session_factory() as session:
        engine = _build_engine(session)
        try:
            report = await engine.apply_session_retention(policy, actor=actor)
        except Exception:
            await session.rollback()
            raise
        await session.commit()

    return _report_to_response(report)


@router.post(
    "/retention/biometric",
    response_model=RetentionRunResponse,
    summary="Borra biometria (embedding + foto) de usuarios egresados",
)
async def run_biometric_egress(
    request: Request,
    principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> RetentionRunResponse:
    """Borra ``embedding_referencia`` + ``foto_referencia`` de cada usuario
    con ``eliminado_en`` NOT NULL. El egreso del titular elimina la base
    legal para conservar su biometria (Ley 25.326)."""
    actor = f"admin:{principal.subject}"
    session_factory = _get_session_factory(request)
    async with session_factory() as session:
        engine = _build_engine(session)
        try:
            report = await engine.apply_embedding_egress(actor=actor)
        except Exception:
            await session.rollback()
            raise
        await session.commit()

    return _report_to_response(report)


@router.post(
    "/retention/capturas",
    response_model=PurgarCapturasResponse,
    summary="Borra la IMAGEN de capturas vencidas (IRREVERSIBLE)",
)
async def purgar_capturas(
    request: Request,
    principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> PurgarCapturasResponse:
    """Pone en NULL ``screenshot_b64`` de los eventos cuya sesion es mas vieja
    que ``retencion_capturas_dias`` (config del sistema, minimo 90 dias).

    CONSERVA el evento, su ``screenshot_sha256`` y el puntero WORM si existe:
    se borra la IMAGEN, no el registro de que existio ni su huella (cadena de
    custodia). Idempotente — correrlo dos veces seguidas la segunda vez purga 0.

    IRREVERSIBLE HOY: en produccion (Render) el deposito WORM esta apagado
    (``worm_storage=None``) — Postgres es la UNICA copia de la imagen. Una vez
    purgada, no se puede recuperar. Por eso este endpoint NUNCA se dispara
    solo: no hay cron ni scheduler colgado de esto, lo llama explicitamente
    quien administra el sistema.

    Es un borrado de evidencia: se audita SIEMPRE (incluso con 0 purgadas), con
    ``registrar_seguro`` en una sesion propia — la auditoria no debe perderse
    aunque el purgado ya haya commiteado.
    """
    session_factory = _get_session_factory(request)
    async with session_factory() as session:
        cfg = await ConfiguracionSistemaSqlRepository(session).ensure_singleton()
        dias = cfg.retencion_capturas_dias
        try:
            purgadas = await purgar_capturas_vencidas(session, dias)
        except Exception:
            await session.rollback()
            raise
        await session.commit()

    await registrar_seguro(
        session_factory,
        actor=f"admin:{principal.subject}",
        accion=AccionAuditoria.RETENCION_CAPTURAS_PURGADAS,
        modulo=ModuloAuditoria.EVIDENCIA,
        entidad=EntidadAuditoria.SISTEMA,
        proposito=(
            f"Purgó {purgadas} captura(s) más vieja(s) que {dias} días "
            "(imagen borrada, evento y hash conservados)"
        ),
    )

    return PurgarCapturasResponse(
        capturas_purgadas=purgadas, retencion_capturas_dias=dias
    )
