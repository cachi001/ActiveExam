"""Router de gestión del catálogo académico (exam_content, C-69) — admin-only.

Materias, comisiones, exámenes de contenido (import Moodle XML), config por examen,
destino Moodle y sincronización manual de resultados. Requiere roles de gestión
(guard a nivel router). Extraído de router.py al partir el god-file en sub-routers.
"""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)

from app.application.audit.service import registrar_seguro
from app.application.audit.acciones import AccionAuditoria
from app.domain.auth.identity import AuthenticatedPrincipal

from app.application.exam_content.asociacion_service import AsociacionComisionService
from app.application.exam_content.errors import (
    ComisionNoEncontradaError,
    ComisionNoVaciaError,
    ExamenNoEncontradoError,
    InscripcionConActividadError,
    InscripcionNoEncontradaError,
    MateriaNoEncontradaError,
    MateriaNoVaciaError,
    MoodleXmlInvalidoError,
    MoodleXmlVacioError,
    UsuarioNoEncontradoError,
)
from app.application.exam_content.import_service import ImportacionMoodleService
from app.application.exam_content.inscripcion_service import (
    InscripcionService,
)
from app.application.exam_content.materia_comision_service import (
    MateriaComisionService,
)
from app.application.moodle.resultados_query import (
    listar_estados_sincronizables,
    listar_resultados_examen,
)
from app.application.moodle.writeback_service import (
    MoodleWritebackService,
    WritebackEstado,
)
from app.domain.auth.roles import Rol
from app.domain.exam_content.config import (
    cambios_bloqueados,
    validar_config_examen,
)
from app.domain.exam_content.entities import Materia
from app.domain.exam_content.errors import (
    CodigoMatriculacionDuplicadoError,
    ComisionDuplicadaError,
    ConfigExamenInvalidaError,
    ExamenContenidoError,
    InscripcionDuplicadaError,
    MateriaDuplicadaError,
    SeleccionInvalidaError,
)
from app.presentation.api.v1.auth.dependencies import (
    get_current_principal,
    require_capability,
)
from app.presentation.api.v1.exam_content.schemas import (
    AltaInlineRequest,
    AltaInlineResponse,
    AlumnoElegibilidadResponse,
    AsociarComisionRequest,
    AsociarComisionResponse,
    ComisionActivaRequest,
    ComisionActualizarRequest,
    ComisionCrearRequest,
    ComisionResponse,
    ExamenConfigPatchRequest,
    ExamenConfigResponse,
    ImportReporteResponse,
    InscribirAlumnoRequest,
    InscripcionResponse,
    MateriaActivaRequest,
    MateriaActualizarRequest,
    MateriaCrearRequest,
    MateriaResponse,
    MoodleTargetRequest,
    MoodleTargetResponse,
    OmitidaItemResponse,
    PreguntaPoolItemResponse,
    PreguntasPoolResponse,
    PreguntasSeleccionRequest,
    ResultadoAlumnoResponse,
    ResultadosExamenPaginadosResponse,
    SincronizarMoodleResponse,
)


async def _titulo_examen(session_factory, examen_id: str) -> str:
    """Titulo visible del examen para los mensajes de auditoria.

    El audit log lo lee una PERSONA: un UUID no le dice nada. Cae al id solo si el
    examen no existe (no vale romper una auditoria por no poder leer un nombre).
    """
    from sqlalchemy import select

    from app.infrastructure.persistence.models.exam_content import (
        ExamenContenidoModel,
    )

    try:
        async with session_factory() as session:
            titulo = (
                await session.execute(
                    select(ExamenContenidoModel.titulo).where(
                        ExamenContenidoModel.id == examen_id
                    )
                )
            ).scalar_one_or_none()
        return titulo or examen_id
    except Exception:  # noqa: BLE001 — nunca romper el flujo por el nombre
        return examen_id


