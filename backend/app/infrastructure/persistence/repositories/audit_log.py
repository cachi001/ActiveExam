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

import ipaddress

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit_chain import GENESIS_HASH, AuditEntry
from app.domain.repositories.ports import AuditLogRepository
from app.infrastructure.persistence.models.audit_log import AuditLogModel


def _normalizar_ip(raw: str | None) -> str | None:
    """Devuelve `raw` si es una IP (v4/v6) valida; None en cualquier otro caso.

    El origen tipico de este valor es `request.client.host`. Detras de nginx es
    una IP real, pero con el TestClient de FastAPI (host literal 'testclient'),
    un proxy mal configurado o un socket unix puede no ser una IP. La columna
    `ip` es INET: un valor no-IP aborta el INSERT (asyncpg DataError) y tumbaria
    la accion auditada. Preferimos registrar la entrada del audit log con
    ip=NULL antes que perderla (la cadena de custodia igual guarda actor,
    user_agent, accion y proposito).
    """
    if not raw:
        return None
    try:
        ipaddress.ip_address(raw)
    except ValueError:
        return None
    return raw


def _to_domain(m: AuditLogModel) -> AuditEntry:
    return AuditEntry(
        actor=m.actor,
        timestamp=str(m.timestamp),
        ip=str(m.ip) if m.ip is not None else "",
        user_agent=m.user_agent or "",
        accion=m.accion,
        evidencia_id=m.evidencia_id,
        proposito=m.proposito or "",
        modulo=m.modulo,
        entidad=m.entidad,
        entidad_id=m.entidad_id,
        tipo_accion=m.tipo_accion,
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
        #
        # FALLBACK de clasificación: si el caller no seteó `modulo` (muchos
        # construían el AuditEntry directo, dejando modulo=NULL → la entrada no
        # aparecía al filtrar por su módulo en Auditoría), se deriva del prefijo de
        # la acción. `modulo` NO entra en el hash (es metadata de clasificación),
        # así que completarlo acá no afecta la cadena de custodia.
        from app.application.audit.acciones import modulo_de_accion

        modulo = entity.modulo or modulo_de_accion(entity.accion)
        row = AuditLogModel(
            actor=entity.actor,
            ip=_normalizar_ip(entity.ip),
            user_agent=entity.user_agent or None,
            accion=entity.accion,
            modulo=modulo,
            entidad=entity.entidad,
            entidad_id=entity.entidad_id,
            tipo_accion=entity.tipo_accion,
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
