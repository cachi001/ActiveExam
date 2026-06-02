"""Router de ingestión de eventos de proctoring slim.

POST /sessions/{id}/events → 201/404

Sin auth (D7 — alcance demo). Inyecta el adapter ReinferenciaPort via Depends
para mantener el desacople puerto/adapter (DD-17).

L2.5: la respuesta incluye el veredicto 'coincide'/'discrepancia'/'no_evaluado'
pero NUNCA sanciona — es informacion para el revisor humano.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring import event_service
from app.application.proctoring.reinferencia import ReinferenciaPort
from app.presentation.api.v1.proctoring.events.schemas import (
    IngestEventoIn,
    IngestEventoOut,
)


def create_events_router(get_db, get_reinferencia) -> APIRouter:
    """Factory del router de eventos. Recibe dependencias de DB y re-inferencia."""
    router = APIRouter()

    @router.post(
        "/sessions/{session_id}/events",
        status_code=http_status.HTTP_201_CREATED,
        response_model=IngestEventoOut,
        summary="Ingestar evento de deteccion con re-inferencia server-side",
    )
    async def ingestar_evento(
        session_id: str,
        body: IngestEventoIn,
        db: Annotated[AsyncSession, Depends(get_db)],
        reinferencia: Annotated[ReinferenciaPort, Depends(get_reinferencia)],
    ) -> IngestEventoOut:
        """Ingesta un evento de deteccion.

        Re-detecta rostros con MediaPipe server-side (mismo motor que el cliente),
        calcula SHA-256 del screenshot y persiste todo en proctoring_event.

        Responde con el veredicto de re-inferencia para que el frontend pueda
        mostrar alertas en tiempo real de discrepancias.

        L2.5: 'discrepancia' solo enriquece la evidencia — no sanciona.
        """
        evento = await event_service.ingestar_evento(
            db=db,
            session_id=session_id,
            tipo=body.tipo,
            severidad=body.severidad.value,
            ts_cliente=body.ts_cliente,
            reinferencia=reinferencia,
            payload=body.payload,
            screenshot_base64=body.screenshot_base64,
            face_count_cliente=body.face_count_cliente,
        )
        return IngestEventoOut(
            evento_id=evento.id,
            veredicto_reinferencia=evento.veredicto_reinferencia,
            face_count_servidor=evento.face_count_servidor,
            screenshot_sha256=evento.screenshot_sha256,
        )

    return router