def create_exam_content_router(
    session_factory=None,
    *,
    writeback_svc: MoodleWritebackService | None = None,
) -> APIRouter:
    """Factory que permite inyectar session_factory en tests.

    writeback_svc: servicio de write-back a Moodle (None = Moodle no configurado;
    la sincronización manual responde 'sin_token' sin crashear).
    """
    # Gate por CAPACIDAD, no por lista de roles: el catalogo academico (examenes,
    # materias, comisiones, notas) lo maneja quien tiene `gestionar_academico` —
    # hoy docente, admin_examenes, coordinador y admin_sistema. Con la lista
    # hardcodeada anterior el docente veia las pantallas pero comia 403 al operar,
    # que es el mismo desfasaje que dejaba la cola de revision inalcanzable.
    router = APIRouter(
        dependencies=[
            Depends(require_capability("gestionar_academico")),
        ]
    )

    async def _get_service(request) -> ImportacionMoodleService:

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
        request: Request,
        file: UploadFile = File(...),
        titulo: str | None = Form(default=None),
        moodle_courseid: int | None = Form(default=None),
        moodle_cmid: int | None = Form(default=None),
        moodle_component: str | None = Form(default=None),
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> ImportReporteResponse:
        """Importa un archivo Moodle XML y crea el examen de contenido.

        D12 (parte B): moodle_courseid/moodle_cmid son opcionales y fijan el destino
        del write-back de nota POR EXAMEN. Si se omiten, el write-back usa el global.
        C-73: moodle_component ('mod_assign'|'mod_quiz') idem — omitido usa el global.
        """

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
                    moodle_component=moodle_component,
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

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.EXAMEN_IMPORTACION,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=f"Cargó el examen «{titulo or 'sin título'}» ({report.importadas} preguntas)",
        )

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
                activa=result.materia.activa,
            ),
            comision=ComisionResponse(
                id=result.comision.id,
                materia_id=result.comision.materia_id,
                codigo=result.comision.codigo,
                nombre=result.comision.nombre,
                periodo=result.comision.periodo,
                anio=result.comision.anio,
                codigo_matriculacion=result.comision.codigo_matriculacion,
                activa=result.comision.activa,
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
    # CRUD de Materias y Comisiones (C-69 sección 6, D11) — admin-only, SIN MFA.
    # Gestión INDEPENDIENTE del import de examen: dar de alta/editar materias y
    # comisiones sin reimportar contenido. No hay DELETE (riesgo de FK). El codigo
    # es inmutable (identidad académica). Errores: duplicado→409, validación→422,
    # no-encontrada→404. Capa router→service→repo (reusa repos/errores existentes).
    # -----------------------------------------------------------------------

    def _build_materia_comision_service(session) -> MateriaComisionService:
        from app.infrastructure.persistence.repositories.exam_content import (
            ComisionSqlRepository,
            MateriaSqlRepository,
        )

        return MateriaComisionService(
            materia_repo=MateriaSqlRepository(session),
            comision_repo=ComisionSqlRepository(session),
        )

    @router.post(
        "/materias",
        response_model=MateriaResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Crear una materia (gestión independiente del import)",
    )
    async def crear_materia(
        body: MateriaCrearRequest,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> MateriaResponse:
        """Crea una materia. 409 'duplicado' si el codigo ya existe; 422
        'validacion_dominio' si codigo/nombre son vacíos o inválidos."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        async with session_factory() as session:
            service = _build_materia_comision_service(session)
            try:
                materia = await service.crear_materia(body.codigo, body.nombre)
                await session.commit()
            except MateriaDuplicadaError as exc:
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

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.MATERIA_ALTA,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=f"Creó la materia {materia.nombre} ({materia.codigo})",
        )

        return MateriaResponse(
            id=materia.id, codigo=materia.codigo, nombre=materia.nombre, activa=materia.activa
        )

    @router.patch(
        "/materias/{materia_id}",
        response_model=MateriaResponse,
        summary="Actualizar nombre y/o codigo de una materia",
    )
    async def actualizar_materia(
        materia_id: str,
        body: MateriaActualizarRequest,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> MateriaResponse:
        """Actualiza el nombre y (opcionalmente) el codigo de una materia. 404
        'materia_no_encontrada' si no existe; 409 'duplicado' si el codigo nuevo ya
        está en uso; 422 'validacion_dominio' si nombre/codigo son vacíos."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        async with session_factory() as session:
            service = _build_materia_comision_service(session)
            try:
                materia = await service.actualizar_materia(
                    materia_id, body.nombre, body.codigo
                )
                await session.commit()
            except MateriaNoEncontradaError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "materia_no_encontrada",
                        "materia_id": materia_id,
                    },
                ) from exc
            except MateriaDuplicadaError as exc:
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

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.MATERIA_EDICION,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=f"Editó la materia {materia.nombre} ({materia.codigo})",
        )

        return MateriaResponse(
            id=materia.id, codigo=materia.codigo, nombre=materia.nombre, activa=materia.activa
        )

    @router.delete(
        "/materias/{materia_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        response_model=None,
        summary="Eliminar una materia (solo si está 100% vacía)",
    )
    async def eliminar_materia(
        materia_id: str,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> None:
        """Elimina una materia SOLO si no tiene inscriptos ni exámenes. 404 si no
        existe; 409 'materia_no_vacia' si tiene contenido (se sugiere desactivar)."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        async with session_factory() as session:
            service = _build_materia_comision_service(session)
            try:
                await service.eliminar_materia(materia_id)
                await session.commit()
            except MateriaNoEncontradaError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "materia_no_encontrada", "materia_id": materia_id},
                ) from exc
            except MateriaNoVaciaError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error": "materia_no_vacia", "mensaje": str(exc)},
                ) from exc

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.MATERIA_BAJA,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=f"Eliminó la materia {materia_id}",
        )

    @router.patch(
        "/materias/{materia_id}/activa",
        response_model=MateriaResponse,
        summary="Activar o desactivar una materia (freeze)",
    )
    async def set_activa_materia(
        materia_id: str,
        body: MateriaActivaRequest,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> MateriaResponse:
        """Activa (true) o desactiva (false) una materia. Desactivar = congelar:
        corta inscripciones nuevas y bloquea iniciar rendición. 404 si no existe."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        async with session_factory() as session:
            service = _build_materia_comision_service(session)
            try:
                materia = await service.set_activa(materia_id, body.activa)
                await session.commit()
            except MateriaNoEncontradaError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "materia_no_encontrada", "materia_id": materia_id},
                ) from exc

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.MATERIA_ACTIVACION,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=f"{'Activó' if body.activa else 'Desactivó'} la materia {materia.nombre}",
        )

        return MateriaResponse(
            id=materia.id,
            codigo=materia.codigo,
            nombre=materia.nombre,
            activa=materia.activa,
        )

    @router.post(
        "/materias/{materia_id}/comisiones",
        response_model=ComisionResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Crear una comisión dentro de una materia",
    )
    async def crear_comision(
        materia_id: str,
        body: ComisionCrearRequest,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> ComisionResponse:
        """Crea una comisión en la materia. 404 'materia_no_encontrada' si la materia
        no existe; 409 'duplicado' si (materia_id, codigo) ya existe; 422
        'validacion_dominio' si codigo/nombre son vacíos."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        async with session_factory() as session:
            service = _build_materia_comision_service(session)
            try:
                comision = await service.crear_comision(
                    materia_id=materia_id,
                    codigo=body.codigo,
                    nombre=body.nombre,
                    periodo=body.periodo,
                    anio=body.anio,
                    codigo_matriculacion=body.codigo_matriculacion,
                )
                await session.commit()
            except MateriaNoEncontradaError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "materia_no_encontrada",
                        "materia_id": materia_id,
                    },
                ) from exc
            except (ComisionDuplicadaError, CodigoMatriculacionDuplicadoError) as exc:
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

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.COMISION_ALTA,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=f"Creó la comisión {comision.nombre} ({comision.codigo})",
        )

        return ComisionResponse(
            id=comision.id,
            materia_id=comision.materia_id,
            codigo=comision.codigo,
            nombre=comision.nombre,
            periodo=comision.periodo,
            anio=comision.anio,
            codigo_matriculacion=comision.codigo_matriculacion,
            activa=comision.activa,
        )

    @router.patch(
        "/comisiones/{comision_id}",
        response_model=ComisionResponse,
        summary="Actualizar nombre/periodo/anio de una comisión (codigo inmutable)",
    )
    async def actualizar_comision(
        comision_id: str,
        body: ComisionActualizarRequest,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> ComisionResponse:
        """Actualiza nombre/periodo/anio de una comisión. 404 'comision_no_encontrada'
        si no existe; 422 'validacion_dominio' si el nombre es vacío. El codigo y la
        materia NO se tocan."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        async with session_factory() as session:
            service = _build_materia_comision_service(session)
            try:
                comision = await service.actualizar_comision(
                    comision_id=comision_id,
                    nombre=body.nombre,
                    periodo=body.periodo,
                    anio=body.anio,
                    codigo_matriculacion=body.codigo_matriculacion,
                )
                await session.commit()
            except ComisionNoEncontradaError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "comision_no_encontrada",
                        "comision_id": comision_id,
                    },
                ) from exc
            except CodigoMatriculacionDuplicadoError as exc:
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

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.COMISION_EDICION,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=f"Editó la comisión {comision.nombre} ({comision.codigo})",
        )

        return ComisionResponse(
            id=comision.id,
            materia_id=comision.materia_id,
            codigo=comision.codigo,
            nombre=comision.nombre,
            periodo=comision.periodo,
            anio=comision.anio,
            codigo_matriculacion=comision.codigo_matriculacion,
            activa=comision.activa,
        )

    @router.patch(
        "/comisiones/{comision_id}/activa",
        response_model=ComisionResponse,
        summary="Activar o desactivar una comisión (baja lógica / freeze)",
    )
    async def set_activa_comision(
        comision_id: str,
        body: ComisionActivaRequest,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> ComisionResponse:
        """Activa (true) o desactiva (false) una comisión. Desactivar = congelar SOLO
        esa comisión: corta inscripciones nuevas por su código y bloquea iniciar sus
        exámenes; la materia y las demás comisiones siguen igual. No desmatricula a
        nadie. Es la alternativa al DELETE cuando la comisión no está vacía. 404 si no
        existe."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        async with session_factory() as session:
            service = _build_materia_comision_service(session)
            try:
                comision = await service.set_activa_comision(comision_id, body.activa)
                await session.commit()
            except ComisionNoEncontradaError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "comision_no_encontrada",
                        "comision_id": comision_id,
                    },
                ) from exc

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.COMISION_ACTIVACION,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"{'Activó' if body.activa else 'Desactivó'} la comisión "
                f"{comision.nombre} ({comision.codigo})"
            ),
        )

        return ComisionResponse(
            id=comision.id,
            materia_id=comision.materia_id,
            codigo=comision.codigo,
            nombre=comision.nombre,
            periodo=comision.periodo,
            anio=comision.anio,
            codigo_matriculacion=comision.codigo_matriculacion,
            activa=comision.activa,
        )

    @router.delete(
        "/comisiones/{comision_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        response_model=None,
        summary="Eliminar una comisión (solo si está vacía)",
    )
    async def eliminar_comision(
        comision_id: str,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> None:
        """Elimina una comisión SOLO si no tiene inscriptos ni exámenes. 404 si no
        existe; 409 'comision_no_vacia' si tiene contenido."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        async with session_factory() as session:
            service = _build_materia_comision_service(session)
            try:
                await service.eliminar_comision(comision_id)
                await session.commit()
            except ComisionNoEncontradaError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "comision_no_encontrada",
                        "comision_id": comision_id,
                    },
                ) from exc
            except ComisionNoVaciaError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error": "comision_no_vacia", "mensaje": str(exc)},
                ) from exc

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.COMISION_BAJA,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=f"Eliminó la comisión {comision_id}",
        )

    # -----------------------------------------------------------------------
    # Rotación del código de matriculación (C-70, D5) — admin-only.
    # Regenera un código único y reemplaza el anterior; las inscripciones
    # existentes quedan INTACTAS (rotar no desmatricula a nadie).
    # -----------------------------------------------------------------------

    @router.post(
        "/comisiones/{comision_id}/rotar-codigo",
        response_model=ComisionResponse,
        status_code=status.HTTP_200_OK,
        summary="Rotar (regenerar) el código de matriculación de una comisión",
    )
    async def rotar_codigo_matriculacion(comision_id: str) -> ComisionResponse:
        """Genera un nuevo código único y reemplaza el vigente. 404 si la comisión
        no existe. Las inscripciones existentes NO se tocan."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        async with session_factory() as session:
            service = _build_materia_comision_service(session)
            try:
                comision = await service.rotar_codigo_matriculacion(comision_id)
                await session.commit()
            except ComisionNoEncontradaError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "comision_no_encontrada",
                        "comision_id": comision_id,
                    },
                ) from exc

        return ComisionResponse(
            id=comision.id,
            materia_id=comision.materia_id,
            codigo=comision.codigo,
            nombre=comision.nombre,
            periodo=comision.periodo,
            anio=comision.anio,
            codigo_matriculacion=comision.codigo_matriculacion,
            activa=comision.activa,
        )

    # -----------------------------------------------------------------------
    # Inscripción de alumnos a comisiones + elegibilidad (C-69) — admin-only.
    # Inscribe/da de baja alumnos a una comisión y lista los inscriptos con su
    # elegibilidad ("puede rendir" = consentimiento vigente + biometría vigente),
    # resuelta server-side (cliente = sensor no confiable). El picker de alumnos
    # del front reusa el GET /users?rol=estudiante existente. Capa router→service→repo.
    # -----------------------------------------------------------------------

    def _build_inscripcion_service(session) -> InscripcionService:
        from app.infrastructure.persistence.repositories.biometric_reference import (
            EmbeddingReferenciaRepository,
        )
        from app.infrastructure.persistence.repositories.consent_perfil import (
            ConsentimientoPerfilSqlRepository,
        )
        from app.infrastructure.persistence.repositories.exam_content import (
            ComisionSqlRepository,
            InscripcionSqlRepository,
        )

        return InscripcionService(
            inscripcion_repo=InscripcionSqlRepository(session),
            comision_repo=ComisionSqlRepository(session),
            consent_repo=ConsentimientoPerfilSqlRepository(session),
            embedding_repo=EmbeddingReferenciaRepository(session),
        )

    @router.post(
        "/comisiones/{comision_id}/inscripciones",
        response_model=InscripcionResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Inscribir un alumno a una comisión",
    )
    async def inscribir_alumno(
        comision_id: str,
        body: InscribirAlumnoRequest,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> InscripcionResponse:
        """Inscribe un alumno a una comisión.

        404 'comision_no_encontrada' si la comisión no existe; 404
        'usuario_no_encontrado' si el alumno no existe (o está dado de baja);
        409 'duplicado' si el alumno ya está inscripto a esa comisión.
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        async with session_factory() as session:
            service = _build_inscripcion_service(session)
            try:
                inscripcion = await service.inscribir(comision_id, body.usuario_id)
                await session.commit()
            except ComisionNoEncontradaError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "comision_no_encontrada", "comision_id": comision_id},
                ) from exc
            except UsuarioNoEncontradoError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "usuario_no_encontrado", "usuario_id": body.usuario_id},
                ) from exc
            except InscripcionDuplicadaError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error": "duplicado", "mensaje": str(exc)},
                ) from exc

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.INSCRIPCION_ALTA,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=f"Inscribió al alumno {body.usuario_id} en la comisión {comision_id}",
        )

        return InscripcionResponse(
            id=inscripcion.id,
            usuario_id=inscripcion.usuario_id,
            comision_id=inscripcion.comision_id,
        )

    @router.delete(
        "/comisiones/{comision_id}/inscripciones/{usuario_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        response_model=None,
        summary="Eliminar la inscripción de un alumno a una comisión",
    )
    async def eliminar_inscripcion(
        comision_id: str,
        usuario_id: str,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> None:
        """Da de baja la inscripción del alumno a la comisión.

        204 si se eliminó; 404 'inscripcion_no_encontrada' si no existía.
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        async with session_factory() as session:
            service = _build_inscripcion_service(session)
            try:
                await service.eliminar(comision_id, usuario_id)
                await session.commit()
            except InscripcionConActividadError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "inscripcion_con_actividad",
                        "mensaje": (
                            "El alumno ya rindió en esta comisión. No se puede dar de "
                            "baja la inscripción para no perder la evidencia de su examen."
                        ),
                        "comision_id": comision_id,
                        "usuario_id": usuario_id,
                    },
                ) from exc
            except InscripcionNoEncontradaError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "inscripcion_no_encontrada",
                        "comision_id": comision_id,
                        "usuario_id": usuario_id,
                    },
                ) from exc

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.INSCRIPCION_BAJA,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=f"Quitó al alumno {usuario_id} de la comisión {comision_id}",
        )

    @router.get(
        "/comisiones/{comision_id}/alumnos",
        response_model=list[AlumnoElegibilidadResponse],
        summary="Listar los inscriptos de una comisión con su elegibilidad para rendir",
    )
    async def listar_alumnos_de_comision(
        comision_id: str,
    ) -> list[AlumnoElegibilidadResponse]:
        """Lista los alumnos inscriptos a la comisión con su elegibilidad.

        Por cada alumno: puede_rendir = consentimiento vigente + biometría vigente
        (resuelto server-side); razon describe qué falta cuando no puede. 404
        'comision_no_encontrada' si la comisión no existe.
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        async with session_factory() as session:
            service = _build_inscripcion_service(session)
            try:
                alumnos = await service.listar_alumnos_con_elegibilidad(comision_id)
            except ComisionNoEncontradaError as exc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "comision_no_encontrada", "comision_id": comision_id},
                ) from exc

        return [
            AlumnoElegibilidadResponse(
                usuario_id=a.usuario_id,
                id_institucional=a.id_institucional,
                nombre=a.nombre,
                apellido=a.apellido,
                email=a.email,
                consentimiento_vigente=a.consentimiento_vigente,
                biometria_vigente=a.biometria_vigente,
                puede_rendir=a.puede_rendir,
                razon=a.razon,
            )
            for a in alumnos
        ]

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
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
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

        # El destino Moodle decide a qué libreta va la nota → se audita (cadena de custodia).
        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.EXAMEN_MOODLE_TARGET,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            # El registro lo lee una persona: va el TITULO del examen, no su UUID.
            # `titulo` es el nombre visible; si el objeto no lo trae, cae al id.
            proposito=(
                f"Fijó destino Moodle del examen «{getattr(examen, 'titulo', None) or examen_id}»: "
                f"curso {examen.moodle_courseid}, actividad {examen.moodle_cmid}"
            ),
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
    # Configuración del examen POR EXAMEN (C-69, migración 0032) — admin-only.
    # ActiveExam opera estos 7 campos; el alumno rinde con ellos. GET lee la
    # config; PATCH la actualiza parcialmente (extra='forbid', validaciones → 422).
    # -----------------------------------------------------------------------

    def _config_to_response(examen, *, bloqueada: bool = False) -> ExamenConfigResponse:
        # C-72 sección 6: si ya fue rendido, expone el detalle direccional para la UI.
        from app.domain.exam_content.config import (
            CAMPOS_SOLO_AMPLIABLES,
            CONGELADO_DURO,
        )

        return ExamenConfigResponse(
            tiempo_limite_min=examen.tiempo_limite_min,
            intentos_permitidos=examen.intentos_permitidos,
            apertura=examen.apertura,
            cierre=examen.cierre,
            nota_maxima=examen.nota_maxima,
            nota_aprobacion=examen.nota_aprobacion,
            mezclar_preguntas=examen.mezclar_preguntas,
            mostrar_nota=examen.mostrar_nota,
            revision_habilitada=examen.revision_habilitada,
            bloqueada=bloqueada,
            campos_congelados=sorted(CONGELADO_DURO) if bloqueada else [],
            campos_solo_ampliables=sorted(CAMPOS_SOLO_AMPLIABLES) if bloqueada else [],
        )

    @router.get(
        "/{examen_id}/config",
        response_model=ExamenConfigResponse,
        summary="Leer la configuración POR EXAMEN (timer/ventana/intentos/nota/shuffle)",
    )
    async def leer_config_examen(examen_id: str) -> ExamenConfigResponse:
        """Devuelve los 7 campos de configuración del examen. 404 si no existe."""
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
            ya_rendido = await _seleccion_bloqueada(session, examen_id)

        return _config_to_response(examen, bloqueada=ya_rendido)

    @router.patch(
        "/{examen_id}/config",
        response_model=ExamenConfigResponse,
        summary="Actualizar (parcial) la configuración POR EXAMEN del examen",
    )
    async def actualizar_config_examen(
        examen_id: str,
        body: ExamenConfigPatchRequest,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> ExamenConfigResponse:
        """Actualiza parcialmente los 7 campos de config (solo los presentes).

        Valida el resultado mergeado (config actual + cambios) — 422 ante:
        intentos_permitidos < 1; nota_maxima <= 0; nota_aprobacion fuera de
        [0, nota_maxima]; apertura >= cierre (si ambos seteados); tiempo_limite_min
        <= 0. 404 si el examen no existe.
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        from app.infrastructure.persistence.repositories.exam_content import (
            ExamenContenidoSqlRepository,
        )

        # Solo los campos REALMENTE enviados (distingue "ausente" de "null explícito").
        cambios = body.model_dump(exclude_unset=True)

        async with session_factory() as session:
            repo = ExamenContenidoSqlRepository(session)
            actual = await repo.obtener(examen_id)
            if actual is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "examen_no_encontrado", "examen_id": examen_id},
                )

            # Candado: si el examen ya tiene >= 1 intento finalizado, los campos
            # de mecánica/nota quedan CONGELADOS (cambiarlos alteraría notas ya
            # calculadas / la equidad de quienes rindieron).
            ya_rendido = await _seleccion_bloqueada(session, examen_id)
            # Candado DIRECCIONAL (C-72 §6 + §18): congelado duro (nota/mecánica) →
            # siempre bloqueado; direccionales solo se pueden AFLOJAR — `cierre` solo
            # EXTENDER, `intentos_permitidos` solo AUMENTAR, `revision_habilitada` solo
            # HABILITAR, `mostrar_nota` solo MOSTRAR ANTES (apretar perjudica a quien ya
            # rindió). Compara contra el valor vigente.
            vigente = {campo: getattr(actual, campo) for campo in cambios}
            congelados = cambios_bloqueados(
                cambios=cambios, vigente=vigente, ya_rendido=ya_rendido
            )
            if congelados:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "config_congelada",
                        "mensaje": (
                            "El examen ya tiene intentos finalizados. No se pueden "
                            "modificar los campos de mecánica/nota, ni cambiar en la "
                            "dirección que perjudica a quien ya rindió "
                            f"({', '.join(sorted(congelados))}). Sí se puede AFLOJAR: "
                            "extender el cierre, aumentar los intentos, habilitar la "
                            "revisión o mostrar la nota antes."
                        ),
                        "campos": sorted(congelados),
                    },
                )

            # Merge: campo enviado → su valor; ausente → el valor actual del examen.
            def _merged(campo: str):
                return cambios[campo] if campo in cambios else getattr(actual, campo)

            try:
                validar_config_examen(
                    tiempo_limite_min=_merged("tiempo_limite_min"),
                    intentos_permitidos=_merged("intentos_permitidos"),
                    apertura=_merged("apertura"),
                    cierre=_merged("cierre"),
                    nota_maxima=_merged("nota_maxima"),
                    nota_aprobacion=_merged("nota_aprobacion"),
                )
            except ConfigExamenInvalidaError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": "config_invalida", "mensaje": str(exc)},
                ) from exc

            examen = await repo.actualizar_config(examen_id, cambios)
            await session.commit()

        # La config define mecánica/nota del examen → cambios auditados (qué campos).
        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.EXAMEN_CONFIG_ACTUALIZACION,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"Actualizó config del examen {examen_id}: "
                f"{', '.join(sorted(cambios)) or '(sin cambios)'}"
            ),
        )

        return _config_to_response(examen, bloqueada=ya_rendido)

    # -----------------------------------------------------------------------
    # Pool de preguntas seleccionables (C-69, opción B) — admin-only, SIN MFA.
    # El examen importado es un POOL; el docente elige CUÁLES preguntas lo forman.
    # GET   /{examen_id}/preguntas            → todo el pool (seleccionadas y no).
    # PATCH /{examen_id}/preguntas-seleccion  → fija la selección (>= 1, 422 si 0).
    # D3: es_correcta NUNCA viaja; el docente identifica la pregunta por enunciado.
    # -----------------------------------------------------------------------

    def _pool_to_response(items, bloqueada: bool = False) -> PreguntasPoolResponse:
        return PreguntasPoolResponse(
            items=[
                PreguntaPoolItemResponse(
                    id=p.id,
                    enunciado=p.enunciado,
                    tipo=p.tipo,
                    orden=p.orden,
                    seleccionada=p.seleccionada,
                )
                for p in items
            ],
            total=len(items),
            seleccionadas=sum(1 for p in items if p.seleccionada),
            bloqueada=bloqueada,
        )

    async def _seleccion_bloqueada(session, examen_id: str) -> bool:
        """True si el examen ya tiene >= 1 intento FINALIZADO.

        Regla de negocio (política elegida): la selección de preguntas se puede
        editar libremente hasta que un alumno finaliza un intento; a partir de ahí
        queda CONGELADA. Cambiarla después alteraría retroactivamente la nota —
        grade_calculator cuenta solo las preguntas seleccionadas (opción B).
        """
        from sqlalchemy import select as _select

        from app.infrastructure.persistence.models.proctoring import (
            ProctoringSessionModel,
        )

        row = await session.execute(
            _select(ProctoringSessionModel.id)
            .where(
                ProctoringSessionModel.examen_contenido_id == examen_id,
                ProctoringSessionModel.finalizada_en.isnot(None),
            )
            .limit(1)
        )
        return row.first() is not None

    @router.get(
        "/{examen_id}/preguntas",
        response_model=PreguntasPoolResponse,
        summary="Listar el pool de preguntas de un examen (seleccionadas y no)",
    )
    async def listar_preguntas_pool(examen_id: str) -> PreguntasPoolResponse:
        """Devuelve TODO el pool del examen para la pantalla de selección del docente.

        D3: sin es_correcta ni opciones — el docente identifica por enunciado.
        404 si el examen no existe.
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
            items = await ExamenContenidoSqlRepository(session).listar_preguntas(
                examen_id
            )
            if items is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "examen_no_encontrado", "examen_id": examen_id},
                )
            bloqueada = await _seleccion_bloqueada(session, examen_id)

        return _pool_to_response(items, bloqueada=bloqueada)

    @router.patch(
        "/{examen_id}/preguntas-seleccion",
        response_model=PreguntasPoolResponse,
        summary="Fijar qué preguntas del pool forman el examen (opción B)",
    )
    async def fijar_seleccion_preguntas(
        examen_id: str,
        body: PreguntasSeleccionRequest,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> PreguntasPoolResponse:
        """Marca seleccionada=true para los ids dados, false para el resto del pool.

        Valida >= 1 pregunta seleccionada (422 si la lista queda sin ids válidos).
        Ignora ids que no pertenezcan a este examen. 404 si el examen no existe.
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
            # Candado: si ya hay un intento finalizado, la selección está congelada.
            # 409 (no 422): no es un body inválido, es un conflicto con el estado del
            # examen (ya se calcularon notas sobre la selección vigente).
            if await _seleccion_bloqueada(session, examen_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "seleccion_bloqueada",
                        "mensaje": (
                            "No se puede cambiar la selección de preguntas: este examen "
                            "ya tiene intentos finalizados y cambiarla alteraría notas ya "
                            "calculadas."
                        ),
                    },
                )
            try:
                items = await repo.actualizar_seleccion(examen_id, body.seleccionadas)
            except SeleccionInvalidaError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": "seleccion_invalida", "mensaje": str(exc)},
                ) from exc
            if items is None:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "examen_no_encontrado", "examen_id": examen_id},
                )
            await session.commit()

        # La selección determina QUÉ preguntas forman el examen → cambio auditado.
        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.EXAMEN_SELECCION_PREGUNTAS,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"Fijó la selección de preguntas del examen {examen_id}: "
                f"{len(body.seleccionadas)} seleccionada(s)"
            ),
        )

        return _pool_to_response(items)

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
                    retenido_por=r.retenido_por,
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
    async def sincronizar_moodle(
        examen_id: str,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> SincronizarMoodleResponse:
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

        # El titulo, para que la auditoria la lea una persona y no un UUID.
        titulo_examen = await _titulo_examen(session_factory, examen_id)

        async with session_factory() as session:
            pendientes = await listar_estados_sincronizables(
                db=session, examen_id=examen_id
            )
            total = len(pendientes)

            # Moodle no configurado: no se puede enviar. No crashea — sin_token.
            if writeback_svc is None:
                # Auditar el INTENTO: hubo una acción humana de sincronización aunque
                # no se escribiera ninguna nota (sin token). Trazabilidad L2.5.
                await registrar_seguro(
                    session_factory,
                    actor=principal.email,
                    accion=AccionAuditoria.MOODLE_SYNC,
                    ip=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    proposito=(
                        f"Intentó sincronizar las notas del examen «{titulo_examen}» a Moodle sin token "
                        f"configurado ({total} nota(s) quedan pendientes)"
                    ),
                )
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

        # Se ESCRIBIERON notas académicas reales en Moodle → cadena de custodia
        # (regla dura #6, L2.5): queda quién sincronizó, qué examen y el resultado.
        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.MOODLE_SYNC,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"Sincronizó las notas del examen «{titulo_examen}» a Moodle: "
                f"{enviadas} enviada(s), {fallidas} fallida(s) de {total}"
            ),
        )

        return SincronizarMoodleResponse(
            enviadas=enviadas,
            fallidas=fallidas,
            sin_token=0,
            total=total,
        )

    return router
