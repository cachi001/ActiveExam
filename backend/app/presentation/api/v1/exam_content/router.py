"""Routers de exam_content (FastAPI, C-69).

Admin router:
  POST /moodle-import — admin-only + MFA: importa XML, crea ExamenContenido.

Taking router (student-facing):
  GET /{examen_id} — cualquier principal autenticado: preguntas+opciones sin es_correcta (D3).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.application.exam_content.asociacion_service import AsociacionComisionService
from app.application.moodle.resultados_query import (
    listar_estados_sincronizables,
    listar_resultados_examen,
)
from app.application.moodle.writeback_service import (
    MoodleWritebackService,
    WritebackEstado,
)
from app.application.exam_content.errors import (
    ComisionNoEncontradaError,
    ExamenNoEncontradoError,
    MoodleXmlInvalidoError,
    MoodleXmlVacioError,
)
from app.application.exam_content.import_service import ImportacionMoodleService
from app.application.exam_content.taking_service import LecturaExamenService, proyectar_examen
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol
from app.domain.exam_content.entities import Materia
from app.domain.exam_content.errors import (
    ComisionDuplicadaError,
    ExamenContenidoError,
    MateriaDuplicadaError,
)
from app.presentation.api.v1.auth.dependencies import (
    get_current_principal,
    require_roles,
)
from app.presentation.api.v1.exam_content.schemas import (
    AltaInlineRequest,
    AltaInlineResponse,
    AsociarComisionRequest,
    AsociarComisionResponse,
    ComisionResponse,
    ExamenContenidoResumenResponse,
    ExamenesContenidoPaginadosResponse,
    ExamenRendicionResponse,
    ImportReporteResponse,
    MateriaResponse,
    MoodleTargetRequest,
    MoodleTargetResponse,
    OmitidaItemResponse,
    OpcionRendicionResponse,
    PreguntaRendicionResponse,
    ResultadoAlumnoResponse,
    ResultadosExamenPaginadosResponse,
    SincronizarMoodleResponse,
)


def _resumen_to_response(r) -> ExamenContenidoResumenResponse:
    """Mapea un ExamenContenidoResumen de dominio al schema de respuesta (D3)."""
    return ExamenContenidoResumenResponse(
        id=r.id,
        titulo=r.titulo,
        cantidad_preguntas=r.cantidad_preguntas,
        comision_id=r.comision_id,
        comision_nombre=r.comision_nombre,
        materia_nombre=r.materia_nombre,
    )


def create_exam_content_router(
    session_factory=None,
    *,
    writeback_svc: MoodleWritebackService | None = None,
) -> APIRouter:
    """Factory que permite inyectar session_factory en tests.

    writeback_svc: servicio de write-back a Moodle (None = Moodle no configurado;
    la sincronización manual responde 'sin_token' sin crashear).
    """
    router = APIRouter(
        dependencies=[
            Depends(require_roles(Rol.ADMIN_EXAMENES, Rol.ADMIN_SISTEMA)),
        ]
    )

    async def _get_service(request) -> ImportacionMoodleService:
        from fastapi import Request

        factory = session_factory or getattr(request.app.state, "session_factory", None)
        if factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada (session_factory).",
            )
        return factory  # devolvemos la factory, el endpoint la usa vía context manager

    @router.post(
        "/moodle-import",
        response_model=ImportReporteResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def importar_moodle(
        file: UploadFile = File(...),
        titulo: str | None = Form(default=None),
        moodle_courseid: int | None = Form(default=None),
        moodle_cmid: int | None = Form(default=None),
    ) -> ImportReporteResponse:
        """Importa un archivo Moodle XML y crea el examen de contenido.

        D12 (parte B): moodle_courseid/moodle_cmid son opcionales y fijan el destino
        del write-back de nota POR EXAMEN. Si se omiten, el write-back usa el global.
        """
        from fastapi import Request

        xml_bytes = await file.read()

        # Construir el servicio directamente con la factory inyectada en el closure
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        from app.infrastructure.persistence.repositories.exam_content import (
            ExamenContenidoSqlRepository,
        )

        async with session_factory() as session:
            repo = ExamenContenidoSqlRepository(session)
            service = ImportacionMoodleService(repo)
            try:
                report = await service.importar(
                    xml_bytes,
                    titulo=titulo,
                    moodle_courseid=moodle_courseid,
                    moodle_cmid=moodle_cmid,
                )
                await session.commit()
            except MoodleXmlInvalidoError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": "xml_invalido", "mensaje": str(exc)},
                ) from exc
            except MoodleXmlVacioError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "xml_vacio", "mensaje": str(exc)},
                ) from exc
            except Exception:
                await session.rollback()
                raise

        return ImportReporteResponse(
            examen_id=report.examen_id,
            importadas=report.importadas,
            omitidas=[
                OmitidaItemResponse(tipo=o.tipo, nombre=o.nombre, motivo=o.motivo)
                for o in report.omitidas
            ],
        )

    # -----------------------------------------------------------------------
    # Materia + comisión (C-69 sección 6, D11) — admin-only, SIN MFA.
    # El guard admin está a nivel router (require_roles); la asociación es
    # OPCIONAL: un examen sin comisión sigue siendo válido y rendible.
    # -----------------------------------------------------------------------

    def _build_asociacion_service(session) -> AsociacionComisionService:
        from app.infrastructure.persistence.repositories.exam_content import (
            ComisionSqlRepository,
            ExamenContenidoSqlRepository,
            MateriaSqlRepository,
        )

        return AsociacionComisionService(
            examen_repo=ExamenContenidoSqlRepository(session),
            materia_repo=MateriaSqlRepository(session),
            comision_repo=ComisionSqlRepository(session),
        )

    @router.post(
        "/materias-comisiones",
        response_model=AltaInlineResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Alta inline de materia + comisión (opcionalmente asocia un examen)",
    )
    async def alta_inline_materia_comision(
        body: AltaInlineRequest,
    ) -> AltaInlineResponse:
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        async with session_factory() as session:
            service = _build_asociacion_service(session)
            try:
                materia = Materia(
                    codigo=body.materia.codigo, nombre=body.materia.nombre
                )
                result = await service.alta_inline(
                    materia=materia,
                    comision_codigo=body.comision.codigo,
                    comision_nombre=body.comision.nombre,
                    periodo=body.comision.periodo,
                    anio=body.comision.anio,
                    examen_id=body.examen_id,
                )
                await session.commit()
            except ExamenNoEncontradoError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "examen_no_encontrado", "examen_id": body.examen_id},
                ) from exc
            except (ComisionDuplicadaError, MateriaDuplicadaError) as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error": "duplicado", "mensaje": str(exc)},
                ) from exc
            except ExamenContenidoError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": "validacion_dominio", "mensaje": str(exc)},
                ) from exc

        return AltaInlineResponse(
            materia=MateriaResponse(
                id=result.materia.id,
                codigo=result.materia.codigo,
                nombre=result.materia.nombre,
            ),
            comision=ComisionResponse(
                id=result.comision.id,
                materia_id=result.comision.materia_id,
                codigo=result.comision.codigo,
                nombre=result.comision.nombre,
                periodo=result.comision.periodo,
                anio=result.comision.anio,
            ),
            examen_id=result.examen_id,
        )

    @router.post(
        "/{examen_id}/comision",
        response_model=AsociarComisionResponse,
        status_code=status.HTTP_200_OK,
        summary="Asociar un examen ya importado a una comisión existente",
    )
    async def asociar_examen_a_comision(
        examen_id: str,
        body: AsociarComisionRequest,
    ) -> AsociarComisionResponse:
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        async with session_factory() as session:
            service = _build_asociacion_service(session)
            try:
                await service.asociar_examen_a_comision(examen_id, body.comision_id)
                await session.commit()
            except ComisionNoEncontradaError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "comision_no_encontrada", "comision_id": body.comision_id},
                ) from exc
            except ExamenNoEncontradoError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "examen_no_encontrado", "examen_id": examen_id},
                ) from exc

        return AsociarComisionResponse(examen_id=examen_id, comision_id=body.comision_id)

    # -----------------------------------------------------------------------
    # Destino de write-back a Moodle POR EXAMEN (C-69, D12 parte B) — admin-only.
    # Permite fijar/leer moodle_courseid/cmid de un examen ya importado. Valores
    # AUTORITATIVOS: el write-back los usa; NULL → fallback al global de config_slim.
    # -----------------------------------------------------------------------

    async def _set_target(examen_id: str, courseid: int | None, cmid: int | None):
        """Carga el repo, fija el destino y devuelve la entidad (o None si no existe)."""
        from app.infrastructure.persistence.repositories.exam_content import (
            ExamenContenidoSqlRepository,
        )

        async with session_factory() as session:
            repo = ExamenContenidoSqlRepository(session)
            examen = await repo.set_moodle_target(examen_id, courseid, cmid)
            await session.commit()
        return examen

    @router.post(
        "/{examen_id}/moodle-target",
        response_model=MoodleTargetResponse,
        status_code=status.HTTP_200_OK,
        summary="Fijar el destino de write-back a Moodle (courseid/cmid) de un examen",
    )
    async def fijar_moodle_target(
        examen_id: str,
        body: MoodleTargetRequest,
    ) -> MoodleTargetResponse:
        """Fija moodle_courseid/cmid del examen (D12). 404 si el examen no existe.

        Valores AUTORITATIVOS para el write-back; null limpia y cae al global.
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        examen = await _set_target(examen_id, body.moodle_courseid, body.moodle_cmid)
        if examen is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "examen_no_encontrado", "examen_id": examen_id},
            )

        return MoodleTargetResponse(
            examen_id=examen.id,
            moodle_courseid=examen.moodle_courseid,
            moodle_cmid=examen.moodle_cmid,
        )

    @router.get(
        "/{examen_id}/moodle-target",
        response_model=MoodleTargetResponse,
        summary="Leer el destino de write-back a Moodle (courseid/cmid) de un examen",
    )
    async def leer_moodle_target(examen_id: str) -> MoodleTargetResponse:
        """Devuelve moodle_courseid/cmid del examen (null = fallback global). 404 si no existe."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        from app.infrastructure.persistence.repositories.exam_content import (
            ExamenContenidoSqlRepository,
        )

        async with session_factory() as session:
            examen = await ExamenContenidoSqlRepository(session).obtener(examen_id)

        if examen is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "examen_no_encontrado", "examen_id": examen_id},
            )

        return MoodleTargetResponse(
            examen_id=examen.id,
            moodle_courseid=examen.moodle_courseid,
            moodle_cmid=examen.moodle_cmid,
        )

    # -----------------------------------------------------------------------
    # Resultados del examen (C-69 admin-sync, tarea 2) — admin-only, SIN MFA.
    # Lista de alumnos que rindieron, con nota y estado del envío a Moodle.
    # -----------------------------------------------------------------------

    @router.get(
        "/{examen_id}/resultados",
        response_model=ResultadosExamenPaginadosResponse,
        summary="Resultados del examen: alumnos, nota y estado de envío a Moodle (paginado)",
    )
    async def resultados_examen(
        examen_id: str,
        q: str | None = None,
        estado: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ResultadosExamenPaginadosResponse:
        """Lista paginada de los alumnos que rindieron el examen.

        Deriva de las sesiones FINALIZADAS vinculadas + la nota persistida + el
        estado de write-back. Filtrado/orden SIEMPRE serverside.
        - q:      búsqueda por alumno (idnumber/email).
        - estado: filtro por estado (pendiente/enviado/fallido/sin_token).
        estado_moodle = 'sin_token' cuando Moodle no está configurado.
        D3: es_correcta NUNCA expuesta.
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        moodle_configurado = writeback_svc is not None
        async with session_factory() as session:
            items, total = await listar_resultados_examen(
                db=session,
                examen_id=examen_id,
                q=q,
                estado=estado,
                page=page,
                page_size=page_size,
                moodle_configurado=moodle_configurado,
            )

        return ResultadosExamenPaginadosResponse(
            items=[
                ResultadoAlumnoResponse(
                    session_id=r.session_id,
                    alumno_idnumber=r.alumno_idnumber,
                    alumno_email=r.alumno_email,
                    alumno_nombre=r.alumno_nombre,
                    nota=r.nota,
                    estado_moodle=r.estado_moodle,
                    actualizado_en=r.actualizado_en,
                )
                for r in items
            ],
            total=total,
            page=max(1, page),
            page_size=max(1, page_size),
        )

    # -----------------------------------------------------------------------
    # Sincronización manual a Moodle (C-69 admin-sync, tarea 3) — admin-only.
    # Dispara el write-back de las notas pendientes/fallidas del examen.
    # -----------------------------------------------------------------------

    @router.post(
        "/{examen_id}/sincronizar-moodle",
        response_model=SincronizarMoodleResponse,
        summary="Sincronizar manualmente las notas pendientes/fallidas del examen a Moodle",
    )
    async def sincronizar_moodle(examen_id: str) -> SincronizarMoodleResponse:
        """Envía a Moodle las notas en estado 'pendiente'/'fallido' del examen.

        Idempotente: las 'enviado' NO se re-mandan (las excluye la query). Si Moodle
        no está configurado (writeback_svc None), NO crashea: devuelve todo como
        'sin_token' y deja las notas en 'pendiente'.
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        async with session_factory() as session:
            pendientes = await listar_estados_sincronizables(
                db=session, examen_id=examen_id
            )
            total = len(pendientes)

            # Moodle no configurado: no se puede enviar. No crashea — sin_token.
            if writeback_svc is None:
                return SincronizarMoodleResponse(
                    enviadas=0,
                    fallidas=0,
                    sin_token=total,
                    total=total,
                    mensaje=(
                        "Moodle no está configurado (sin token). Las notas quedan "
                        "'pendiente'; configurá MOODLE_BASE_URL/MOODLE_WS_TOKEN para enviar."
                    ),
                )

            enviadas = 0
            fallidas = 0
            for fila in pendientes:
                await writeback_svc.ejecutar_writeback(
                    db=session,
                    session_id=fila.session_id,
                    nota=float(fila.nota) if fila.nota is not None else 0.0,
                    alumno_idnumber=fila.alumno_idnumber or "",
                    alumno_email=fila.alumno_email or "",
                )
                if fila.estado == WritebackEstado.ENVIADO:
                    enviadas += 1
                else:
                    fallidas += 1
            await session.commit()

        return SincronizarMoodleResponse(
            enviadas=enviadas,
            fallidas=fallidas,
            sin_token=0,
            total=total,
        )

    return router


def create_exam_taking_router(session_factory=None) -> APIRouter:
    """Router de lectura de examen para la rendición del alumno (C-69, D3).

    GET /            : cualquier principal autenticado lista los exámenes importados
                       con id, titulo y cantidad_preguntas (catálogo del alumno).
    GET /{examen_id} : cualquier principal autenticado obtiene preguntas+opciones
                       en orden estable, SIN es_correcta (D3).
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
        )

        async with session_factory() as session:
            repo = ExamenContenidoSqlRepository(session)
            resumenes, total = await repo.listar_paginado(
                q=q, page=page, page_size=page_size
            )

        return ExamenesContenidoPaginadosResponse(
            items=[_resumen_to_response(r) for r in resumenes],
            total=total,
            page=max(1, page),
            page_size=max(1, page_size),
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
            MateriaSqlRepository,
        )

        async with session_factory() as session:
            materias = await MateriaSqlRepository(session).listar()

        return [
            MateriaResponse(id=m.id, codigo=m.codigo, nombre=m.nombre) for m in materias
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
        )

        async with session_factory() as session:
            comisiones = await ComisionSqlRepository(session).listar_por_materia(
                materia_id
            )

        return [
            ComisionResponse(
                id=c.id,
                materia_id=c.materia_id,
                codigo=c.codigo,
                nombre=c.nombre,
                periodo=c.periodo,
                anio=c.anio,
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
            ExamenContenidoSqlRepository,
        )

        async with session_factory() as session:
            repo = ExamenContenidoSqlRepository(session)
            service = LecturaExamenService(repo)
            rendicion = await service.obtener_para_rendir(examen_id)

        if rendicion is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "examen_no_encontrado", "examen_id": examen_id},
            )

        return ExamenRendicionResponse(
            id=rendicion.id,
            titulo=rendicion.titulo,
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
