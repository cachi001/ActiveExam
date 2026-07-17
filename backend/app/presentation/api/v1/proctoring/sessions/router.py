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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.proctoring import observacion_service, session_service
from app.application.proctoring.enforcement import (
    FueraDeVentanaError,
    IntentosAgotadosError,
    NoInscriptoError,
    TiempoAgotadoError,
    verificar_enforcement,
    verificar_inscripcion,
    verificar_plazo,
)
from app.application.proctoring.finalizar_con_writeback import (
    finalizar_sesion_con_writeback,
)
from app.application.proctoring.scoring import (
    calcular_score,
    eventos_en_pausa_autorizada,
)
from app.application.moodle.grade_calculator import RespuestaAlumno, calcular_nota_academica
from app.application.moodle.writeback_service import MoodleWritebackService
from app.domain.auth.identity import AuthenticatedPrincipal
from app.infrastructure.persistence.models.moodle_writeback import RespuestaAlumnoModel
from app.infrastructure.persistence.models.proctoring import ProctoringSessionModel
from app.infrastructure.persistence.repositories.moodle_writeback import (
    RespuestaAlumnoRepository,
)
from app.presentation.api.v1.proctoring.sessions.schemas import (
    BiometriaDetalle,
    CerrarForzadoIn,
    CerrarForzadoOut,
    CrearSesionIn,
    CrearSesionOut,
    EventoDetalle,
    FinalizarSesionOut,
    ListarRespuestasOut,
    ObservacionIn,
    ObservacionOut,
    RespuestaGuardadaOut,
    SesionDetalle,
    SesionResumen,
    SubmitRespuestasIn,
    SubmitRespuestasOut,
)


