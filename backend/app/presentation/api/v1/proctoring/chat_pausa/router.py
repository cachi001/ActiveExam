"""Router slim de chat bidireccional + pausa autorizada (C-15 tareas 6.x).

Transporte REST + polling (el slim NO monta el WS de eventos). Factory que recibe
``get_db`` inyectado desde el router padre (mismo patron que sessions/events).

Rutas (prefijo final /api/v1/proctoring):
  CHAT
    POST /sessions/{session_id}/chat
    GET  /sessions/{session_id}/chat?desde=<iso?>
  PAUSA
    POST  /sessions/{session_id}/pausas
    GET   /sessions/{session_id}/pausas
    GET   /pausas/pendientes          (poll del proctor — NO colisiona con /sessions/{id})
    PATCH /pausas/{pausa_id}          (aprobar | rechazar)
    PATCH /pausas/{pausa_id}/finalizar
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring import chat_pausa_service
from app.application.proctoring.chat_pausa_service import EstadoInvalido
from app.presentation.api.v1.proctoring.chat_pausa.schemas import (
    MensajeChatIn,
    MensajeChatOut,
    PausaDetalle,
    PausaPendiente,
    PausaResolverIn,
    PausaSolicitudIn,
    PausaSolicitudOut,
)


def create_chat_pausa_router(
    get_db,
    *,
    require_autenticado,
    require_proctor_o_admin,
) -> APIRouter:
    """Factory del router de chat + pausa. Recibe la dependencia de DB inyectada.

    Guards de auth/RBAC (los inyecta el router padre):
      - ``require_autenticado``: chat (alumno y proctor postean), solicitar pausa,
        poll de pausas de la sesion, reanudar (finalizar) pausa — flujo del alumno.
      - ``require_proctor_o_admin``: poll de pausas pendientes y aprobar/rechazar.
    """
    router = APIRouter()

    # ---------------- CHAT ----------------

    @router.post(
        "/sessions/{session_id}/chat",
        status_code=http_status.HTTP_201_CREATED,
        response_model=MensajeChatOut,
        summary="Enviar mensaje de chat (alumno o proctor)",
        dependencies=[Depends(require_autenticado)],
    )
    async def enviar_mensaje(
        session_id: str,
        body: MensajeChatIn,
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> MensajeChatOut:
        """Persiste un mensaje. 404 si la sesion no existe. autor validado por schema."""
        mensaje = await chat_pausa_service.crear_mensaje(
            db, session_id=session_id, autor=body.autor, texto=body.texto
        )
        if mensaje is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )
        return MensajeChatOut(
            id=mensaje.id,
            autor=mensaje.autor,
            texto=mensaje.texto,
            creado_en=mensaje.creado_en,
        )

    @router.get(
        "/sessions/{session_id}/chat",
        response_model=list[MensajeChatOut],
        summary="Listar mensajes de chat (polling incremental con ?desde)",
        dependencies=[Depends(require_autenticado)],
    )
    async def listar_mensajes(
        session_id: str,
        db: Annotated[AsyncSession, Depends(get_db)],
        desde: datetime | None = Query(
            None,
            description="ISO datetime: solo mensajes con creado_en > desde (polling).",
        ),
    ) -> list[MensajeChatOut]:
        """Lista mensajes asc por creado_en. 404 si la sesion no existe."""
        mensajes = await chat_pausa_service.listar_mensajes(db, session_id, desde=desde)
        if mensajes is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )
        return [
            MensajeChatOut(
                id=m.id, autor=m.autor, texto=m.texto, creado_en=m.creado_en
            )
            for m in mensajes
        ]

    # ---------------- PAUSA ----------------

    @router.post(
        "/sessions/{session_id}/pausas",
        status_code=http_status.HTTP_201_CREATED,
        response_model=PausaSolicitudOut,
        summary="Solicitar pausa autorizada (alumno)",
        dependencies=[Depends(require_autenticado)],
    )
    async def solicitar_pausa(
        session_id: str,
        body: PausaSolicitudIn,
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> PausaSolicitudOut:
        """Crea una pausa en estado 'solicitada'. 404 si la sesion no existe."""
        pausa = await chat_pausa_service.solicitar_pausa(
            db, session_id=session_id, motivo=body.motivo
        )
        if pausa is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )
        return PausaSolicitudOut(
            id=pausa.id,
            estado=pausa.estado,
            motivo=pausa.motivo,
            solicitada_en=pausa.solicitada_en,
        )

    @router.get(
        "/sessions/{session_id}/pausas",
        response_model=list[PausaDetalle],
        summary="Listar pausas de la sesion (poll del alumno)",
        dependencies=[Depends(require_autenticado)],
    )
    async def listar_pausas_sesion(
        session_id: str,
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> list[PausaDetalle]:
        """Lista las pausas de la sesion desc por solicitada_en. 404 si no existe."""
        pausas = await chat_pausa_service.listar_pausas_de_sesion(db, session_id)
        if pausas is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )
        return [
            PausaDetalle(
                id=p.id,
                motivo=p.motivo,
                estado=p.estado,
                solicitada_en=p.solicitada_en,
                resuelta_en=p.resuelta_en,
                proctor_actor=p.proctor_actor,
                motivo_rechazo=p.motivo_rechazo,
                inicio_en=p.inicio_en,
                fin_en=p.fin_en,
            )
            for p in pausas
        ]

    @router.get(
        "/pausas/pendientes",
        response_model=list[PausaPendiente],
        summary="Listar pausas pendientes de TODAS las sesiones (poll del proctor)",
        dependencies=[Depends(require_proctor_o_admin)],
    )
    async def listar_pausas_pendientes(
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> list[PausaPendiente]:
        """Pausas en estado 'solicitada' de todas las sesiones, asc por solicitada_en."""
        pendientes = await chat_pausa_service.listar_pausas_pendientes(db)
        return [
            PausaPendiente(
                id=p.id,
                session_id=p.session_id,
                etiqueta=etiqueta,
                motivo=p.motivo,
                solicitada_en=p.solicitada_en,
            )
            for (p, etiqueta) in pendientes
        ]

    @router.patch(
        "/pausas/{pausa_id}",
        response_model=PausaDetalle,
        summary="Resolver pausa (aprobar | rechazar) — proctor",
        dependencies=[Depends(require_proctor_o_admin)],
    )
    async def resolver_pausa(
        pausa_id: str,
        body: PausaResolverIn,
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> PausaDetalle:
        """aprobar abre ventana (inicio_en); rechazar no. 404 si no existe; 409 si no esta 'solicitada'."""
        try:
            pausa = await chat_pausa_service.resolver_pausa(
                db,
                pausa_id,
                accion=body.accion,
                proctor_actor=body.proctor_actor,
                motivo_rechazo=body.motivo_rechazo,
            )
        except EstadoInvalido as exc:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc
        if pausa is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Pausa {pausa_id!r} no encontrada",
            )
        return PausaDetalle(
            id=pausa.id,
            motivo=pausa.motivo,
            estado=pausa.estado,
            solicitada_en=pausa.solicitada_en,
            resuelta_en=pausa.resuelta_en,
            proctor_actor=pausa.proctor_actor,
            motivo_rechazo=pausa.motivo_rechazo,
            inicio_en=pausa.inicio_en,
            fin_en=pausa.fin_en,
        )

    @router.patch(
        "/pausas/{pausa_id}/finalizar",
        response_model=PausaDetalle,
        summary="Finalizar (cerrar ventana de) una pausa aprobada",
        dependencies=[Depends(require_autenticado)],
    )
    async def finalizar_pausa(
        pausa_id: str,
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> PausaDetalle:
        """estado='finalizada', fin_en=now. 404 si no existe; 409 si no esta 'aprobada'."""
        try:
            pausa = await chat_pausa_service.finalizar_pausa(db, pausa_id)
        except EstadoInvalido as exc:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc
        if pausa is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Pausa {pausa_id!r} no encontrada",
            )
        return PausaDetalle(
            id=pausa.id,
            motivo=pausa.motivo,
            estado=pausa.estado,
            solicitada_en=pausa.solicitada_en,
            resuelta_en=pausa.resuelta_en,
            proctor_actor=pausa.proctor_actor,
            motivo_rechazo=pausa.motivo_rechazo,
            inicio_en=pausa.inicio_en,
            fin_en=pausa.fin_en,
        )

    return router
