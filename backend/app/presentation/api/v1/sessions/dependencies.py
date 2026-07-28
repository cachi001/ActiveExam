"""Dependencias del cierre de sesion (C-13): compone el SessionFinalizationService."""

from __future__ import annotations

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.config.service import ConfigService
from app.application.scoring.finalization import SessionFinalizationService
from app.domain.scoring.risk_score import PesosScore
from app.infrastructure.persistence.repositories.event import EventSqlRepository
from app.infrastructure.persistence.repositories.transactional import (
    ExamSqlRepository,
    SessionSqlRepository,
)


def _build_pesos_provider(config_service: ConfigService):
    """Provider de pesos vivos: lee ``scoring_weights`` (config viva desde
    ``evento_score_config``) y los inyecta en ``PesosScore.por_tipo``.

    Asi ``finalization.consolidar()`` queda alineado con lo que el admin edita
    en la UI de Scoring (config-driven-scoring v2). Antes, el cierre usaba SOLO
    los pesos hardcodeados por severidad — la UI quedaba desconectada del flujo
    de score final."""

    async def provider() -> tuple[PesosScore, int]:
        efectiva = await config_service.get_efectiva()
        # scoring_weights es dict[str, int] (peso por tipo). Lo casteamos a float
        # para alinear con la API de PesosScore (que usa floats).
        por_tipo = {tipo: float(peso) for tipo, peso in efectiva.scoring_weights.items()}
        # Los tipos APAGADOS viajan aparte: pesan 0 en el cierre. Sin esto, un
        # detector desactivado en la UI seguia sumando su peso por severidad en el
        # score que se persiste.
        return (
            PesosScore(
                por_tipo=por_tipo, desactivados=efectiva.scoring_desactivados
            ),
            efectiva.version,
        )

    return provider


def build_finalization_service(
    request: Request, session: AsyncSession
) -> SessionFinalizationService:
    """Compone el servicio de cierre sobre una sesion async.

    Inyecta el provider de pesos vivos cuando el ``ConfigService`` esta disponible
    (caso normal en produccion). Si no esta, el servicio cae al fallback de pesos
    por severidad hardcodeado (RN-GLB-03)."""
    cola = getattr(request.app.state, "message_queue", None)
    if cola is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cola no inicializada (message_queue).",
        )
    config_service: ConfigService | None = getattr(request.app.state, "config_service", None)
    pesos_provider = _build_pesos_provider(config_service) if config_service is not None else None
    return SessionFinalizationService(
        sesiones=SessionSqlRepository(session),
        eventos=EventSqlRepository(session),
        examenes=ExamSqlRepository(session),
        cola=cola,
        pesos_provider=pesos_provider,
    )
