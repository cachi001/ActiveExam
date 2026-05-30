"""Router del canal WebSocket del estudiante + consulta de replay (C-10).

- ``WS /ws``: canal bidireccional del estudiante (DD-16). Handshake con
  ``session_id`` + ``access_token`` (JWT) + ``last_event_id``; el JWT se valida
  contra el JWKS (C-06). Loop: recibe eventos/heartbeats, los ingesta (valida firma
  server-side, persiste, fan-out) y responde un ack; puede emitir comandos.
- ``GET /replay``: eventos posteriores a ``last_event_id`` por sesion (gancho C-14).

El WebSocket bidireccional del estudiante es FIJO (DD-16); el transporte del panel y
el backplane los decide C-03 (detras de puerto). L2.5: solo transporta/persiste.
"""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from app.domain.auth.errors import UnauthenticatedError
from app.presentation.api.v1.auth.realtime import (
    authenticate_handshake,
    extract_token_from_query,
)
from app.presentation.api.v1.events.channel import Handshake, StudentChannelSession
from app.presentation.api.v1.events.dependencies import (
    build_ingestion_service,
    get_backplane,
)
from app.infrastructure.persistence.repositories.event import EventSqlRepository

router = APIRouter()


@router.websocket("/ws")
async def student_channel(websocket: WebSocket) -> None:
    """Canal WS bidireccional del estudiante: handshake autenticado + loop (DD-16)."""
    app = websocket.app
    validator = getattr(app.state, "jwt_validator", None)
    factory = getattr(app.state, "session_factory", None)
    if validator is None or factory is None:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    # --- Handshake: session_id + JWT + last_event_id (RN-AU-03) --------------
    qp = dict(websocket.query_params)
    token = extract_token_from_query(qp)
    try:
        authenticate_handshake(validator, token)  # 401 logico si invalido/ausente
    except UnauthenticatedError:
        # JWT invalido o ausente -> se rechaza el handshake (no se abre el canal).
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    session_id = qp.get("session_id")
    if not session_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    handshake = Handshake(
        session_id=session_id, jwt=token or "", last_event_id=qp.get("last_event_id")
    )

    await websocket.accept()

    async def _send_command(comando: dict) -> None:
        await websocket.send_json(comando)

    backplane = get_backplane(_RequestShim(app))
    async with factory() as session:
        ingestion = build_ingestion_service(session, backplane)
        canal = StudentChannelSession(
            handshake=handshake, ingestion=ingestion, send_command=_send_command
        )
        try:
            while True:
                mensaje = await websocket.receive_json()
                ack = await canal.on_message(mensaje)
                await session.commit()
                await websocket.send_json(ack)
        except WebSocketDisconnect:
            return
        except Exception:
            await session.rollback()
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            return


@router.get("/replay")
async def replay_events(
    request: Request,
    session_id: str = Query(...),
    last_event_id: str | None = Query(default=None),
) -> dict:
    """Eventos posteriores a ``last_event_id`` por sesion (gancho C-14, C-10 4.4)."""
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Persistencia no inicializada (session_factory).",
        )
    async with factory() as session:
        repo = EventSqlRepository(session)
        eventos = await repo.posteriores_a(
            session_id=session_id, last_event_id=last_event_id
        )
        return {
            "session_id": session_id,
            "last_event_id": last_event_id,
            "eventos": [
                {
                    "id": e.id,
                    "tipo": e.tipo,
                    "severidad": e.severidad,
                    "ts_backend": e.timestamp_backend,
                }
                for e in eventos
            ],
        }


class _RequestShim:
    """Shim minimo para reusar ``get_backplane`` (que espera ``request.app``)."""

    def __init__(self, app) -> None:
        self.app = app
