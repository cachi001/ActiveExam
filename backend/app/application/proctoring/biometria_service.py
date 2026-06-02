"""Servicio de aplicacion para biometria de proctoring slim.

Verifica que la sesion exista y persiste el resultado biometrico.
Ley 25.326: el embedding facial es dato sensible — comentado en el modelo ORM.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.proctoring import (
    ProctoringBiometriaModel,
    ProctoringSessionModel,
)
from app.infrastructure.persistence.repositories.proctoring import ProctoringRepository


async def guardar_biometria(
    db: AsyncSession,
    session_id: str,
    liveness_ok: bool,
    retos_resueltos: list,
    resultado: str,
    embedding: str | None = None,
) -> ProctoringBiometriaModel:
    """Persiste el resultado biometrico de una sesion.

    Args:
        db: Sesion async de SQLAlchemy.
        session_id: UUID de la sesion de proctoring.
        liveness_ok: True si el liveness challenge paso.
        retos_resueltos: Lista de retos de liveness resueltos.
        resultado: 'verificado' | 'rechazado' | 'pendiente'.
        embedding: Embedding facial en base64 (dato sensible, Ley 25.326).
            PRODUCCION: cifrar con KMS antes de persistir; purgar al egreso (DSR).

    Returns:
        ProctoringBiometriaModel persistido.

    Raises:
        HTTPException 404: si la sesion no existe.
    """
    # Verificar existencia de la sesion
    sesion = await db.get(ProctoringSessionModel, session_id)
    if sesion is None:
        raise HTTPException(status_code=404, detail=f"Sesion {session_id!r} no encontrada")

    repo = ProctoringRepository(db)
    return await repo.guardar_biometria(
        session_id=session_id,
        liveness_ok=liveness_ok,
        retos_resueltos=retos_resueltos,
        resultado=resultado,
        embedding=embedding,
    )
