"""Router de estadísticas institucionales (C-20 re-alcanzado, standalone).

GET /api/v1/stats/resumen → sumario agregado (conteos + riesgo + distribución).
RBAC: admin_sistema / coordinador (vista institucional). Agregado SIN PII.
L2.5: el "riesgo" prioriza la revisión humana, NUNCA emite veredicto.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from app.application.stats.resumen_service import obtener_resumen
from app.domain.auth.roles import Rol
from app.presentation.api.v1.auth.dependencies import require_roles

__all__ = ["create_stats_router"]


class ResumenStatsResponse(BaseModel):
    """Sumario institucional agregado (sin PII)."""

    model_config = ConfigDict(extra="forbid")

    total_examenes: int
    total_materias: int
    total_comisiones: int
    total_sesiones: int
    sesiones_finalizadas: int
    sesiones_en_riesgo: int
    umbral_riesgo: int
    distribucion_scores: dict[str, int]


def create_stats_router(session_factory=None) -> APIRouter:
    """Factory del router de stats (permite inyectar session_factory en tests)."""
    router = APIRouter(
        dependencies=[Depends(require_roles(Rol.ADMIN_SISTEMA, Rol.COORDINADOR))]
    )

    @router.get("/resumen", response_model=ResumenStatsResponse)
    async def resumen(request: Request) -> ResumenStatsResponse:
        factory = session_factory or getattr(request.app.state, "session_factory", None)
        if factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada (session_factory).",
            )
        async with factory() as db:
            r = await obtener_resumen(db)
        return ResumenStatsResponse(
            total_examenes=r.total_examenes,
            total_materias=r.total_materias,
            total_comisiones=r.total_comisiones,
            total_sesiones=r.total_sesiones,
            sesiones_finalizadas=r.sesiones_finalizadas,
            sesiones_en_riesgo=r.sesiones_en_riesgo,
            umbral_riesgo=r.umbral_riesgo,
            distribucion_scores=r.distribucion_scores,
        )

    return router
