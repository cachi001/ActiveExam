"""Router de biometria de proctoring slim.

POST /sessions/{id}/biometria → 200/404

Sin auth (D7 — alcance demo).
Ley 25.326: el embedding se trata como dato sensible en toda la capa.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring import biometria_service
from app.presentation.api.v1.proctoring.biometria.schemas import (
    BiometriaOut,
    GuardarBiometriaIn,
)


def create_biometria_router(get_db) -> APIRouter:
    """Factory del router de biometria."""
    router = APIRouter()

    @router.post(
        "/sessions/{session_id}/biometria",
        response_model=BiometriaOut,
        summary="Guardar resultado biometrico de la sesion",
    )
    async def guardar_biometria(
        session_id: str,
        body: GuardarBiometriaIn,
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> BiometriaOut:
        """Persiste el resultado del liveness challenge y verificacion biometrica.

        Ley 25.326: el embedding facial es dato sensible. PRODUCCION: cifrar con
        KMS antes de persistir; purgar al egreso del estudiante (DD-13, DSR).
        """
        await biometria_service.guardar_biometria(
            db=db,
            session_id=session_id,
            liveness_ok=body.liveness_ok,
            retos_resueltos=body.retos_resueltos,
            resultado=body.resultado,
            embedding=body.embedding,
        )
        return BiometriaOut(ok=True)

    return router
