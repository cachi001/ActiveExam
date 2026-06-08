"""Dependencias del consentimiento: arma el ConsentService por request (C-08).

Abre una sesion async (``app.state.session_factory``), arma el repositorio de
``Consentimiento`` (sin update/delete), el del audit log (append-only) y el adaptador
de cola (``app.state.message_queue``), y compone el ``ConsentService``. Commit al
cerrar; rollback ante error. Sin DB cableada -> 500 explicito.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import HTTPException, Request, status

from app.application.consent.service import ConsentService
from app.infrastructure.persistence.repositories.alternative_request import (
    AlternativeRequestSqlRepository,
)
from app.infrastructure.persistence.repositories.audit_log import AuditLogSqlRepository
from app.infrastructure.persistence.repositories.consent import ConsentSqlRepository


async def get_consent_service(request: Request) -> AsyncIterator[ConsentService]:
    """Provee el ``ConsentService`` ligado a una sesion async por request.

    C-63: inyecta el ``AlternativeRequestRepository`` si la tabla esta disponible
    (modulo slim con migracion 0010 aplicada). Si el app.state no tiene la tabla,
    el repositorio es None y el servicio opera en modo legacy (sin estado mutable).
    En la practica, en el slim la tabla SIEMPRE existe tras la migracion 0010.
    """
    factory = getattr(request.app.state, "session_factory", None)
    queue = getattr(request.app.state, "message_queue", None)
    if factory is None or queue is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Consentimiento no inicializado (persistencia/cola).",
        )
    async with factory() as session:
        service = ConsentService(
            ConsentSqlRepository(session),
            AuditLogSqlRepository(session),
            queue,
            AlternativeRequestSqlRepository(session),
        )
        try:
            yield service
            await session.commit()
        except Exception:
            await session.rollback()
            raise
