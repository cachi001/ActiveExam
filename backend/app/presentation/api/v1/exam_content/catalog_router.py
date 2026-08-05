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
from app.application.audit.acciones import AccionAuditoria, ModuloAuditoria
from app.domain.auth.identity import AuthenticatedPrincipal

from app.application.exam_content.asociacion_service import AsociacionComisionService
from app.application.exam_content.errors import (
    ComisionNoEncontradaError,
    ComisionNoVaciaError,
    ExamenNoEncontradoError,
    InscripcionConActividadError,
    InscripcionNoEncontradaError,
    LimitePreguntasExcedidoError,
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
from app.domain.exam_content.entities import Materia, PoliticaIntentos
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
    ComisionDocenteRequest,
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
    SorteoRequest,
    ResultadosExamenPaginadosResponse,
    SincronizarMoodleResponse,
    SyncBancoRequest,
    SyncBancoResponse,
    CrearDesdebancoRequest,
    CrearDesdebancoResponse,
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
        materia_id: str | None = Form(default=None),
        moodle_courseid: int | None = Form(default=None),
        moodle_cmid: int | None = Form(default=None),
        moodle_component: str | None = Form(default=None),
        limite_preguntas: int | None = Form(default=None, ge=1),
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
                    materia_id=materia_id,
                    moodle_courseid=moodle_courseid,
                    moodle_cmid=moodle_cmid,
                    moodle_component=moodle_component,
                    limite_preguntas=limite_preguntas,
                )
                await session.commit()
            except LimitePreguntasExcedidoError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "limite_preguntas_excedido",
                        "mensaje": str(exc),
                        "importables": exc.importables,
                        "limite": exc.limite,
                    },
                ) from exc
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
            modulo=ModuloAuditoria.EXAMENES,
            entidad_id=str(report.examen_id),
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
            modulo=ModuloAuditoria.MATERIAS,
            entidad_id=str(materia.id),
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
            modulo=ModuloAuditoria.MATERIAS,
            entidad_id=str(materia_id),
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
            modulo=ModuloAuditoria.MATERIAS,
            entidad_id=str(materia_id),
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
            modulo=ModuloAuditoria.MATERIAS,
            entidad_id=str(materia_id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"La materia {materia.nombre} pasó de "
                f"{'Inactiva a Activa' if body.activa else 'Activa a Inactiva'}"
            ),
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
            modulo=ModuloAuditoria.MATERIAS,
            entidad_id=str(comision.id),
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
            modulo=ModuloAuditoria.MATERIAS,
            entidad_id=str(comision_id),
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
                f"La comisión {comision.nombre} ({comision.codigo}) pasó de "
                f"{'Inactiva a Activa' if body.activa else 'Activa a Inactiva'}"
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

    @router.put(
        "/comisiones/{comision_id}/docente",
        response_model=ComisionResponse,
        summary="Asignar (o desasignar) el docente a cargo de una comisión",
    )
    async def asignar_docente_comision(
        comision_id: str,
        body: ComisionDocenteRequest,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(
            require_capability("asignar_docente")
        ),
    ) -> ComisionResponse:
        """Fija el docente a cargo. ``docente_id=null`` desasigna (C-73 §9).

        Requiere la capacidad `asignar_docente`, que NO tiene el rol DOCENTE: si un
        docente pudiera asignarse a sí mismo, la validación de pertenencia dejaría de
        ser un control.

        404 si la comisión no existe. 422 si el usuario no existe, está dado de baja, o
        no tiene rol docente — poner a cargo a alguien que no dicta la materia haría
        que la nota se devuelva con una identidad equivocada."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        from sqlalchemy import select

        from app.infrastructure.persistence.models.transactional import UsuarioModel
        from app.infrastructure.persistence.repositories.exam_content import (
            ComisionSqlRepository,
        )

        async with session_factory() as session:
            if body.docente_id is not None:
                usuario = (
                    await session.execute(
                        select(UsuarioModel).where(UsuarioModel.id == body.docente_id)
                    )
                ).scalar_one_or_none()
                if usuario is None or usuario.eliminado_en is not None:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={
                            "error": "docente_invalido",
                            "mensaje": "El usuario no existe o está dado de baja.",
                        },
                    )
                if Rol.DOCENTE.value not in (usuario.roles or []):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={
                            "error": "no_es_docente",
                            "mensaje": "El usuario no tiene rol docente.",
                        },
                    )

            repo = ComisionSqlRepository(session)
            comision = await repo.asignar_docente(comision_id, body.docente_id)
            if comision is None:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "comision_no_encontrada",
                        "comision_id": comision_id,
                    },
                )
            nombres = await repo.nombres_de_docentes(
                [comision.docente_id] if comision.docente_id else []
            )
            await session.commit()

        nombre_docente = nombres.get(comision.docente_id or "")
        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.COMISION_DOCENTE,
            modulo=ModuloAuditoria.MATERIAS,
            entidad_id=str(comision_id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"Asignó a {nombre_docente} como docente a cargo de la comisión "
                f"{comision.nombre} ({comision.codigo})"
                if comision.docente_id
                else (
                    f"Dejó sin docente a cargo la comisión {comision.nombre} "
                    f"({comision.codigo})"
                )
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
            docente_id=comision.docente_id,
            docente_nombre=nombre_docente,
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
            modulo=ModuloAuditoria.MATERIAS,
            entidad_id=str(comision_id),
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
            modulo=ModuloAuditoria.EXAMENES,
            entidad_id=str(inscripcion.id),
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
            modulo=ModuloAuditoria.EXAMENES,
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

    async def _exigir_pertenencia(principal, examen_id: str) -> None:
        """C-73 §9: el DOCENTE solo opera los exámenes de SUS comisiones.

        La capacidad (`gestionar_academico`) dice QUÉ puede hacer el rol; esto dice
        SOBRE QUÉ. Sin esta segunda pregunta, un docente redirige la nota de un examen
        ajeno a la libreta que quiera. Los roles de alcance institucional no pasan por
        acá (ver `autorizar_docente_sobre_examen`)."""
        from app.domain.auth.authorization import autorizar_docente_sobre_examen
        from app.domain.auth.errors import ForbiddenError
        from app.infrastructure.persistence.repositories.exam_content import (
            ComisionSqlRepository,
        )

        async with session_factory() as session:
            docente_id = await ComisionSqlRepository(session).docente_de_examen(
                examen_id
            )
        try:
            autorizar_docente_sobre_examen(principal, docente_id)
        except ForbiddenError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "examen_ajeno", "mensaje": str(exc)},
            ) from exc

    async def _exigir_pertenencia_materia(principal, materia_id: str) -> None:
        """C-74: docente solo opera el banco de su propia materia (misma política que examen)."""
        from app.domain.auth.authorization import autorizar_docente_sobre_examen
        from app.domain.auth.errors import ForbiddenError
        from app.infrastructure.persistence.repositories.exam_content import (
            ComisionSqlRepository,
        )
        async with session_factory() as session:
            docente_id = await ComisionSqlRepository(session).docente_de_materia(materia_id)
        try:
            autorizar_docente_sobre_examen(principal, docente_id)
        except ForbiddenError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "materia_ajena", "mensaje": str(exc)},
            ) from exc

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

        await _exigir_pertenencia(principal, examen_id)
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
            modulo=ModuloAuditoria.EXAMENES,
            entidad_id=str(examen_id),
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
            limite_preguntas=examen.limite_preguntas,
            mostrar_nota=examen.mostrar_nota,
            revision_habilitada=examen.revision_habilitada,
            politica_intentos=examen.politica_intentos,
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

        await _exigir_pertenencia(principal, examen_id)
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

        # Tope de preguntas: 0 es la forma de SACAR el tope (el schema no acepta
        # negativos y `null` ya significa "no lo toques" en un PATCH parcial).
        if cambios.get("limite_preguntas") == 0:
            cambios["limite_preguntas"] = None

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
            modulo=ModuloAuditoria.EXAMENES,
            entidad_id=str(examen_id),
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

    # -----------------------------------------------------------------------
    # Banco de preguntas — categorías (C-74 §4)
    # -----------------------------------------------------------------------

    @router.get(
        "/categorias",
        summary="Listar categorías del banco de preguntas de una materia (C-74 §4)",
    )
    async def listar_categorias_banco(
        materia_id: str,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ):
        """Devuelve todas las categorías de la materia, flat (el cliente construye el árbol)."""
        await _exigir_pertenencia_materia(principal, materia_id)
        if session_factory is None:
            raise HTTPException(status_code=500, detail="Persistencia no inicializada.")
        from app.infrastructure.persistence.repositories.categoria_pregunta import (
            CategoriaPreguntaSqlRepository,
        )
        async with session_factory() as session:
            cats = await CategoriaPreguntaSqlRepository(session).listar_por_materia(materia_id)
        return [
            {
                "id": c.id,
                "nombre": c.nombre,
                "materia_id": c.materia_id,
                "categoria_padre_id": c.categoria_padre_id,
                "creada_en": c.creada_en.isoformat() if c.creada_en else None,
            }
            for c in cats
        ]

    @router.post(
        "/categorias",
        status_code=201,
        summary="Crear categoría en el banco de preguntas (C-74 §4)",
    )
    async def crear_categoria_banco(
        body: dict,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ):
        materia_id = body.get("materia_id", "")
        nombre = body.get("nombre", "").strip()
        padre_id = body.get("categoria_padre_id") or None
        if not materia_id or not nombre:
            raise HTTPException(status_code=422, detail="materia_id y nombre son requeridos.")
        await _exigir_pertenencia_materia(principal, materia_id)
        if session_factory is None:
            raise HTTPException(status_code=500, detail="Persistencia no inicializada.")
        from app.domain.exam_content.entities import CategoriaPregunta
        from app.infrastructure.persistence.repositories.categoria_pregunta import (
            CategoriaPreguntaSqlRepository,
        )
        async with session_factory() as session:
            cat = await CategoriaPreguntaSqlRepository(session).crear(
                CategoriaPregunta(nombre=nombre, materia_id=materia_id, categoria_padre_id=padre_id)
            )
            await session.commit()
        return {
            "id": cat.id,
            "nombre": cat.nombre,
            "materia_id": cat.materia_id,
            "categoria_padre_id": cat.categoria_padre_id,
            "creada_en": cat.creada_en.isoformat() if cat.creada_en else None,
        }

    @router.patch(
        "/categorias/{categoria_id}",
        summary="Renombrar categoría del banco de preguntas (C-74 §4)",
    )
    async def renombrar_categoria_banco(
        categoria_id: str,
        body: dict,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ):
        nombre = body.get("nombre", "").strip()
        if not nombre:
            raise HTTPException(status_code=422, detail="nombre es requerido.")
        if session_factory is None:
            raise HTTPException(status_code=500, detail="Persistencia no inicializada.")
        from app.infrastructure.persistence.models.exam_content import CategoriaPreguntaModel
        from app.infrastructure.persistence.repositories.categoria_pregunta import (
            CategoriaPreguntaSqlRepository,
        )
        from sqlalchemy import update as _update
        async with session_factory() as session:
            cat = await CategoriaPreguntaSqlRepository(session).obtener(categoria_id)
            if cat is None:
                raise HTTPException(status_code=404, detail="categoria_no_encontrada")
            await _exigir_pertenencia_materia(principal, cat.materia_id)
            await session.execute(
                _update(CategoriaPreguntaModel)
                .where(CategoriaPreguntaModel.id == categoria_id)
                .values(nombre=nombre)
            )
            await session.commit()
            cat_act = await CategoriaPreguntaSqlRepository(session).obtener(categoria_id)
        return {
            "id": cat_act.id,
            "nombre": cat_act.nombre,
            "materia_id": cat_act.materia_id,
            "categoria_padre_id": cat_act.categoria_padre_id,
        }

    @router.delete(
        "/categorias/{categoria_id}",
        status_code=204,
        summary="Borrar categoría del banco de preguntas (C-74 §4)",
    )
    async def borrar_categoria_banco(
        categoria_id: str,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ):
        if session_factory is None:
            raise HTTPException(status_code=500, detail="Persistencia no inicializada.")
        from app.infrastructure.persistence.repositories.categoria_pregunta import (
            CategoriaPreguntaSqlRepository,
        )
        async with session_factory() as session:
            cat = await CategoriaPreguntaSqlRepository(session).obtener(categoria_id)
            if cat is None:
                raise HTTPException(status_code=404, detail="categoria_no_encontrada")
            await _exigir_pertenencia_materia(principal, cat.materia_id)
            await CategoriaPreguntaSqlRepository(session).borrar(categoria_id)
            await session.commit()

    # -----------------------------------------------------------------------
    # Banco de preguntas — listar/mover preguntas del banco (C-74 §4)
    # -----------------------------------------------------------------------

    @router.get(
        "/preguntas",
        summary="Listar preguntas del banco por materia/categoría (C-74 §4, 0057)",
    )
    async def listar_preguntas_banco(
        materia_id: str,
        categoria_id: str | None = None,
        sin_categoria: bool = False,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ):
        """Devuelve preguntas de la tabla pregunta_banco para la materia dada.

        Las preguntas del banco son independientes de los exámenes (0057).
        Si ``sin_categoria=true``, devuelve las preguntas con categoria_id=NULL.
        Si se provee ``categoria_id``, filtra por esa categoría.
        """
        await _exigir_pertenencia_materia(principal, materia_id)
        if session_factory is None:
            raise HTTPException(status_code=500, detail="Persistencia no inicializada.")
        from sqlalchemy import select as _select
        from app.infrastructure.persistence.models.exam_content import PreguntaBancoModel
        async with session_factory() as session:
            stmt = _select(PreguntaBancoModel).where(
                PreguntaBancoModel.materia_id == materia_id
            )
            if sin_categoria:
                stmt = stmt.where(PreguntaBancoModel.categoria_id.is_(None))
            elif categoria_id:
                stmt = stmt.where(PreguntaBancoModel.categoria_id == categoria_id)
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "enunciado": r.enunciado,
                "tipo": r.tipo,
                "orden": 0,
                "seleccionada": True,
                "categoria_id": r.categoria_id,
                # 0058: la UI marca con esto qué preguntas ya no las toca Moodle.
                "categoria_manual": r.categoria_manual,
            }
            for r in rows
        ]

    @router.patch(
        "/preguntas/{pregunta_id}/categoria",
        summary="Mover pregunta del banco a una categoría (C-74 §4.3, 0057)",
    )
    async def mover_pregunta_categoria(
        pregunta_id: str,
        body: dict,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ):
        """Mueve la pregunta y marca su categoría como decidida por el docente.

        ``categoria_manual=True`` (0058) es lo que después hace que el import de
        XML y el sync desde Moodle dejen esta pregunta donde el docente la puso.
        """
        nueva_cat_id = body.get("categoria_id") or None
        if session_factory is None:
            raise HTTPException(status_code=500, detail="Persistencia no inicializada.")
        from sqlalchemy import update as _update
        from app.infrastructure.persistence.models.exam_content import PreguntaBancoModel
        async with session_factory() as session:
            row = await session.get(PreguntaBancoModel, pregunta_id)
            if row is None:
                raise HTTPException(status_code=404, detail="pregunta_no_encontrada")
            await _exigir_pertenencia_materia(principal, row.materia_id)
            await session.execute(
                _update(PreguntaBancoModel)
                .where(PreguntaBancoModel.id == pregunta_id)
                .values(categoria_id=nueva_cat_id, categoria_manual=True)
            )
            await session.commit()
        return {
            "pregunta_id": pregunta_id,
            "categoria_id": nueva_cat_id,
            "categoria_manual": True,
        }

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

        await _exigir_pertenencia(principal, examen_id)
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
            # Tope de preguntas del examen: la selección no puede excederlo. Se
            # valida acá (y no solo en la UI) porque es el único punto por el que
            # pasa cualquier cambio de selección.
            examen_cfg = await repo.obtener(examen_id)
            tope = getattr(examen_cfg, "limite_preguntas", None) if examen_cfg else None
            if tope is not None and len(body.seleccionadas) > tope:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "limite_preguntas_excedido",
                        "mensaje": (
                            f"Este examen admite como máximo {tope} pregunta(s) y se "
                            f"seleccionaron {len(body.seleccionadas)}. Quitá "
                            f"{len(body.seleccionadas) - tope} o subí el tope en la "
                            "configuración del examen."
                        ),
                        "limite": tope,
                        "seleccionadas": len(body.seleccionadas),
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
            modulo=ModuloAuditoria.EXAMENES,
            entidad_id=str(examen_id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"Fijó la selección de preguntas del examen {examen_id}: "
                f"{len(body.seleccionadas)} seleccionada(s)"
            ),
        )

        return _pool_to_response(items)

    @router.post(
        "/{examen_id}/sortear-preguntas",
        response_model=PreguntasPoolResponse,
        summary="Armar examen por sorteo aleatorio de categorías (C-74 §3)",
    )
    async def sortear_preguntas(
        examen_id: str,
        body: SorteoRequest,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> PreguntasPoolResponse:
        """Sortea N preguntas de cada categoría y marca seleccionada=true.

        - 409 si el examen ya tiene intentos finalizados (mismo candado que selección manual).
        - 422 si alguna categoría tiene menos preguntas de las pedidas.
        - 422 si la lista de categorías está vacía.
        - Cada llamada produce una selección NUEVA (no idempotente).
        """
        await _exigir_pertenencia(principal, examen_id)
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        from app.application.exam_content.errors import SorteoInsuficienteError
        from app.domain.exam_content.errors import SeleccionInvalidaError
        from app.infrastructure.persistence.repositories.exam_content import (
            ExamenContenidoSqlRepository,
        )

        async with session_factory() as session:
            repo = ExamenContenidoSqlRepository(session)

            if await _seleccion_bloqueada(session, examen_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "seleccion_bloqueada",
                        "mensaje": (
                            "No se puede sortear: este examen ya tiene intentos "
                            "finalizados y cambiar la selección alteraría notas ya "
                            "calculadas."
                        ),
                    },
                )

            try:
                items = await repo.sortear_por_categorias(
                    examen_id,
                    body.categoria_ids,
                    body.cantidad_por_categoria,
                )
            except SorteoInsuficienteError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "sorteo_insuficiente",
                        "mensaje": str(exc),
                        "categoria_id": exc.categoria_id,
                        "disponibles": exc.disponibles,
                        "pedidas": exc.pedidas,
                    },
                ) from exc
            except SeleccionInvalidaError as exc:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": "seleccion_invalida", "mensaje": str(exc)},
                ) from exc

            if items is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "examen_no_encontrado", "examen_id": examen_id},
                )
            await session.commit()

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
                writeback_svc=writeback_svc,
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

    def _aplicar_politica(
        filas: list,
        politica: PoliticaIntentos,
    ) -> list:
        """Dado el set de filas sincronizables, devuelve las que SE DEBEN ENVIAR.

        - MANUAL     → todas (el admin eligió sincronizar cada sesión a mano).
        - MAS_ALTA   → por alumno, solo la fila con la nota más alta.
        - ULTIMO     → por alumno, solo la fila de la sesión más reciente
                       (usa el session_id como proxy de orden de creación, que
                       es un UUID v4 temporal o un timestamp implícito; si la
                       tabla tuviera created_at lo usaríamos, pero session_id
                       es suficientemente estable para dev — en prod se puede
                       mejorar con created_at en la migración siguiente).
        - PRIMERO    → por alumno, solo la fila de la sesión más antigua.

        La deduplicación es por `alumno_idnumber` (legajo). Si es None, se trata
        cada fila como alumno distinto (no hay forma de deduplicar sin identidad).
        """
        if politica == PoliticaIntentos.MANUAL:
            return filas

        # Agrupa por alumno
        grupos: dict[str, list] = {}
        sin_id: list = []
        for f in filas:
            key = f.alumno_idnumber
            if key is None:
                sin_id.append(f)
            else:
                grupos.setdefault(key, []).append(f)

        resultado: list = list(sin_id)
        for intentos in grupos.values():
            if len(intentos) == 1:
                resultado.append(intentos[0])
                continue
            if politica == PoliticaIntentos.MAS_ALTA:
                elegida = max(intentos, key=lambda f: float(f.nota or 0))
            elif politica == PoliticaIntentos.PRIMERO:
                elegida = min(intentos, key=lambda f: f.session_id)
            else:  # ULTIMO
                elegida = max(intentos, key=lambda f: f.session_id)
            resultado.append(elegida)
        return resultado

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

        await _exigir_pertenencia(principal, examen_id)
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
                    modulo=ModuloAuditoria.MOODLE,
                    entidad_id=str(examen_id),
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

            # Aplica la política de intentos: filtra qué notas enviar cuando
            # un alumno tiene múltiples sesiones pendientes para el mismo examen.
            from app.infrastructure.persistence.repositories.exam_content import (
                ExamenContenidoSqlRepository,
            )
            examen_cfg = await ExamenContenidoSqlRepository(session).obtener(examen_id)
            politica = (
                examen_cfg.politica_intentos
                if examen_cfg is not None
                else PoliticaIntentos.MAS_ALTA
            )
            pendientes = _aplicar_politica(pendientes, politica)
            total = len(pendientes)

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
            modulo=ModuloAuditoria.MOODLE,
            entidad_id=str(examen_id),
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

    # -----------------------------------------------------------------------
    # Sincronización del banco de preguntas desde Moodle (C-74 §9.4)
    # Importa las categorías del banco del curso Moodle a la materia indicada.
    # Idempotente: segunda sincronización del mismo curso no duplica filas.
    # -----------------------------------------------------------------------

    @router.post(
        "/moodle/sync-banco",
        response_model=SyncBancoResponse,
        status_code=status.HTTP_200_OK,
        summary="Sincronizar banco de preguntas desde Moodle (C-74 §9.4)",
    )
    async def sync_banco_preguntas(
        body: SyncBancoRequest,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> SyncBancoResponse:
        """Importa categorías del banco de preguntas de un curso Moodle.

        El token se obtiene de la credencial docente personal del docente que
        hace la llamada (``_credencial_para``), igual que en el write-back.
        Si no tiene credencial propia se cae al token institucional de config.

        Idempotente: re-sincronizar el mismo curso no duplica categorías.
        422 si ``materia_id`` no corresponde al docente.
        503 si Moodle no está configurado.
        """
        from app.application.exam_content.moodle_sync_service import (
            MoodleSyncError,
            sync_banco_desde_moodle,
        )

        await _exigir_pertenencia_materia(principal, body.materia_id)

        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        # Resolver token: preferir credencial docente personal; si no, usar el
        # token institucional de writeback_svc (si está configurado).
        token: str | None = None
        base_url: str | None = None

        from app.infrastructure.persistence.models.transactional import (
            MoodleCredencialDocenteModel,
        )
        from sqlalchemy import select as _select

        async with session_factory() as session:
            fila_cred = (
                await session.execute(
                    _select(MoodleCredencialDocenteModel).where(
                        MoodleCredencialDocenteModel.usuario_id == principal.usuario_id
                    )
                )
            ).scalar_one_or_none()

        if fila_cred is not None and fila_cred.estado == "activa":
            from app.infrastructure.crypto.secret_encryption import SecretCipher
            import os

            secret_key = os.environ.get("SECRET_ENCRYPTION_KEY", "")
            if secret_key:
                try:
                    cipher = SecretCipher(secret_key)
                    token = cipher.decrypt(fila_cred.token_cifrado)
                    base_url = fila_cred.base_url
                except Exception:
                    token = None

        if token is None and writeback_svc is not None:
            # Usar el token institucional de la config de writeback
            try:
                cfg = await writeback_svc._client._resolver_config()
                token = cfg.ws_token
                base_url = cfg.base_url
            except Exception:
                token = None

        if not token or not base_url:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "moodle_sin_token",
                    "mensaje": (
                        "No hay credencial Moodle disponible. Configurá tu "
                        "credencial personal en Configuración → Campus (Moodle) "
                        "o pedí al administrador que configure el token institucional."
                    ),
                },
            )

        try:
            async with session_factory() as session:
                resultado = await sync_banco_desde_moodle(
                    db=session,
                    courseid=body.courseid,
                    materia_id=body.materia_id,
                    token=token,
                    base_url=base_url,
                )
                await session.commit()
        except MoodleSyncError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error": "moodle_sync_error", "mensaje": str(exc)},
            ) from exc

        return SyncBancoResponse(
            categorias_creadas=resultado["categorias_creadas"],
            preguntas_nuevas=resultado["preguntas_nuevas"],
            preguntas_actualizadas=resultado["preguntas_actualizadas"],
        )

    # -----------------------------------------------------------------------
    # Crear examen desde banco de preguntas (C-74 §5)
    # -----------------------------------------------------------------------

    @router.post(
        "/crear-desde-banco",
        response_model=CrearDesdebancoResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Crea un examen extrayendo preguntas aleatoriamente del banco (C-74 §5)",
    )
    async def crear_desde_banco(
        body: CrearDesdebancoRequest,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> CrearDesdebancoResponse:
        """Crea un examen de contenido en un solo paso.

        Para cada item de ``sorteo``, extrae ``cantidad`` preguntas aleatorias del banco
        de la categoría indicada (None = sin clasificar). Todas quedan con seleccionada=True.

        Errores:
        - 422 si alguna categoría tiene menos preguntas disponibles que las pedidas.
        - 404 si la materia no existe o el usuario no tiene acceso.
        """
        await _exigir_pertenencia_materia(principal, body.materia_id)
        if session_factory is None:
            raise HTTPException(status_code=500, detail="Persistencia no inicializada.")

        import random
        import uuid as _uuid
        from sqlalchemy import select as _select
        from sqlalchemy.orm import selectinload as _selectinload
        from app.infrastructure.persistence.models.exam_content import (
            BlankBancoModel,
            CategoriaPreguntaModel,
            ExamenContenidoModel,
            OpcionClozeBlancoModel,
            OpcionRespuestaModel,
            PreguntaBancoModel,
            PreguntaClozeBlankModel,
            PreguntaExamenModel,
        )

        async with session_factory() as session:
            # Árbol de categorías de la materia, para expandir cada tramo a su
            # descendencia. Una sola consulta: el árbol es chico (decenas de filas)
            # y así evitamos una consulta recursiva por tramo.
            hijos_por_padre: dict[str | None, list[str]] = {}
            cats_result = await session.execute(
                _select(
                    CategoriaPreguntaModel.id,
                    CategoriaPreguntaModel.categoria_padre_id,
                ).where(CategoriaPreguntaModel.materia_id == body.materia_id)
            )
            for cat_id, padre_id in cats_result.all():
                hijos_por_padre.setdefault(padre_id, []).append(cat_id)

            def _con_descendencia(raiz: str) -> list[str]:
                """La categoría más todas sus subcategorías, a cualquier profundidad."""
                acumulado: list[str] = []
                pendientes = [raiz]
                vistos: set[str] = set()
                while pendientes:
                    actual = pendientes.pop()
                    if actual in vistos:
                        continue
                    vistos.add(actual)
                    acumulado.append(actual)
                    pendientes.extend(hijos_por_padre.get(actual, []))
                return acumulado

            # ── Sortear preguntas del banco por cada tramo ──────────────────
            preguntas_sorteadas: list[PreguntaBancoModel] = []
            # Una pregunta no puede caer dos veces en el mismo examen: con tramos
            # anidados ("Unidad 1" y además "Unidad 1 / Tema A") el mismo registro
            # entra en los dos conjuntos.
            ya_sorteadas: set[str] = set()

            for tramo in body.sorteo:
                # Las opciones y los blanks viajan con la pregunta: se copian al
                # examen más abajo, así que se cargan acá de una (sin N+1).
                stmt = (
                    _select(PreguntaBancoModel)
                    .where(PreguntaBancoModel.materia_id == body.materia_id)
                    .options(
                        _selectinload(PreguntaBancoModel.opciones_banco),
                        _selectinload(PreguntaBancoModel.blanks_banco).selectinload(
                            BlankBancoModel.opciones_blank_banco
                        ),
                    )
                )
                if tramo.categoria_id is None:
                    stmt = stmt.where(PreguntaBancoModel.categoria_id.is_(None))
                elif tramo.incluir_subcategorias:
                    stmt = stmt.where(
                        PreguntaBancoModel.categoria_id.in_(
                            _con_descendencia(tramo.categoria_id)
                        )
                    )
                else:
                    stmt = stmt.where(PreguntaBancoModel.categoria_id == tramo.categoria_id)

                result = await session.execute(stmt)
                disponibles = [
                    p for p in result.scalars().all() if p.id not in ya_sorteadas
                ]

                if len(disponibles) < tramo.cantidad:
                    cat_label = tramo.categoria_id or "sin clasificar"
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={
                            "error": "sorteo_insuficiente",
                            "mensaje": (
                                f"Categoría '{cat_label}': se pidieron {tramo.cantidad} "
                                f"preguntas pero solo hay {len(disponibles)} disponibles."
                            ),
                            "categoria_id": tramo.categoria_id,
                            "disponibles": len(disponibles),
                            "pedidas": tramo.cantidad,
                        },
                    )

                elegidas = random.sample(disponibles, tramo.cantidad)
                preguntas_sorteadas.extend(elegidas)
                ya_sorteadas.update(p.id for p in elegidas)

            # El tope del examen se valida ANTES de crear nada: es preferible un 422
            # claro a un examen a medio armar. Mismo criterio que el import de XML
            # (LimitePreguntasExcedidoError): no se trunca en silencio.
            if body.limite_preguntas is not None and len(preguntas_sorteadas) > body.limite_preguntas:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "limite_preguntas_excedido",
                        "mensaje": (
                            f"El sorteo suma {len(preguntas_sorteadas)} preguntas pero el "
                            f"examen admite {body.limite_preguntas}. Ajustá las cantidades "
                            "por categoría o subí el límite."
                        ),
                        "sorteadas": len(preguntas_sorteadas),
                        "limite": body.limite_preguntas,
                    },
                )

            # ── Crear examen_contenido ───────────────────────────────────────
            examen_id = str(_uuid.uuid4())
            examen = ExamenContenidoModel(
                id=examen_id,
                titulo=body.titulo,
                comision_id=body.comision_id,
                activo=False,
                limite_preguntas=body.limite_preguntas,
            )
            session.add(examen)
            await session.flush()

            # ── Copiar preguntas del banco al examen ─────────────────────────
            # La pregunta se COPIA, no se referencia: el examen queda congelado
            # aunque después se edite el banco. Y hay que copiar TAMBIÉN opciones y
            # blanks — sin ellos la pregunta llega al alumno sin nada que responder
            # y sin nada con qué calificarla.
            for orden, pb in enumerate(preguntas_sorteadas):
                pregunta_id = str(_uuid.uuid4())
                session.add(
                    PreguntaExamenModel(
                        id=pregunta_id,
                        examen_id=examen_id,
                        enunciado=pb.enunciado,
                        tipo=pb.tipo,
                        orden=orden,
                        seleccionada=True,
                        categoria_id=pb.categoria_id,
                        moodle_question_id=pb.moodle_question_id,
                        pregunta_banco_id=pb.id,
                    )
                )

                for opcion in pb.opciones_banco:
                    session.add(
                        OpcionRespuestaModel(
                            id=str(_uuid.uuid4()),
                            pregunta_id=pregunta_id,
                            texto=opcion.texto,
                            es_correcta=opcion.es_correcta,
                            orden=opcion.orden,
                        )
                    )

                for blank in pb.blanks_banco:
                    blank_id = str(_uuid.uuid4())
                    session.add(
                        PreguntaClozeBlankModel(
                            id=blank_id,
                            pregunta_id=pregunta_id,
                            orden=blank.orden,
                            tipo=blank.tipo,
                            texto_antes=blank.texto_antes,
                            texto_despues=blank.texto_despues,
                        )
                    )
                    for opcion_blank in blank.opciones_blank_banco:
                        session.add(
                            OpcionClozeBlancoModel(
                                id=str(_uuid.uuid4()),
                                blank_id=blank_id,
                                texto=opcion_blank.texto,
                                es_correcta=opcion_blank.es_correcta,
                                peso=opcion_blank.peso,
                            )
                        )

            await session.commit()

        return CrearDesdebancoResponse(
            examen_id=examen_id,
            titulo=body.titulo,
            total_preguntas=len(preguntas_sorteadas),
        )

    return router
