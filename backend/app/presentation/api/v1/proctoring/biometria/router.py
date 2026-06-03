"""Router de biometria de proctoring slim.

POST /sessions/{id}/biometria → 200/404

Sin auth (D7 — alcance demo).
Ley 25.326: el embedding se trata como dato sensible en toda la capa.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring import biometria_service
from app.domain.biometrics.matching import (
    UMBRAL_COSENO_DEFECTO,
    EmbeddingInvalidoError,
    comparar_identidad,
)
from app.presentation.api.v1.proctoring.biometria.schemas import (
    BiometriaOut,
    GuardarBiometriaIn,
    VerificarIdentidadIn,
    VerificarIdentidadOut,
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

    @router.post(
        "/biometria/verificar",
        response_model=VerificarIdentidadOut,
        summary="Verificacion biometrica 1:1 (stateless, sin DB)",
    )
    async def verificar_identidad(
        body: VerificarIdentidadIn,
    ) -> VerificarIdentidadOut:
        """Compara dos embeddings faciales por distancia coseno (RN-BIO-01/02/03).

        Endpoint stateless: no persiste ni consulta la DB.
        Ley 25.326: ambos embeddings son dato sensible; no se loguean.
        """
        umbral = body.umbral if body.umbral is not None else UMBRAL_COSENO_DEFECTO
        try:
            resultado = comparar_identidad(
                body.embedding_vivo,
                body.embedding_referencia,
                umbral=umbral,
            )
        except EmbeddingInvalidoError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return VerificarIdentidadOut(
            distancia=resultado.distancia,
            es_match=resultado.es_match,
            umbral=resultado.umbral,
        )

    return router
