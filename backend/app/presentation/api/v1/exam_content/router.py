"""Routers de exam_content (FastAPI, C-69).

Admin router:
  POST /moodle-import — admin-only + MFA: importa XML, crea ExamenContenido.

Taking router (student-facing):
  GET /{examen_id} — cualquier principal autenticado: preguntas+opciones sin es_correcta (D3).
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

from app.application.exam_content.asociacion_service import AsociacionComisionService
from app.application.exam_content.inscripcion_service import (
    AutoMatriculacionService,
    InscripcionService,
)
from app.application.exam_content.materia_comision_service import (
    MateriaComisionService,
)
from app.application.moodle.resultados_query import (
    listar_estados_sincronizables,
    listar_mis_notas,
    listar_resultados_examen,
)
from app.application.moodle.revision_query import obtener_revision
from app.application.moodle.writeback_service import (
    MoodleWritebackService,
    WritebackEstado,
)
from app.application.exam_content.errors import (
    CodigoMatriculacionInvalidoError,
    ComisionNoEncontradaError,
    ComisionNoVaciaError,
    ExamenNoEncontradoError,
    InscripcionNoEncontradaError,
    MateriaNoEncontradaError,
    MateriaInactivaError,
    MateriaNoVaciaError,
    MoodleXmlInvalidoError,
    MoodleXmlVacioError,
    PerfilIncompletoError,
    UsuarioNoEncontradoError,
)
from app.application.exam_content.import_service import ImportacionMoodleService
from app.application.exam_content.taking_service import LecturaExamenService, proyectar_examen
from app.domain.auth.identity import AuthenticatedPrincipal
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
    require_roles,
)
from app.presentation.api.v1.exam_content.schemas import (
    AltaInlineRequest,
    AltaInlineResponse,
    AlumnoElegibilidadResponse,
    AsociarComisionRequest,
    AsociarComisionResponse,
    ComisionActualizarRequest,
    ComisionCrearRequest,
    ComisionResponse,
    ExamenConfigPatchRequest,
    ExamenConfigResponse,
    ExamenContenidoResumenResponse,
    ExamenesContenidoPaginadosResponse,
    ExamenRendicionResponse,
    CapturaFirmadaResponse,
    ImportReporteResponse,
    InformeDevolucionResponse,
    InscribirAlumnoRequest,
    InscribirPorCodigoRequest,
    InscribirPorCodigoResponse,
    InscripcionResponse,
    MateriaActivaRequest,
    MateriaActualizarRequest,
    MateriaCrearRequest,
    MateriaResponse,
    MiNotaResponse,
    MisNotasResponse,
    MoodleTargetRequest,
    MoodleTargetResponse,
    OmitidaItemResponse,
    OpcionRendicionResponse,
    OpcionRevisionResponse,
    PeriodoEnum,
    PreguntaPoolItemResponse,
    PreguntaRendicionResponse,
    PreguntaRevisionResponse,
    PreguntasPoolResponse,
    PreguntasSeleccionRequest,
    ResultadoAlumnoResponse,
    ResultadosExamenPaginadosResponse,
    RevisionExamenResponse,
    SenalAnalisisResponse,
    SincronizarMoodleResponse,
)


# Gate de inscripción (C-71): los roles de gestión ven TODO el catálogo/materias;
# el alumno ve solo lo de sus comisiones inscriptas.
_ROLES_STAFF = frozenset(
    {"admin_sistema", "admin_examenes", "proctor", "revisor", "coordinador", "auditor"}
)


def _es_staff(principal: AuthenticatedPrincipal) -> bool:
    return bool(set(principal.roles or []) & _ROLES_STAFF)


def _resumen_to_response(r) -> ExamenContenidoResumenResponse:
    """Mapea un ExamenContenidoResumen de dominio al schema de respuesta (D3)."""
    return ExamenContenidoResumenResponse(
        id=r.id,
        titulo=r.titulo,
        cantidad_preguntas=r.cantidad_preguntas,
        comision_id=r.comision_id,
        comision_nombre=r.comision_nombre,
        materia_nombre=r.materia_nombre,
        apertura=r.apertura,
        cierre=r.cierre,
        tiempo_limite_min=r.tiempo_limite_min,
        intentos_permitidos=r.intentos_permitidos,
    )


def create_periodos_router() -> APIRouter:
    """Router público (sin auth) que expone los valores válidos de período."""
    router = APIRouter()

    @router.get("/periodos", response_model=list[dict], tags=["exam-content"])
    async def listar_periodos():
        """Devuelve los períodos académicos válidos para una comisión."""
        return [
            {"value": PeriodoEnum.primer_cuatrimestre, "label": "1er cuatrimestre"},
            {"value": PeriodoEnum.segundo_cuatrimestre, "label": "2do cuatrimestre"},
        ]

    return router


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
    async def crear_materia(body: MateriaCrearRequest) -> MateriaResponse:
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

        return MateriaResponse(
            id=materia.id, codigo=materia.codigo, nombre=materia.nombre, activa=materia.activa
        )

    @router.delete(
        "/materias/{materia_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        response_model=None,
        summary="Eliminar una materia (solo si está 100% vacía)",
    )
    async def eliminar_materia(materia_id: str) -> None:
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

    @router.patch(
        "/materias/{materia_id}/activa",
        response_model=MateriaResponse,
        summary="Activar o desactivar una materia (freeze)",
    )
    async def set_activa_materia(
        materia_id: str,
        body: MateriaActivaRequest,
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

        return ComisionResponse(
            id=comision.id,
            materia_id=comision.materia_id,
            codigo=comision.codigo,
            nombre=comision.nombre,
            periodo=comision.periodo,
            anio=comision.anio,
            codigo_matriculacion=comision.codigo_matriculacion,
        )

    @router.patch(
        "/comisiones/{comision_id}",
        response_model=ComisionResponse,
        summary="Actualizar nombre/periodo/anio de una comisión (codigo inmutable)",
    )
    async def actualizar_comision(
        comision_id: str,
        body: ComisionActualizarRequest,
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

        return ComisionResponse(
            id=comision.id,
            materia_id=comision.materia_id,
            codigo=comision.codigo,
            nombre=comision.nombre,
            periodo=comision.periodo,
            anio=comision.anio,
            codigo_matriculacion=comision.codigo_matriculacion,
        )

    @router.delete(
        "/comisiones/{comision_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        response_model=None,
        summary="Eliminar una comisión (solo si está vacía)",
    )
    async def eliminar_comision(comision_id: str) -> None:
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
        )

    # -----------------------------------------------------------------------
    # Inscripción de alumnos a comisiones + elegibilidad (C-69) — admin-only.
    # Inscribe/da de baja alumnos a una comisión y lista los inscriptos con su
    # elegibilidad ("puede rendir" = consentimiento vigente + biometría vigente),
    # resuelta server-side (cliente = sensor no confiable). El picker de alumnos
    # del front reusa el GET /users?rol=estudiante existente. Capa router→service→repo.
    # -----------------------------------------------------------------------

    def _build_inscripcion_service(session) -> InscripcionService:
        from app.infrastructure.persistence.repositories.exam_content import (
            ComisionSqlRepository,
            InscripcionSqlRepository,
        )
        from app.infrastructure.persistence.repositories.biometric_reference import (
            EmbeddingReferenciaRepository,
        )
        from app.infrastructure.persistence.repositories.consent_perfil import (
            ConsentimientoPerfilSqlRepository,
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
    async def eliminar_inscripcion(comision_id: str, usuario_id: str) -> None:
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
    # Configuración del examen POR EXAMEN (C-69, migración 0032) — admin-only.
    # ActiveExam opera estos 7 campos; el alumno rinde con ellos. GET lee la
    # config; PATCH la actualiza parcialmente (extra='forbid', validaciones → 422).
    # -----------------------------------------------------------------------

    def _config_to_response(examen, *, bloqueada: bool = False) -> ExamenConfigResponse:
        # C-72 sección 6: si ya fue rendido, expone el detalle direccional para la UI.
        from app.domain.exam_content.config import (
            CAMPOS_DIRECCIONALES,
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
            campos_solo_ampliables=sorted(CAMPOS_DIRECCIONALES) if bloqueada else [],
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
