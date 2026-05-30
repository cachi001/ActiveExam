"""Adaptador SQLAlchemy del repositorio del Audit log (SOLO-APPEND, D1+D2).

Implementa ``AuditLogRepository`` (puerto ``AppendOnlyRepository``): expone solo
``append``/``get``/``list`` (sin update/delete) -> coherente con el trigger de la
base que rechaza UPDATE/DELETE. ``hash_prev`` y ``hash_self`` los calcula el
trigger ``trg_audit_log_encadenar`` al INSERT (la cadena la construye el motor,
no la aplicacion), de modo que el encadenamiento es la fuente de verdad.

``verificar_cadena`` lee las entradas en orden y valida que el ``hash_prev`` de
cada una coincida con el ``hash_self`` de la anterior (validacion diaria, `04`).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit_chain import GENESIS_HASH, AuditEntry
from app.domain.repositories.ports import AuditLogRepository
from app.infrastructure.persistence.models.audit_log import AuditLogModel


def _to_domain(m: AuditLogModel) -> AuditEntry:
    return AuditEntry(
        actor=m.actor,
        timestamp=str(m.timestamp),
        ip=str(m.ip) if m.ip is not None else "",
        user_agent=m.user_agent or "",
        accion=m.accion,
        evidencia_id=m.evidencia_id,
        proposito=m.proposito or "",
        hash_prev=m.hash_prev,
    )


class AuditLogSqlRepository(AuditLogRepository):
    """Repositorio append-only del audit log. El hash lo encadena el motor."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, entity: AuditEntry) -> AuditEntry:
        # hash_prev/hash_self los completa el trigger BEFORE INSERT (002); aqui
        # no se calcula la cadena en la aplicacion para que la fuente de verdad
        # sea el motor.
        row = AuditLogModel(
            actor=entity.actor,
            ip=entity.ip or None,
            user_agent=entity.user_agent or None,
            accion=entity.accion,
            evidencia_id=entity.evidencia_id,
            proposito=entity.proposito or None,
            hash_prev="",  # placeholder; el trigger lo sobreescribe
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_domain(row)

    async def get(self, entity_id: str) -> AuditEntry | None:
        row = await self._session.get(AuditLogModel, entity_id)
        return _to_domain(row) if row is not None else None

    async def list(self) -> list[AuditEntry]:
        result = await self._session.execute(
            select(AuditLogModel).order_by(
                AuditLogModel.timestamp.asc(), AuditLogModel.id.asc()
            )
        )
        return [_to_domain(r) for r in result.scalars().all()]

    async def verificar_cadena(self) -> bool:
        """Verifica el encadenamiento extremo a extremo usando los hashes que
        materializo el motor: hash_prev[n] == hash_self[n-1] (y el primero == genesis)."""
        result = await self._session.execute(
            select(AuditLogModel.hash_prev, AuditLogModel.hash_self).order_by(
                AuditLogModel.timestamp.asc(), AuditLogModel.id.asc()
            )
        )
        prev = GENESIS_HASH
        for hash_prev, hash_self in result.all():
            if hash_prev != prev:
                return False
            prev = hash_self
        return True
