"""Dependencias del canal de eventos: arma el EventIngestionService (C-10).

Compone el servicio de ingesta sobre una sesion async: repo de Evento (append-only,
hypertable), repo de Sesion (clave de sesion de C-09) y el backplane ganador de
C-03 (seleccionado por ``messaging_backend``). El publisher concreto del backplane
(NOTIFY de asyncpg / PUBLISH de redis) se toma de ``app.state``; sin el, se usa un
publisher no-op que no rompe el arranque (el fan-out real se cablea en deploy).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.events.ingestion import EventIngestionService
from app.infrastructure.messaging.backplane import EventBackplane, build_backplane
from app.infrastructure.persistence.repositories.event import EventSqlRepository
from app.infrastructure.persistence.repositories.transactional import (
    SessionSqlRepository,
)


def get_backplane(request: Request) -> EventBackplane:
    """Construye el backplane ganador de C-03 desde la config + publisher cableado."""
    settings = getattr(request.app.state, "settings", None)
    backend = getattr(settings, "messaging_backend", "postgres") if settings else "postgres"
    publisher = getattr(request.app.state, "backplane_publisher", None)
    if publisher is None:
        # Publisher no-op: el NOTIFY/PUBLISH real se cablea en deploy. No rompe el
        # arranque; el fan-out queda inerte hasta cablear el publisher concreto.
        async def _noop(_canal: str, _evento: dict[str, Any]) -> None:
            return None

        publisher = _noop
    return build_backplane(backend, publisher)


def build_ingestion_service(
    session: AsyncSession, backplane: EventBackplane
) -> EventIngestionService:
    """Arma el ``EventIngestionService`` sobre una sesion async dada."""
    return EventIngestionService(
        eventos=EventSqlRepository(session),
        sesiones=SessionSqlRepository(session),
        backplane=backplane,
    )


async def get_ingestion_service(
    request: Request,
) -> AsyncIterator[EventIngestionService]:
    """Provee el ``EventIngestionService`` ligado a una sesion async por request."""
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Persistencia no inicializada (session_factory).",
        )
    backplane = get_backplane(request)
    async with factory() as session:
        service = build_ingestion_service(session, backplane)
        try:
            yield service
            await session.commit()
        except Exception:
            await session.rollback()
            raise
