"""Router slim del verify-chain (c-18).

POST /api/v1/evidence/{event_id}/verify-chain

Solo rol ``admin_sistema`` puede invocarlo (en el futuro se extiende a
revisor / coordinador / auditor cuando llegue c-16/c-69; por ahora slim
queda admin-only para el endpoint legal). Cada llamada queda en el audit
log con propósito declarado.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.verify_chain.service import VerifyChainService
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol
from app.domain.verify_chain.certificate import (
    ChainStageResult,
    CustodyChainCertificate,
)
from app.infrastructure.persistence.repositories.verify_chain import (
    SqlChainVerificationAuditor,
    SqlEventMaterialRepository,
)
from app.presentation.api.v1.auth.dependencies import require_roles

router = APIRouter()

_require_staff = require_roles(Rol.ADMIN_SISTEMA)


# ---------------------------------------------------------------------------
# Schemas (extra='forbid' — regla dura)
# ---------------------------------------------------------------------------


class StageResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    expected: str
    actual: str
    match: bool


class ChainCertificateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    status: str  # 'intact' | 'broken' | 'material_missing'
    algorithm: str
    stages: list[StageResultResponse]
    verified_at: str
    note: str  # texto descriptivo para perito (slim/full)


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


_SLIM_NOTE = (
    "Certificado emitido por rama slim (c-18): 1 etapa verificable "
    "(screenshot_recorded). La cadena completa de 4 etapas (cliente HMAC, "
    "backend, firma maestra, re-inferencia) sera disponible cuando se "
    "implemente c-68 sobre tabla evidencia."
)


def _cert_to_response(cert: CustodyChainCertificate) -> ChainCertificateResponse:
    return ChainCertificateResponse(
        event_id=cert.event_id,
        status=cert.status.value,
        algorithm=cert.algorithm,
        stages=[
            StageResultResponse(
                stage=s.stage,
                expected=s.expected,
                actual=s.actual,
                match=s.match,
            )
            for s in cert.stages
        ],
        verified_at=cert.verified_at,
        note=_SLIM_NOTE,
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/evidence/{event_id}/verify-chain",
    response_model=ChainCertificateResponse,
    summary=(
        "Verifica cadena de custodia de un evento (slim: SHA-256 del screenshot)"
    ),
)
async def verify_chain(
    event_id: str,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(_require_staff),
) -> ChainCertificateResponse:
    """Recalcula SHA-256 del screenshot y lo compara con el hash registrado.

    Devuelve un certificado autoportante con el resultado por etapa y el
    status global. Cada llamada queda en el audit log con propopsito
    declarado ('verify-chain: cadena integra / rota / material faltante').
    """
    actor = f"{principal.subject or 'unknown'}:verify-chain"

    session_factory = _get_session_factory(request)
    async with session_factory() as session:
        service = VerifyChainService(
            event_repo=SqlEventMaterialRepository(session),
            auditor=SqlChainVerificationAuditor(session),
        )
        try:
            cert = await service.verify(event_id, actor=actor)
        except ValueError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except Exception:
            await session.rollback()
            raise
        await session.commit()

    return _cert_to_response(cert)
