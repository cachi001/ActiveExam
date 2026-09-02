"""Router activeexam de chat bidireccional + pausa autorizada (C-15 tareas 6.x).

Transporte REST + polling (el activeexam NO monta el WS de eventos). Factory que recibe
``get_db`` inyectado desde el router padre (mismo patron que sessions/events).

Rutas (prefijo final /api/v1/proctoring):
  CHAT
    POST /sessions/{session_id}/chat
    GET  /sessions/{session_id}/chat?desde=<iso?>
  PAUSA
    POST  /sessions/{session_id}/pausas
    GET   /sessions/{session_id}/pausas
    GET   /pausas/pendientes          (poll del tutor/coordinador — NO colisiona con /sessions/{id})
    PATCH /pausas/{pausa_id}          (aprobar | rechazar)
    PATCH /pausas/{pausa_id}/finalizar
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.config.service import ConfigService
from app.application.proctoring import chat_pausa_service, session_service
from app.application.proctoring.scoring import (
    chat_habilitado_de_snapshot,
    pausas_habilitadas_de_snapshot,
)
from app.application.proctoring.chat_pausa_service import (
    AlumnoNoPuedeIniciarError,
    EstadoInvalido,
    LimitePausasExcedido,
)
from app.domain.auth.authorization import (
    autorizar_dueno_o_supervision_vivo_sobre_sesion,
    autorizar_supervision_vivo_sobre_sesion,
    principal_es_dueno_de_sesion,
)
from app.domain.auth.errors import ForbiddenError
from app.domain.auth.identity import AuthenticatedPrincipal
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
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
    require_supervision_vivo,
    config_service: ConfigService | None = None,
) -> APIRouter:
    """Factory del router de chat + pausa. Recibe la dependencia de DB inyectada.

    Guards de auth/RBAC (los inyecta el router padre):
      - ``require_autenticado``: chat (alumno y tutor postean), solicitar pausa,
        poll de pausas de la sesion, reanudar (finalizar) pausa — flujo del alumno.
      - ``require_supervision_vivo``: poll de pausas pendientes y aprobar/rechazar.
    """
    router = APIRouter()

    # ---------------- CHAT ----------------

    async def _sesion_o_404(
        db: AsyncSession, session_id: str
    ) -> ProctoringSessionModel:
        sesion = await session_service.obtener_sesion_ligera(db, session_id)
        if sesion is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )
        return sesion

    async def _config_viva() -> tuple[bool, bool]:
        """(chat_habilitado, pausas_habilitadas) de la config VIVA.

        Solo para sesiones cuya foto no trae los interruptores (creadas antes de
        c-78). Sin `config_service` no se puede decidir: se deja pasar, que es el
        comportamiento previo — nunca cerrar una funcionalidad por no poder leer.
        """
        if config_service is None:
            return (True, True)
        efectiva = await config_service.get_efectiva()
        return (bool(efectiva.chat_habilitado), bool(efectiva.pausas_habilitadas))

    async def _exigir_habilitado(
        sesion: ProctoringSessionModel, *, funcionalidad: str
    ) -> None:
        """403 si la funcionalidad esta apagada PARA ESTA SESION.

        c-78: hasta ahora `chat_habilitado`/`pausas_habilitadas` eran SOLO visuales
        — `Examen.tsx` escondia el recuadro y ningun endpoint los consultaba, asi
        que apagarlos no apagaba nada. Rompia la regla dura #6 (el cliente no es
        confiable: la regla la hace valer el backend).

        El valor sale del `config_snapshot` de la sesion, NO de la config viva: el
        examen corre contra la foto que se tomo al crearlo, y un cambio de config a
        mitad de una rendicion no puede alterarla (es lo que el snapshot existe para
        impedir). Las sesiones sin ese dato en su foto caen a la config viva.
        """
        chat_vivo, pausas_vivo = await _config_viva()
        if funcionalidad == "chat":
            habilitado = chat_habilitado_de_snapshot(sesion.config_snapshot, vivo=chat_vivo)
            detalle = "El chat con el tutor no está habilitado para este examen."
        else:
            habilitado = pausas_habilitadas_de_snapshot(
                sesion.config_snapshot, vivo=pausas_vivo
            )
            detalle = "Las pausas autorizadas no están habilitadas para este examen."
        if not habilitado:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN, detail=detalle
            )

    async def _tiene_pertenencia(
        db: AsyncSession, principal: AuthenticatedPrincipal, session_id: str
    ) -> bool:
        """Pertenencia del principal sobre la sesión (tutor de su comisión, o
        coordinador de su materia) — c-79, N:M."""
        from app.domain.auth.roles import Rol

        return await session_service.tiene_pertenencia_de_sesion(
            db,
            principal.subject or "",
            session_id,
            es_coordinador=principal.tiene_rol(Rol.COORDINADOR),
        )

    @router.post(
        "/sessions/{session_id}/chat",
        status_code=http_status.HTTP_201_CREATED,
        response_model=MensajeChatOut,
        summary="Enviar mensaje de chat (alumno o tutor)",
    )
    async def enviar_mensaje(
        session_id: str,
        body: MensajeChatIn,
        db: Annotated[AsyncSession, Depends(get_db)],
        principal: Annotated[AuthenticatedPrincipal, Depends(require_autenticado)],
    ) -> MensajeChatOut:
        """Persiste un mensaje. 404 si la sesion no existe. 403 si el alumno intenta
        iniciar el hilo (D4: solo responde si el tutor ya escribio). autor validado
        por schema (alumno | tutor).

        H1 (IDOR, pentest): antes cualquier token valido bastaba para escribir en
        CUALQUIER sesion. Ahora, si ``autor='alumno'`` exige que la sesion sea del
        principal; si ``autor='tutor'`` exige supervision en vivo sobre ESA sesion
        puntual (no alcanza con tener el rol tutor en general)."""
        sesion = await _sesion_o_404(db, session_id)
        # c-78: el interruptor vale server-side. Antes era solo visual.
        await _exigir_habilitado(sesion, funcionalidad="chat")
        if body.autor == "alumno":
            if not principal_es_dueno_de_sesion(
                principal, sesion.alumno_idnumber, sesion.alumno_email
            ):
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail="La sesion pertenece a otro alumno.",
                )
        else:  # autor == "tutor" (unico otro valor valido por schema)
            tiene_pertenencia = await _tiene_pertenencia(db, principal, session_id)
            try:
                autorizar_supervision_vivo_sobre_sesion(principal, tiene_pertenencia)
            except ForbiddenError as exc:
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail={"error": "sesion_ajena", "mensaje": str(exc)},
                ) from exc
        try:
            mensaje = await chat_pausa_service.crear_mensaje(
                db, session_id=session_id, autor=body.autor, texto=body.texto
            )
        except AlumnoNoPuedeIniciarError as exc:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN, detail=str(exc)
            ) from exc
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
    )
    async def listar_mensajes(
        session_id: str,
        db: Annotated[AsyncSession, Depends(get_db)],
        principal: Annotated[AuthenticatedPrincipal, Depends(require_autenticado)],
        desde: datetime | None = Query(
            None,
            description="ISO datetime: solo mensajes con creado_en > desde (polling).",
        ),
    ) -> list[MensajeChatOut]:
        """Lista mensajes asc por creado_en. 404 si la sesion no existe.

        H1 (IDOR): exige que el principal sea el dueño de la sesion O tenga
        supervision en vivo sobre ella — antes cualquier alumno autenticado
        podia leer el chat privado de la sesion de otro alumno."""
        sesion = await _sesion_o_404(db, session_id)
        tiene_pertenencia = await _tiene_pertenencia(db, principal, session_id)
        try:
            autorizar_dueno_o_supervision_vivo_sobre_sesion(
                principal, sesion.alumno_idnumber, sesion.alumno_email, tiene_pertenencia
            )
        except ForbiddenError as exc:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail={"error": "sesion_ajena", "mensaje": str(exc)},
            ) from exc
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
    )
    async def solicitar_pausa(
        session_id: str,
        body: PausaSolicitudIn,
        db: Annotated[AsyncSession, Depends(get_db)],
        principal: Annotated[AuthenticatedPrincipal, Depends(require_autenticado)],
    ) -> PausaSolicitudOut:
        """Crea una pausa en estado 'solicitada'. 404 si la sesion no existe.

        H1 (IDOR): solo el dueño de la sesion puede solicitar la pausa de SU
        propio examen — antes cualquier alumno autenticado podia solicitar
        pausas en la sesion de otro."""
        sesion = await _sesion_o_404(db, session_id)
        # c-78: el interruptor vale server-side. Antes era solo visual.
        # NO se cierra la FINALIZACION de una pausa ya activa: apagar el
        # interruptor no puede dejar a un alumno pausado para siempre.
        await _exigir_habilitado(sesion, funcionalidad="pausas")
        if not principal_es_dueno_de_sesion(
            principal, sesion.alumno_idnumber, sesion.alumno_email
        ):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="La sesion pertenece a otro alumno.",
            )
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
        summary="Listar pausas de la sesion (poll del alumno o de quien supervisa)",
    )
    async def listar_pausas_sesion(
        session_id: str,
        db: Annotated[AsyncSession, Depends(get_db)],
        principal: Annotated[AuthenticatedPrincipal, Depends(require_autenticado)],
    ) -> list[PausaDetalle]:
        """Lista las pausas de la sesion desc por solicitada_en. 404 si no existe.

        H1 (IDOR): exige que el principal sea el dueño de la sesion O tenga
        supervision en vivo sobre ella."""
        sesion = await _sesion_o_404(db, session_id)
        tiene_pertenencia = await _tiene_pertenencia(db, principal, session_id)
        try:
            autorizar_dueno_o_supervision_vivo_sobre_sesion(
                principal, sesion.alumno_idnumber, sesion.alumno_email, tiene_pertenencia
            )
        except ForbiddenError as exc:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail={"error": "sesion_ajena", "mensaje": str(exc)},
            ) from exc
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
                tutor_actor=p.tutor_actor,
                motivo_rechazo=p.motivo_rechazo,
                inicio_en=p.inicio_en,
                fin_en=p.fin_en,
            )
            for p in pausas
        ]

    @router.get(
        "/pausas/pendientes",
        response_model=list[PausaPendiente],
        summary="Listar pausas pendientes de TODAS las sesiones (poll del tutor/coordinador)",
        dependencies=[Depends(require_supervision_vivo)],
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
                alumno_nombre=alumno_nombre,
                motivo=p.motivo,
                solicitada_en=p.solicitada_en,
            )
            for (p, etiqueta, alumno_nombre) in pendientes
        ]

    @router.patch(
        "/pausas/{pausa_id}",
        response_model=PausaDetalle,
        summary="Resolver pausa (aprobar | rechazar) — capacidad `supervisar_sesion`",
    )
    async def resolver_pausa(
        pausa_id: str,
        body: PausaResolverIn,
        db: Annotated[AsyncSession, Depends(get_db)],
        principal: Annotated[AuthenticatedPrincipal, Depends(require_supervision_vivo)],
    ) -> PausaDetalle:
        """aprobar abre ventana (inicio_en); rechazar no. 404 si no existe; 403 si el
        tutor no es el docente a cargo de la comision de esa sesion (C-76 bloque 6.3/8,
        D2); 409 si no esta 'solicitada' o si la sesion ya alcanzo el limite de
        pausas (C-76 bloque 4, umbral configurable ``pausas_max_por_sesion``,
        default 2)."""
        pausa_existente = await chat_pausa_service.obtener_pausa(db, pausa_id)
        if pausa_existente is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Pausa {pausa_id!r} no encontrada",
            )
        tiene_pertenencia = await _tiene_pertenencia(db, principal, pausa_existente.session_id)
        try:
            autorizar_supervision_vivo_sobre_sesion(principal, tiene_pertenencia)
        except ForbiddenError as exc:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail={"error": "sesion_ajena", "mensaje": str(exc)},
            ) from exc
        limite_pausas: int | None = None
        if body.accion == "aprobar" and config_service is not None:
            efectiva = await config_service.get_efectiva()
            limite_pausas = efectiva.pausas_max_por_sesion
        try:
            pausa = await chat_pausa_service.resolver_pausa(
                db,
                pausa_id,
                accion=body.accion,
                tutor_actor=body.tutor_actor,
                motivo_rechazo=body.motivo_rechazo,
                limite_pausas=limite_pausas,
            )
        except LimitePausasExcedido as exc:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc
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
            tutor_actor=pausa.tutor_actor,
            motivo_rechazo=pausa.motivo_rechazo,
            inicio_en=pausa.inicio_en,
            fin_en=pausa.fin_en,
        )

    @router.patch(
        "/pausas/{pausa_id}/finalizar",
        response_model=PausaDetalle,
        summary="Finalizar (cerrar ventana de) una pausa aprobada",
    )
    async def finalizar_pausa(
        pausa_id: str,
        db: Annotated[AsyncSession, Depends(get_db)],
        principal: Annotated[AuthenticatedPrincipal, Depends(require_autenticado)],
    ) -> PausaDetalle:
        """estado='finalizada', fin_en=now. 404 si no existe; 409 si no esta 'aprobada'.

        H1 (IDOR): solo el alumno dueño de la sesion de esa pausa puede
        finalizarla (reanudar su propio examen) — antes cualquier token valido
        alcanzaba para cerrar la pausa de la sesion de otro alumno."""
        pausa_existente = await chat_pausa_service.obtener_pausa(db, pausa_id)
        if pausa_existente is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Pausa {pausa_id!r} no encontrada",
            )
        sesion = await _sesion_o_404(db, pausa_existente.session_id)
        if not principal_es_dueno_de_sesion(
            principal, sesion.alumno_idnumber, sesion.alumno_email
        ):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="La pausa pertenece a la sesion de otro alumno.",
            )
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
            tutor_actor=pausa.tutor_actor,
            motivo_rechazo=pausa.motivo_rechazo,
            inicio_en=pausa.inicio_en,
            fin_en=pausa.fin_en,
        )

    return router
