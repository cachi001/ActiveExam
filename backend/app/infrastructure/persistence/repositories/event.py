"""Adaptador SQLAlchemy del repositorio de Evento (SOLO-APPEND, hypertable).

Implementa ``EventRepository`` (puerto ``AppendOnlyRepository``): los eventos son
inmutables una vez ingeridos; la limpieza la hace la politica de compresion/
retencion de la hypertable, no un update de fila. La VALIDACION de firma HMAC de
produccion es C-10; aqui solo se persiste el Evento con su columna ``firma``.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.event import Evento
from app.domain.repositories.ports import EventRepository
from app.infrastructure.persistence.models.event import EventModel


def _parse_ts_cliente(value: object) -> object:
    """Normaliza ``timestamp_cliente`` (str ISO del cliente) a ``datetime`` aware.

    El cliente manda ``ts_client`` como string ISO (es JSON). La columna es
    ``TIMESTAMP WITH TIME ZONE`` y **asyncpg es estricto**: rechaza un str con
    ``DataError`` (a diferencia de psycopg2, que lo auto-convierte). Sin esta
    conversión, TODA ingesta de eventos por asyncpg falla. Acepta el sufijo 'Z'.
    """
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def _to_domain(m: EventModel) -> Evento:
    return Evento(
        id=str(m.id),
        session_id=m.session_id,
        exam_id=m.exam_id,
        tipo=m.tipo,
        severidad=m.severidad,
        timestamp_cliente=str(m.timestamp_cliente),
        timestamp_backend=str(m.timestamp_backend),
        payload=dict(m.payload or {}),
        firma=m.firma,
        schema_version=m.schema_version,
    )


class EventSqlRepository(EventRepository):
    """Repositorio append-only de Evento sobre la hypertable TimescaleDB."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, entity: Evento) -> Evento:
        row = EventModel(
            session_id=entity.session_id,
            exam_id=entity.exam_id,
            tipo=entity.tipo,
            severidad=entity.severidad,
            timestamp_cliente=_parse_ts_cliente(entity.timestamp_cliente),
            payload=entity.payload,
            firma=entity.firma,
            schema_version=entity.schema_version,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_domain(row)

    async def get(self, entity_id: str) -> Evento | None:
        result = await self._session.execute(
            select(EventModel).where(EventModel.id == int(entity_id))
        )
        row = result.scalar_one_or_none()
        return _to_domain(row) if row is not None else None

    async def list(self) -> list[Evento]:
        result = await self._session.execute(
            select(EventModel).order_by(EventModel.timestamp.asc())
        )
        return [_to_domain(r) for r in result.scalars().all()]

    async def posteriores_a(
        self, *, session_id: str, last_event_id: str | None
    ) -> list[Evento]:
        """Eventos de la sesion posteriores a ``last_event_id`` (gancho C-14, C-10 4.4).

        Resuelve por el indice ``(session_id, timestamp)`` (ix_evento_session_ts):
        filtra por sesion y ``id > last_event_id`` (orden monotono del BigInteger de
        ingesta), devolviendo los faltantes en orden. Si ``last_event_id`` es None,
        devuelve todos los de la sesion. La replay/dedup completa la construye C-14;
        aqui se deja la consulta ordenada que la habilita."""
        stmt = select(EventModel).where(EventModel.session_id == session_id)
        if last_event_id is not None:
            stmt = stmt.where(EventModel.id > int(last_event_id))
        stmt = stmt.order_by(EventModel.id.asc())
        result = await self._session.execute(stmt)
        return [_to_domain(r) for r in result.scalars().all()]
