"""Router de sesiones de proctoring slim.

POST /sessions → 201
GET  /sessions → 200
GET  /sessions/{id} → 200/404

Sin auth (D7 — alcance demo). La session_factory y el db_dependency se
inyectan desde el router padre para evitar acoplar este router a SlimSettings.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring import observacion_service, session_service
from app.application.proctoring.scoring import (
    calcular_score,
    eventos_en_pausa_autorizada,
)
from app.presentation.api.v1.proctoring.sessions.schemas import (
    BiometriaDetalle,
    CerrarForzadoIn,
    CerrarForzadoOut,
    CrearSesionIn,
    CrearSesionOut,
    EventoDetalle,
    FinalizarSesionOut,
    ObservacionIn,
    ObservacionOut,
    SesionDetalle,
    SesionResumen,
)


async def _pesos_vivos_por_tipo(db: AsyncSession) -> dict[str, int] | None:
    """Lee los pesos vivos por tipo de evento desde evento_score_config (activos).

    Devuelve None si la tabla no esta disponible (degradacion graceful, RN-GLB-03):
    en ese caso calcular_score cae al fallback por severidad. Cierra GAP #1
    (consumo server-side de la config, no constantes hardcodeadas)."""
    from sqlalchemy import select

    from app.infrastructure.persistence.models.transactional import (
        EventoScoreConfigModel,
    )

    try:
        result = await db.execute(
            select(
                EventoScoreConfigModel.tipo_evento,
                EventoScoreConfigModel.peso,
            ).where(EventoScoreConfigModel.activo.is_(True))
        )
        return {row.tipo_evento: row.peso for row in result.all()}
    except Exception:  # noqa: BLE001 — degradacion: sin config, fallback por severidad
        return None


async def _ventanas_pausa_aprobada(db: AsyncSession, session_id: str) -> list:
    """Ventanas de pausa APROBADA de la sesion (estados 'aprobada' y 'finalizada').

    Devuelve filas con estado/inicio_en/fin_en que el helper puro
    ``eventos_en_pausa_autorizada`` usa para contextualizar el score (C-15 6.4).
    Si la tabla no esta disponible (degradacion graceful) devuelve lista vacia:
    el score se calcula sin exclusiones."""
    from sqlalchemy import select

    from app.infrastructure.persistence.models.chat_pausa import PausaAutorizadaModel

    try:
        result = await db.execute(
            select(PausaAutorizadaModel).where(
                PausaAutorizadaModel.session_id == session_id,
                PausaAutorizadaModel.estado.in_(("aprobada", "finalizada")),
            )
        )
        return list(result.scalars().all())
    except Exception:  # noqa: BLE001 — sin tabla de pausas, no se excluye nada
        return []


def create_sessions_router(
    get_db,
    *,
    require_autenticado,
    require_proctor_o_admin,
    require_admin,
) -> APIRouter:
    """Factory del router de sesiones. Recibe la dependencia de DB inyectada.

    Guards de auth/RBAC (endurecimiento por rol — los inyecta el router padre):
      - ``require_autenticado``: cualquier token valido (flujo del alumno).
      - ``require_proctor_o_admin``: vista del proctor (lista/detalle de sesiones).
      - ``require_admin``: operaciones de cadena de custodia (DELETE — JAMAS proctor).
    """
    router = APIRouter()

    @router.post(
        "/sessions",
        status_code=http_status.HTTP_201_CREATED,
        response_model=CrearSesionOut,
        summary="Crear sesion de proctoring",
        dependencies=[Depends(require_autenticado)],
    )
    async def crear_sesion(
        body: CrearSesionIn,
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> CrearSesionOut:
        """Crea una nueva sesion de proctoring slim."""
        sesion = await session_service.crear_sesion(
            db=db,
            modo=body.modo,
            exam_id=body.exam_id,
            etiqueta=body.etiqueta,
        )
        return CrearSesionOut(id=sesion.id, creada_en=sesion.creada_en)

    @router.get(
        "/sessions",
        response_model=list[SesionResumen],
        summary="Listar sesiones con score y discrepancias",
        dependencies=[Depends(require_proctor_o_admin)],
    )
    async def listar_sesiones(
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> list[SesionResumen]:
        """Lista todas las sesiones con total_eventos, total_discrepancias y score."""
        sesiones = await session_service.listar_sesiones(db)
        return [
            SesionResumen(
                id=s.id,
                modo=s.modo,
                exam_id=s.exam_id,
                etiqueta=s.etiqueta,
                creada_en=s.creada_en,
                finalizada_en=s.finalizada_en,
                ultimo_evento_en=s.ultimo_evento_en,
                total_eventos=s.total_eventos,
                total_discrepancias=s.total_discrepancias,
                score=s.score,
            )
            for s in sesiones
        ]

    @router.get(
        "/sessions/{session_id}",
        response_model=SesionDetalle,
        summary="Detalle de sesion para revision del proctor",
        dependencies=[Depends(require_proctor_o_admin)],
    )
    async def obtener_sesion(
        session_id: str,
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> SesionDetalle:
        """Detalle completo de una sesion con eventos y biometria (vista del proctor)."""
        sesion = await session_service.detalle_sesion(db, session_id)
        if sesion is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )

        # Pesos VIVOS por tipo de evento desde la config persistida
        # (evento_score_config). Si la config no esta disponible, calcular_score
        # cae al fallback por severidad (degradacion graceful, RN-GLB-03). L2.5:
        # el score solo prioriza la revision humana.
        pesos_por_tipo = await _pesos_vivos_por_tipo(db)

        # C-15 (6.4): contextualizacion del score. Los eventos que caen dentro de
        # una ventana de pausa AUTORIZADA (aprobada/finalizada) se EXCLUYEN del
        # puntaje (L2.5: no se borran ni se ocultan, solo se marcan). El detalle
        # del proctor reporta el score SIN esos eventos.
        ventanas = await _ventanas_pausa_aprobada(db, session_id)
        ids_en_pausa = eventos_en_pausa_autorizada(sesion.eventos, ventanas)
        eventos_para_score = [
            e for e in sesion.eventos if e.id not in ids_en_pausa
        ]
        score = calcular_score(eventos_para_score, pesos_por_tipo=pesos_por_tipo)

        eventos = [
            EventoDetalle(
                id=e.id,
                tipo=e.tipo,
                severidad=e.severidad,
                ts_cliente=e.ts_cliente,
                ts_backend=e.ts_backend,
                payload=e.payload,
                screenshot_base64=e.screenshot_b64,
                screenshot_sha256=e.screenshot_sha256,
                face_count_cliente=e.face_count_cliente,
                face_count_servidor=e.face_count_servidor,
                veredicto_reinferencia=e.veredicto_reinferencia,
                en_pausa_autorizada=e.id in ids_en_pausa,
            )
            for e in sesion.eventos
        ]

        biometria = None
        if sesion.biometria is not None:
            bio = sesion.biometria
            biometria = BiometriaDetalle(
                liveness_ok=bio.liveness_ok,
                retos_resueltos=bio.retos_resueltos,
                resultado=bio.resultado,
                registrada_en=bio.registrada_en,
            )

        return SesionDetalle(
            id=sesion.id,
            modo=sesion.modo,
            etiqueta=sesion.etiqueta,
            creada_en=sesion.creada_en,
            finalizada_en=sesion.finalizada_en,
            score=score,
            eventos=eventos,
            biometria=biometria,
        )

    @router.patch(
        "/sessions/{session_id}/finalizar",
        response_model=FinalizarSesionOut,
        summary="Finalizar sesion de proctoring (idempotente)",
        dependencies=[Depends(require_autenticado)],
    )
    async def finalizar_sesion(
        session_id: str,
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> FinalizarSesionOut:
        """Setea finalizada_en = now() si es NULL.

        Idempotente: si ya estaba finalizada, responde 200 sin modificar.
        404 si la sesion no existe.
        Sin body requerido.
        """
        sesion = await session_service.finalizar_sesion(db, session_id)
        if sesion is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )
        return FinalizarSesionOut(id=sesion.id, finalizada_en=sesion.finalizada_en)

    # C-15 (3.2): observaciones del proctor (insumo de la revision humana C-16).
    @router.post(
        "/sessions/{session_id}/observaciones",
        status_code=http_status.HTTP_201_CREATED,
        response_model=ObservacionOut,
        summary="Registrar observacion del proctor (insumo C-16)",
        dependencies=[Depends(require_proctor_o_admin)],
    )
    async def crear_observacion(
        session_id: str,
        body: ObservacionIn,
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> ObservacionOut:
        """Persiste una observacion del proctor sobre la sesion. 404 si no existe."""
        obs = await observacion_service.crear_observacion(
            db, session_id=session_id, texto=body.texto, proctor_actor=body.proctor_actor
        )
        if obs is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )
        return ObservacionOut(
            id=obs.id,
            texto=obs.texto,
            proctor_actor=obs.proctor_actor,
            creada_en=obs.creada_en,
        )

    @router.get(
        "/sessions/{session_id}/observaciones",
        response_model=list[ObservacionOut],
        summary="Listar observaciones del proctor de la sesion",
        dependencies=[Depends(require_proctor_o_admin)],
    )
    async def listar_observaciones(
        session_id: str,
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> list[ObservacionOut]:
        """Lista observaciones asc por creada_en. 404 si la sesion no existe."""
        obs = await observacion_service.listar_observaciones(db, session_id)
        if obs is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )
        return [
            ObservacionOut(
                id=o.id,
                texto=o.texto,
                proctor_actor=o.proctor_actor,
                creada_en=o.creada_en,
            )
            for o in obs
        ]

    # C-15 (3.3): cierre FORZADO de la sesion por el proctor. Operativo, NO
    # disciplinario (regla dura #5: el sistema nunca sanciona; el veredicto es
    # HUMANO en C-16). El audit trail vive en la propia fila (cierre_forzado_*).
    @router.patch(
        "/sessions/{session_id}/cerrar-forzado",
        response_model=CerrarForzadoOut,
        summary="Cierre forzado de sesion por el proctor (operativo, auditado)",
        dependencies=[Depends(require_proctor_o_admin)],
    )
    async def cerrar_forzado(
        session_id: str,
        body: CerrarForzadoIn,
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> CerrarForzadoOut:
        """Fuerza el cierre: setea finalizada_en + cierre_forzado_*. Idempotente. 404 si no existe."""
        sesion = await session_service.cerrar_forzado(
            db, session_id, motivo=body.motivo, proctor_actor=body.proctor_actor
        )
        if sesion is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )
        return CerrarForzadoOut(
            id=sesion.id,
            finalizada_en=sesion.finalizada_en,
            cierre_forzado_en=sesion.cierre_forzado_en,
            cierre_forzado_por=sesion.cierre_forzado_por,
            cierre_forzado_motivo=sesion.cierre_forzado_motivo,
        )

    @router.delete(
        "/sessions/{session_id}",
        status_code=http_status.HTTP_204_NO_CONTENT,
        summary="Eliminar sesion",
        dependencies=[Depends(require_admin)],
    )
    async def eliminar_sesion(
        session_id: str,
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> None:
        """Elimina una sesion y sus eventos/biometria asociados (CASCADE)."""
        ok = await session_service.eliminar_sesion(db, session_id)
        if not ok:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )

    return router
