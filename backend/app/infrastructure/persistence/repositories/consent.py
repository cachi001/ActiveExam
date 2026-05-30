"""Adaptador SQLAlchemy del repositorio de Consentimiento (INMUTABLE, D5).

Implementa ``ConsentRepository``, que hereda solo ``add``/``get``/``list`` de
``Repository`` -> NO expone ``update``. La inmutabilidad se refuerza ademas con el
trigger anti-UPDATE/DELETE de la migracion 002.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.consent import Consentimiento
from app.domain.repositories.ports import ConsentRepository
from app.infrastructure.persistence.models.transactional import ConsentimientoModel


def _to_domain(m: ConsentimientoModel) -> Consentimiento:
    return Consentimiento(
        id=m.id,
        user_id=m.user_id,
        exam_id=m.exam_id,
        version_texto=m.version_texto,
        timestamp=str(m.timestamp),
        hash=m.hash,
    )


class ConsentSqlRepository(ConsentRepository):
    """Repositorio de Consentimiento sin operacion de modificacion (D5)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entity: Consentimiento) -> Consentimiento:
        row = ConsentimientoModel(
            user_id=entity.user_id,
            exam_id=entity.exam_id,
            version_texto=entity.version_texto,
            hash=entity.hash,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_domain(row)

    async def get(self, entity_id: str) -> Consentimiento | None:
        row = await self._session.get(ConsentimientoModel, entity_id)
        return _to_domain(row) if row is not None else None

    async def list(self) -> list[Consentimiento]:
        result = await self._session.execute(select(ConsentimientoModel))
        return [_to_domain(r) for r in result.scalars().all()]
