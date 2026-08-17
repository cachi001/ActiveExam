"""Servicio de aplicacion activeexam para observaciones del tutor (C-15 tarea 3.2).

Sin Keycloak/Vault/MinIO. Persistencia contra la DB real (sin mocks, regla dura).

INSUMO DE C-16: el tutor registra observaciones libres sobre una sesion durante
la supervision. Son MULTIPLES por sesion y append-only (nunca se borran/mutan): la
revision humana de C-16 las consume como contexto. L2.5 (regla #5): una observacion
NO sanciona ni exime — es insumo para la decision HUMANA.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.observacion import ObservacionTutorModel
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel


async def _sesion_existe(db: AsyncSession, session_id: str) -> bool:
    result = await db.execute(
        select(ProctoringSessionModel.id).where(
            ProctoringSessionModel.id == session_id
        )
    )
    return result.scalar_one_or_none() is not None


async def crear_observacion(
    db: AsyncSession,
    session_id: str,
    texto: str,
    tutor_actor: str | None = None,
) -> ObservacionTutorModel | None:
    """Persiste una observacion del tutor. None si la sesion no existe."""
    if not await _sesion_existe(db, session_id):
        return None
    obs = ObservacionTutorModel(
        session_id=session_id, texto=texto, tutor_actor=tutor_actor
    )
    db.add(obs)
    await db.commit()
    await db.refresh(obs)
    return obs


async def listar_observaciones(
    db: AsyncSession, session_id: str
) -> list[ObservacionTutorModel] | None:
    """Lista las observaciones de la sesion (asc por creada_en). None si no existe."""
    if not await _sesion_existe(db, session_id):
        return None
    stmt = (
        select(ObservacionTutorModel)
        .where(ObservacionTutorModel.session_id == session_id)
        .order_by(ObservacionTutorModel.creada_en.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
