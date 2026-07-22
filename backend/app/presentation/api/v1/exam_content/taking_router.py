"""Router de rendición de examen del alumno (exam_content, C-69).

Endpoints student-facing: catálogo elegible, rendición (preguntas sin es_correcta,
D3), envío de respuestas, notas, informe de devolución y revisión post-examen.
Extraído de router.py al partir el god-file en sub-routers; los helpers compartidos
viven en ./_shared.
"""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)

from app.application.exam_content.errors import (
    CodigoMatriculacionInvalidoError,
    ComisionInactivaError,
    MateriaInactivaError,
    PerfilIncompletoError,
)
from app.application.exam_content.inscripcion_service import (
    AutoMatriculacionService,
)
from app.application.exam_content.taking_service import LecturaExamenService
from app.application.moodle.resultados_query import (
    listar_mis_notas,
)
from app.application.moodle.revision_query import obtener_revision
from app.application.moodle.writeback_service import (
    MoodleWritebackService,
)
from app.domain.auth.identity import AuthenticatedPrincipal
from app.presentation.api.v1.auth.dependencies import (
    get_current_principal,
)
from app.presentation.api.v1.exam_content._shared import _es_staff, _resumen_to_response
from app.presentation.api.v1.exam_content.schemas import (
    CapturaFirmadaResponse,
    ComisionResponse,
    ExamenContenidoResumenResponse,
    ExamenesContenidoPaginadosResponse,
    ExamenRendicionResponse,
    InformeDevolucionResponse,
    InscribirPorCodigoRequest,
    InscribirPorCodigoResponse,
    MateriaResponse,
    MiNotaResponse,
    MisNotasResponse,
    OpcionRendicionResponse,
    OpcionRevisionResponse,
    PreguntaRendicionResponse,
    PreguntaRevisionResponse,
    RevisionExamenResponse,
    SenalAnalisisResponse,
)


