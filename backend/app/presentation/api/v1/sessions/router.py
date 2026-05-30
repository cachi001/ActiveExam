"""Router del cierre de sesion (C-13, Flujo 6).

- ``POST /sessions/{id}/finish``: marca la sesion finalizada y dispara la tarea
  asincrona de consolidacion del score (no bloquea al estudiante, RN-SC-04). El
  score final + decision de encolado (flaggeada/archivada) los calcula el worker.

L2.5: el endpoint NUNCA devuelve veredicto ni sancion; solo confirma el cierre.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.presentation.api.v1.sessions.dependencies import build_finalization_service
from app.presentation.api.v1.sessions.schemas import FinishSessionResponse

router = APIRouter()


@router.post("/{session_id}/finish", response_model=FinishSessionResponse)
async def finish_session(request: Request, session_id: str) -> FinishSessionResponse:
    """Cierra la sesion y encola la consolidacion del score (no bloqueante)."""
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Persistencia no inicializada (session_factory).",
        )
    async with factory() as session:
        service = build_finalization_service(request, session)
        try:
            await service.finish(session_id)
            await session.commit()
        except ValueError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
    return FinishSessionResponse(
        session_id=session_id, estado="finalizada", consolidacion_encolada=True
    )