def _principal_es_dueno(
    sesion: ProctoringSessionModel, principal: AuthenticatedPrincipal
) -> bool:
    """True si la sesion pertenece al principal autenticado (H1, IDOR).

    Los endpoints de respuestas/finalizar son del ALUMNO: solo el dueno de la
    sesion puede operarla. La identidad del alumno se persiste server-side al
    CREAR la sesion (``alumno_idnumber``/``alumno_email`` desde el JWT), por lo
    que aca se compara contra el principal del request.

    - Coincide por ``id_institucional`` O por ``email`` → es el dueno.
    - Sesion SIN identidad almacenada (legacy/modo 'test' previo a la persistencia
      de identidad) → se permite: no hay a quien atribuirla y no expone notas de
      nadie. Toda sesion nueva guarda identidad, asi que este caso no aplica al
      flujo normal de examen.
    """
    idn = sesion.alumno_idnumber
    email = sesion.alumno_email
    if not idn and not email:
        return True
    if idn and principal.id_institucional and idn == principal.id_institucional:
        return True
    if email and principal.email and email == principal.email:
        return True
    return False


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
    writeback_svc: MoodleWritebackService | None = None,
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
    )
    async def crear_sesion(
        body: CrearSesionIn,
        db: Annotated[AsyncSession, Depends(get_db)],
        principal: Annotated[AuthenticatedPrincipal, Depends(require_autenticado)],
    ) -> CrearSesionOut:
        """Crea una nueva sesion de proctoring slim.

        C-69 (backstop server-side): si la sesion se vincula a un examen
        (``examen_contenido_id``), se ENFORCEA la ventana de rendicion
        (apertura/cierre) y los intentos permitidos contra ``examen_contenido``,
        con la hora del servidor. El cliente ya gatea "Rendir" pero es un sensor
        no confiable (regla dura #6); esto es el backstop duro. Sin
        ``examen_contenido_id`` (modo 'test') NO se aplica enforcement.

        La identidad del alumno (id_institucional/email del JWT) se persiste SIEMPRE
        en la fila — el enforcement de intentos la usa para contar las rendiciones.
        """
        from datetime import datetime, timezone

        if body.examen_contenido_id is not None:
            try:
                await verificar_enforcement(
                    db,
                    examen_contenido_id=body.examen_contenido_id,
                    alumno_idnumber=principal.id_institucional,
                    ahora=datetime.now(timezone.utc),
                )
            except FueraDeVentanaError as exc:
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "fuera_de_ventana",
                        "mensaje": exc.mensaje,
                        "apertura": exc.apertura.isoformat() if exc.apertura else None,
                        "cierre": exc.cierre.isoformat() if exc.cierre else None,
                    },
                ) from exc
            except IntentosAgotadosError as exc:
                raise HTTPException(
                    status_code=http_status.HTTP_409_CONFLICT,
                    detail={
                        "error": "intentos_agotados",
                        "mensaje": exc.mensaje,
                        "intentos_permitidos": exc.intentos_permitidos,
                        "rendidos": exc.rendidos,
                    },
                ) from exc

            # Gate de inscripción (C-71): backstop server-side — el alumno debe estar
            # inscripto en la comisión del examen para poder crear la sesión.
            try:
                await verificar_inscripcion(
                    db,
                    examen_contenido_id=body.examen_contenido_id,
                    alumno_idnumber=principal.id_institucional,
                )
            except NoInscriptoError as exc:
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail={"error": "no_inscripto", "mensaje": exc.mensaje},
                ) from exc

        sesion = await session_service.crear_o_reanudar_sesion(
            db=db,
            modo=body.modo,
            exam_id=body.exam_id,
            etiqueta=body.etiqueta,
            examen_contenido_id=body.examen_contenido_id,
            alumno_idnumber=principal.id_institucional or None,
            alumno_email=principal.email or None,
        )
        return CrearSesionOut(
            id=sesion.id,
            creada_en=sesion.creada_en,
            examen_contenido_id=sesion.examen_contenido_id,
        )

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
                examen_contenido_id=s.examen_contenido_id,
                examen_titulo=s.examen_titulo,
                comision_nombre=s.comision_nombre,
                materia_nombre=s.materia_nombre,
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
            examen_contenido_id=sesion.examen_contenido_id,
            creada_en=sesion.creada_en,
            finalizada_en=sesion.finalizada_en,
            score=score,
            eventos=eventos,
            biometria=biometria,
            cierre_forzado_en=sesion.cierre_forzado_en,
            cierre_forzado_motivo=sesion.cierre_forzado_motivo,
        )

    @router.post(
        "/sessions/{session_id}/respuestas",
        status_code=http_status.HTTP_201_CREATED,
        response_model=SubmitRespuestasOut,
        summary="Enviar respuestas del alumno (para cálculo de nota server-side, C-69)",
        dependencies=[Depends(require_autenticado)],
    )
    async def submit_respuestas(
        session_id: str,
        body: SubmitRespuestasIn,
        db: Annotated[AsyncSession, Depends(get_db)],
        principal: Annotated[AuthenticatedPrincipal, Depends(require_autenticado)],
    ) -> SubmitRespuestasOut:
        """Persiste las respuestas del alumno para calcular la nota server-side.

        D8: la corrección y el write-back los origina el backend, nunca el cliente.
        D3: la opción correcta NUNCA viaja al cliente — sólo se usa acá server-side.
        Idempotente por (session_id, pregunta_id): re-enviar sobreescribe la respuesta.

        Seguridad:
        - H1 (IDOR): 404 si la sesión no existe o no es del alumno autenticado.
        - H2 (regrade): 409 si la sesión ya está finalizada — no se pueden cambiar
          las respuestas de un intento ya entregado.
        """
        sesion_model = (
            await db.execute(
                select(ProctoringSessionModel).where(
                    ProctoringSessionModel.id == session_id
                )
            )
        ).scalar_one_or_none()
        # 404 (no 403) tanto si no existe como si no es del alumno: no revelar la
        # existencia de sesiones ajenas (no dar un oráculo de session_ids).
        if sesion_model is None or not _principal_es_dueno(sesion_model, principal):
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )
        if sesion_model.finalizada_en is not None:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail={
                    "error": "sesion_finalizada",
                    "mensaje": "No se pueden modificar las respuestas de una sesión ya finalizada.",
                },
            )
        # Enforcement de PLAZO (C-72 §2, H-1/H-2): revalidar el reloj server-side en
        # cada envío. El cliente es sensor no confiable (regla #6): sin esto la sesión
        # abierta acepta respuestas fuera de tiempo / con la ventana cerrada.
        if sesion_model.examen_contenido_id is not None:
            from datetime import datetime, timezone

            try:
                await verificar_plazo(
                    db,
                    examen_contenido_id=sesion_model.examen_contenido_id,
                    creada_en=sesion_model.creada_en,
                    ahora=datetime.now(timezone.utc),
                )
            except TiempoAgotadoError as exc:
                raise HTTPException(
                    status_code=http_status.HTTP_409_CONFLICT,
                    detail={"error": "tiempo_agotado", "mensaje": exc.mensaje},
                ) from exc
        repo = RespuestaAlumnoRepository(db)
        n = await repo.guardar_respuestas(
            session_id=session_id,
            respuestas=[
                {"pregunta_id": r.pregunta_id, "opcion_elegida_id": r.opcion_elegida_id}
                for r in body.respuestas
            ],
        )
        # El repo hace flush; sin commit las respuestas se pierden al cerrar la
        # sesión de DB del request (get_db no auto-commitea).
        await db.commit()
        return SubmitRespuestasOut(session_id=session_id, respuestas_guardadas=n)

    @router.get(
        "/sessions/{session_id}/respuestas",
        response_model=ListarRespuestasOut,
        summary="Obtener las respuestas ya guardadas de la sesion (reanudacion, dueño)",
    )
    async def obtener_respuestas(
        session_id: str,
        db: Annotated[AsyncSession, Depends(get_db)],
        principal: Annotated[AuthenticatedPrincipal, Depends(require_autenticado)],
    ) -> ListarRespuestasOut:
        """Devuelve las respuestas ya persistidas de la sesion (vuln reload/restart).

        Al reanudar una sesion ACTIVA (creada antes de un F5), el cliente necesita
        recuperar lo que ya habia contestado para no reiniciar el intento con las
        respuestas en blanco. Gateado al DUEÑO de la sesion (mismo criterio de
        ``_principal_es_dueno`` que ``submit_respuestas``/``finalizar_sesion``):
        404 (no 403) tanto si no existe como si no es del alumno autenticado, para
        no revelar la existencia de sesiones ajenas.
        """
        sesion_model = (
            await db.execute(
                select(ProctoringSessionModel).where(
                    ProctoringSessionModel.id == session_id
                )
            )
        ).scalar_one_or_none()
        if sesion_model is None or not _principal_es_dueno(sesion_model, principal):
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )
        repo = RespuestaAlumnoRepository(db)
        rows = await repo.listar_por_sesion(session_id)
        return ListarRespuestasOut(
            session_id=session_id,
            respuestas=[
                RespuestaGuardadaOut(
                    pregunta_id=r.pregunta_id, opcion_elegida_id=r.opcion_elegida_id
                )
                for r in rows
            ],
        )

    @router.patch(
        "/sessions/{session_id}/finalizar",
        response_model=FinalizarSesionOut,
        summary="Finalizar sesion de proctoring (idempotente)",
    )
    async def finalizar_sesion(
        session_id: str,
        db: Annotated[AsyncSession, Depends(get_db)],
        principal: Annotated[AuthenticatedPrincipal, Depends(require_autenticado)],
    ) -> FinalizarSesionOut:
        """Setea finalizada_en = now() si es NULL.

        Idempotente: si ya estaba finalizada, responde 200 sin modificar.
        404 si la sesion no existe.
        C-69 (admin-sync): si la sesión tiene examen_contenido vinculado, la nota se
        CALCULA y PERSISTE como 'pendiente'. NO se auto-envía a Moodle — el envío es
        manual por el admin (POST /exam-content/{examen_id}/sincronizar-moodle). La
        nota se calcula SIEMPRE que haya examen vinculado, esté o no Moodle configurado
        (así el admin la ve en los resultados aunque Moodle no exista todavía).

        Seguridad:
        - H1 (IDOR): 404 si la sesión no existe o no es del alumno autenticado.
        - H2 (regrade): si la sesión YA estaba finalizada, NO se recalcula ni
          re-persiste la nota (idempotente puro) — así no se puede subir la nota
          re-finalizando un intento ya entregado.
        """
        sesion_model = (
            await db.execute(
                select(ProctoringSessionModel).where(
                    ProctoringSessionModel.id == session_id
                )
            )
        ).scalar_one_or_none()
        if sesion_model is None or not _principal_es_dueno(sesion_model, principal):
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Sesion {session_id!r} no encontrada",
            )

        ya_finalizada = sesion_model.finalizada_en is not None

        # H2: la nota se calcula SOLO en la primera finalización. Re-finalizar una
        # sesión ya finalizada es idempotente y NO recalcula (nota=None → el
        # writeback no toca el estado persistido).
        nota: float | None = None
        if not ya_finalizada and sesion_model.examen_contenido_id:
            resp_rows = await db.execute(
                select(RespuestaAlumnoModel).where(
                    RespuestaAlumnoModel.session_id == session_id
                )
            )
            respuestas = [
                RespuestaAlumno(
                    pregunta_id=r.pregunta_id,
                    opcion_elegida_id=r.opcion_elegida_id,
                )
                for r in resp_rows.scalars().all()
            ]
            nota = await calcular_nota_academica(
                db=db,
                examen_contenido_id=sesion_model.examen_contenido_id,
                respuestas=respuestas,
            )

        # Identidad para el write-back: la del DUEÑO de la sesión (persistida al
        # crearla), con fallback al principal. Antes se usaba la identidad del que
        # finaliza → atribución incorrecta de la nota (H1).
        alumno_idnumber = sesion_model.alumno_idnumber or principal.id_institucional or ""
        alumno_email = sesion_model.alumno_email or principal.email or ""

        sesion = await finalizar_sesion_con_writeback(
            db=db,
            session_id=session_id,
            writeback_svc=writeback_svc,
            nota=nota,
            alumno_idnumber=alumno_idnumber,
            alumno_email=alumno_email,
        )
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
        """Fuerza el cierre: setea finalizada_en + cierre_forzado_*.

        Idempotente. 404 si la sesion no existe.
        """
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