def create_exam_taking_router(
    session_factory=None,
    *,
    writeback_svc: MoodleWritebackService | None = None,
    presign_service=None,
) -> APIRouter:
    """Router de lectura de examen para la rendición del alumno (C-69, D3).

    GET /            : cualquier principal autenticado lista los exámenes importados
                       con id, titulo y cantidad_preguntas (catálogo del alumno).
    GET /mis-notas   : el alumno autenticado ve SUS notas finalizadas + estado L2.5.
    GET /{examen_id} : cualquier principal autenticado obtiene preguntas+opciones
                       en orden estable, SIN es_correcta (D3).

    writeback_svc: None = Moodle no configurado; una nota 'pendiente' se muestra como
    'sin_token' (igual que el read-model del admin).
    """
    router = APIRouter()

    @router.get(
        "",
        response_model=ExamenesContenidoPaginadosResponse,
        summary="Listar exámenes de contenido importados (catálogo paginado)",
    )
    @router.get(
        "/",
        response_model=ExamenesContenidoPaginadosResponse,
        include_in_schema=False,
    )
    async def listar_examenes_contenido(
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
        q: str | None = None,
        page: int = 1,
        page_size: int = 1000,
    ) -> ExamenesContenidoPaginadosResponse:
        """Lista paginada de exámenes de contenido (catálogo del alumno/admin).

        Cualquier principal autenticado puede consultar el catálogo (sin admin ni MFA).
        Contrato (C-69 admin-sync, tarea 4): { items, total, page, page_size }.
        - q:        búsqueda serverside por título/materia/comisión (ILIKE, opcional).
        - page:     1-indexado (default 1).
        - page_size: default 1000 → sin params devuelve TODO (compat frontend).
        Filtrado y orden SIEMPRE en SQL. D3: es_correcta NUNCA incluida.
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        from app.infrastructure.persistence.repositories.exam_content import (
            ExamenContenidoSqlRepository,
            InscripcionSqlRepository,
        )

        # Gate de inscripción (C-71): el alumno ve SOLO los exámenes de las comisiones
        # donde está inscripto; los roles de gestión (admin/proctor/...) ven todo el
        # catálogo. El filtro es server-side por el id_institucional del principal.
        async with session_factory() as session:
            repo = ExamenContenidoSqlRepository(session)
            if _es_staff(principal):
                comision_ids = None
            else:
                comision_ids = await InscripcionSqlRepository(
                    session
                ).comision_ids_inscriptas(principal.id_institucional)
            resumenes, total = await repo.listar_paginado(
                q=q, page=page, page_size=page_size, comision_ids=comision_ids
            )

        return ExamenesContenidoPaginadosResponse(
            items=[_resumen_to_response(r) for r in resumenes],
            total=total,
            page=max(1, page),
            page_size=max(1, page_size),
        )

    # -----------------------------------------------------------------------
    # Auto-matriculación por código (C-70, D3) — auth-only (rol estudiante).
    # El alumno postea un codigo_matriculacion y se une a esa comisión. El
    # usuario_id sale del principal (JWT sub), NUNCA del body (cliente no
    # confiable). Idempotente: ya-inscripto → respuesta amistosa sin duplicar.
    # No altera el gate puede_rendir (solo set-membership).
    # -----------------------------------------------------------------------

    @router.post(
        "/inscribirme",
        response_model=InscribirPorCodigoResponse,
        status_code=status.HTTP_200_OK,
        summary="Auto-matricularse a una comisión con un código (enrolment key)",
    )
    async def inscribirme_por_codigo(
        body: InscribirPorCodigoRequest,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> InscribirPorCodigoResponse:
        """El alumno autenticado se auto-matricula a la comisión del código.

        422 'codigo_invalido' si el código es vacío/malformado; 404 'codigo_invalido'
        si no mapea a ninguna comisión (sin crear inscripción). Idempotente: si ya
        estaba inscripto responde ya_inscripto=True (200) sin duplicar.
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        if not principal.subject:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token no porta un subject (sub) válido.",
            )
        # Vacío/malformado → 422 (validación); no-existente → 404 (abajo, del service).
        if not body.codigo_matriculacion.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "codigo_invalido", "mensaje": "El código es vacío."},
            )

        from app.infrastructure.persistence.repositories.biometric_reference import (
            EmbeddingReferenciaRepository,
            FotoReferenciaRepository,
        )
        from app.infrastructure.persistence.repositories.consent_perfil import (
            ConsentimientoPerfilSqlRepository,
        )
        from app.infrastructure.persistence.repositories.exam_content import (
            ComisionSqlRepository,
            InscripcionSqlRepository,
            MateriaSqlRepository,
        )

        async with session_factory() as session:
            service = AutoMatriculacionService(
                comision_repo=ComisionSqlRepository(session),
                materia_repo=MateriaSqlRepository(session),
                inscripcion_repo=InscripcionSqlRepository(session),
                consent_repo=ConsentimientoPerfilSqlRepository(session),
                embedding_repo=EmbeddingReferenciaRepository(session),
                foto_repo=FotoReferenciaRepository(session),
            )
            try:
                result = await service.inscribir_por_codigo(
                    body.codigo_matriculacion, principal.subject
                )
                await session.commit()
            except PerfilIncompletoError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"error": "perfil_incompleto", "mensaje": exc.razon},
                ) from exc
            except CodigoMatriculacionInvalidoError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "codigo_invalido", "mensaje": str(exc)},
                ) from exc
            except MateriaInactivaError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error": "materia_inactiva", "mensaje": str(exc)},
                ) from exc
            except ComisionInactivaError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error": "comision_inactiva", "mensaje": str(exc)},
                ) from exc

        return InscribirPorCodigoResponse(
            comision_id=result.comision_id,
            comision_nombre=result.comision_nombre,
            materia_nombre=result.materia_nombre,
            ya_inscripto=result.ya_inscripto,
        )

    # -----------------------------------------------------------------------
    # "Mis notas" del alumno (C-69, student-facing). Cualquier principal
    # autenticado ve SOLO sus notas finalizadas (identificado por el JWT:
    # id_institucional -> alumno_idnumber, email -> alumno_email). Ruta estática
    # declarada ANTES de "/{examen_id}" para que el path param no la capture.
    # -----------------------------------------------------------------------

    @router.get(
        "/mis-notas",
        response_model=MisNotasResponse,
        summary="Mis notas finalizadas (nota + estado de envío + estado de revisión L2.5)",
    )
    async def mis_notas(
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> MisNotasResponse:
        """Notas finalizadas del alumno autenticado + estado L2.5 'en cola de revisión'.

        Identidad del alumno desde el JWT (id_institucional/email), igual que lo que
        el write-back persiste (alumno_idnumber/alumno_email). Para cada examen:
        nota académica, estado del envío a Moodle y si la sesión está en cola de
        revisión (score de proctoring >= umbral_cola_revision). D3: es_correcta NUNCA
        expuesta; el score PRIORIZA, no sanciona (L2.5).
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        moodle_configurado = writeback_svc is not None
        async with session_factory() as session:
            items, total = await listar_mis_notas(
                db=session,
                alumno_idnumber=principal.id_institucional or "",
                alumno_email=principal.email or "",
                moodle_configurado=moodle_configurado,
            )

        return MisNotasResponse(
            items=[
                MiNotaResponse(
                    examen_id=r.examen_id,
                    examen_titulo=r.examen_titulo,
                    nota=r.nota,
                    nota_maxima=r.nota_maxima,
                    aprobado=r.aprobado,
                    estado_moodle=r.estado_moodle,
                    en_cola_revision=r.en_cola_revision,
                    score=r.score,
                    umbral_revision=r.umbral_revision,
                    eventos=r.eventos,
                    finalizada_en=r.finalizada_en,
                    nota_visible=r.nota_visible,
                    revision_disponible=r.revision_disponible,
                    cierre=r.cierre,
                    session_id=r.session_id,
                    nota_anulada=r.nota_anulada,
                    veredicto=r.veredicto,
                    informe_disponible=r.informe_disponible,
                )
                for r in items
            ],
            total=total,
        )

    @router.get(
        "/mis-notas/{session_id}/informe",
        response_model=InformeDevolucionResponse,
        summary="Informe de devolución (SOLO nota anulada por fraude) — C-71 D12",
    )
    async def informe_devolucion(
        session_id: str,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> InformeDevolucionResponse:
        """Informe de devolución del alumno para SU sesión anulada por fraude.

        Minimización (Ley 25.326): solo existe si la nota del titular fue anulada
        por fraude; en cualquier otro caso (sesión ajena, sin anulación) → 404 sin
        revelar evidencia. Cada acceso se audita como ejercicio del derecho de
        acceso del titular (RN-DSR-01)."""
        from app.application.review.informe_service import build_informe_devolucion
        from app.infrastructure.storage.presign import StoragePresignService

        factory = session_factory or getattr(
            request.app.state, "session_factory", None
        )
        if factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        presign = presign_service or getattr(
            request.app.state, "presign_service", None
        )
        if presign is None:
            # Fallback determinista: el contrato de la URL firmada (expira 15 min)
            # no depende del SDK real de storage en el MVP slim.
            presign = StoragePresignService(endpoint="", bucket="evidence")

        async with factory() as session:
            informe = await build_informe_devolucion(
                db=session,
                session_id=session_id,
                titular_idnumber=principal.id_institucional or "",
                presign=presign,
            )
            if informe is None:
                # Minimización: no se revela si la sesión existe o no.
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Informe no disponible.",
                )
            # Audit del acceso del TITULAR como derecho de acceso (Ley 25.326).
            from app.domain.audit_chain import AuditEntry
            from app.infrastructure.persistence.repositories.audit_log import (
                AuditLogSqlRepository,
            )

            await AuditLogSqlRepository(session).append(
                AuditEntry(
                    actor=principal.id_institucional or "titular",
                    timestamp="",
                    ip=request.client.host if request.client else "",
                    user_agent=request.headers.get("user-agent", ""),
                    accion="derecho_acceso.informe_devolucion",
                    evidencia_id=session_id,
                    proposito=(
                        "Ejercicio del derecho de acceso del titular al informe de "
                        "devolución de su sesión anulada (Ley 25.326, RN-DSR-01)."
                    ),
                )
            )
            await session.commit()

        return InformeDevolucionResponse(
            session_id=informe.session_id,
            decision=informe.decision,
            resolucion=informe.resolucion,
            motivo=informe.motivo,
            senales=[
                SenalAnalisisResponse(
                    tipo=s.tipo,
                    severidad=s.severidad,
                    ocurrencias=s.ocurrencias,
                    face_count_servidor=s.face_count_servidor,
                    veredicto_reinferencia=s.veredicto_reinferencia,
                )
                for s in informe.senales
            ],
            capturas=[
                CapturaFirmadaResponse(
                    object_key=c.object_key, url=c.url, expires_in=c.expires_in
                )
                for c in informe.capturas
            ],
        )

    # -----------------------------------------------------------------------
    # Navegación del alumno: materia → comisión → examen (datos REALES).
    # Cualquier principal autenticado. Rutas estáticas declaradas ANTES de
    # "/{examen_id}" para que no las capture el path param. Sin trailing slash
    # (evita el 307 del catálogo).
    # -----------------------------------------------------------------------

    @router.get(
        "/materias",
        response_model=list[MateriaResponse],
        summary="Listar materias disponibles",
    )
    async def listar_materias(
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> list[MateriaResponse]:
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        from app.infrastructure.persistence.repositories.exam_content import (
            InscripcionSqlRepository,
            MateriaSqlRepository,
        )

        # Gate de inscripción (C-71): el alumno ve SOLO las materias donde tiene
        # comisión inscripta; staff ve todas.
        async with session_factory() as session:
            if _es_staff(principal):
                materias = await MateriaSqlRepository(session).listar()
            else:
                materias = await InscripcionSqlRepository(session).materias_inscriptas(
                    principal.id_institucional
                )

        return [
            MateriaResponse(id=m.id, codigo=m.codigo, nombre=m.nombre, activa=m.activa)
            for m in materias
        ]

    @router.get(
        "/materias/{materia_id}/comisiones",
        response_model=list[ComisionResponse],
        summary="Listar comisiones de una materia",
    )
    async def listar_comisiones_de_materia(
        materia_id: str,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> list[ComisionResponse]:
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        from app.infrastructure.persistence.repositories.exam_content import (
            ComisionSqlRepository,
            InscripcionSqlRepository,
        )

        # Gate de inscripción (C-71): el alumno ve SOLO sus comisiones inscriptas de
        # esa materia; staff ve todas las comisiones de la materia.
        async with session_factory() as session:
            if _es_staff(principal):
                comisiones = await ComisionSqlRepository(session).listar_por_materia(
                    materia_id
                )
            else:
                comisiones = await InscripcionSqlRepository(
                    session
                ).comisiones_inscriptas_de_materia(principal.id_institucional, materia_id)

        return [
            ComisionResponse(
                id=c.id,
                materia_id=c.materia_id,
                codigo=c.codigo,
                nombre=c.nombre,
                periodo=c.periodo,
                anio=c.anio,
                codigo_matriculacion=c.codigo_matriculacion,
                activa=c.activa,
            )
            for c in comisiones
        ]

    @router.get(
        "/comisiones/{comision_id}/examenes",
        response_model=list[ExamenContenidoResumenResponse],
        summary="Listar exámenes de una comisión",
    )
    async def listar_examenes_de_comision(
        comision_id: str,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> list[ExamenContenidoResumenResponse]:
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        from app.infrastructure.persistence.repositories.exam_content import (
            ExamenContenidoSqlRepository,
        )

        async with session_factory() as session:
            resumenes = await ExamenContenidoSqlRepository(session).listar_por_comision(
                comision_id
            )

        return [_resumen_to_response(r) for r in resumenes]

    @router.get(
        "/{examen_id}/resumen",
        response_model=ExamenContenidoResumenResponse,
        summary="Resumen (metadatos) de un examen para el encabezado del detalle",
    )
    async def obtener_resumen_examen(
        examen_id: str,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> ExamenContenidoResumenResponse:
        """Metadatos del encabezado del detalle: id, titulo, cantidad_preguntas y,
        si tiene comisión asociada (D11, NULLABLE), comision_id/comision_nombre/
        materia_nombre. Cualquier principal autenticado (sin admin/MFA). 404 si no
        existe. D3: es_correcta NUNCA expuesta; no viajan preguntas ni opciones.
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        from app.infrastructure.persistence.repositories.exam_content import (
            ExamenContenidoSqlRepository,
        )

        async with session_factory() as session:
            resumen = await ExamenContenidoSqlRepository(session).obtener_resumen(
                examen_id
            )

        if resumen is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "examen_no_encontrado", "examen_id": examen_id},
            )

        return _resumen_to_response(resumen)

    @router.get(
        "/{examen_id}/revision",
        response_model=RevisionExamenResponse,
        summary="Revisión post-examen del alumno (corrección + contadores)",
    )
    async def revisar_examen(
        examen_id: str,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> RevisionExamenResponse:
        """Devuelve la corrección del intento FINALIZADO del alumno para este examen.

        Excepción a D3: expone es_correcta, pero SOLO al dueño (la query filtra por
        idnumber/email del JWT) y SOLO con el intento ya finalizado — como las
        "Review options" de Moodle. 404 si el alumno no tiene un intento finalizado.
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        async with session_factory() as session:
            rev = await obtener_revision(
                db=session,
                examen_contenido_id=examen_id,
                alumno_idnumber=principal.id_institucional or "",
                alumno_email=principal.email or "",
            )

        if rev is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "revision_no_disponible", "examen_id": examen_id},
            )

        return RevisionExamenResponse(
            examen_id=rev.examen_id,
            titulo=rev.titulo,
            nota=rev.nota,
            nota_maxima=rev.nota_maxima,
            aprobado=rev.aprobado,
            total_preguntas=rev.total_preguntas,
            correctas=rev.correctas,
            incorrectas=rev.incorrectas,
            sin_responder=rev.sin_responder,
            finalizada_en=rev.finalizada_en,
            disponible=rev.disponible,
            revision_disponible=rev.revision_disponible,
            cierre=rev.cierre,
            preguntas=[
                PreguntaRevisionResponse(
                    id=p.id,
                    enunciado=p.enunciado,
                    orden=p.orden,
                    respondida=p.respondida,
                    acertada=p.acertada,
                    opciones=[
                        OpcionRevisionResponse(
                            id=o.id,
                            texto=o.texto,
                            orden=o.orden,
                            es_correcta=o.es_correcta,
                            elegida=o.elegida,
                        )
                        for o in p.opciones
                    ],
                )
                for p in rev.preguntas
            ],
        )

    @router.get(
        "/{examen_id}",
        response_model=ExamenRendicionResponse,
        summary="Obtener examen para rendir (sin opción correcta)",
    )
    async def obtener_examen_para_rendir(
        examen_id: str,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> ExamenRendicionResponse:
        """Devuelve preguntas y opciones en orden estable.

        D3: es_correcta NUNCA incluida. 404 si el examen no existe.
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        from app.infrastructure.persistence.repositories.exam_content import (
            ComisionSqlRepository,
            ExamenContenidoSqlRepository,
            MateriaSqlRepository,
        )

        async with session_factory() as session:
            repo = ExamenContenidoSqlRepository(session)
            # Repos de contexto para el freeze de materia desactivada (C-72 §17).
            service = LecturaExamenService(
                repo,
                comision_repo=ComisionSqlRepository(session),
                materia_repo=MateriaSqlRepository(session),
            )
            try:
                rendicion = await service.obtener_para_rendir(examen_id)
            except MateriaInactivaError as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error": "materia_inactiva", "mensaje": str(exc)},
                ) from exc
            except ComisionInactivaError as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error": "comision_inactiva", "mensaje": str(exc)},
                ) from exc

        if rendicion is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "examen_no_encontrado", "examen_id": examen_id},
            )

        return ExamenRendicionResponse(
            id=rendicion.id,
            titulo=rendicion.titulo,
            tiempo_limite_min=rendicion.tiempo_limite_min,
            mezclar_preguntas=rendicion.mezclar_preguntas,
            nota_maxima=rendicion.nota_maxima,
            nota_aprobacion=rendicion.nota_aprobacion,
            preguntas=[
                PreguntaRendicionResponse(
                    id=p.id,
                    enunciado=p.enunciado,
                    tipo=p.tipo,
                    orden=p.orden,
                    opciones=[
                        OpcionRendicionResponse(
                            id=o.id,
                            texto=o.texto,
                            orden=o.orden,
                        )
                        for o in p.opciones
                    ],
                )
                for p in rendicion.preguntas
            ],
        )

    return router
