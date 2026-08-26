"""Router de gestión del catálogo académico (exam_content, C-69) — admin-only.

Materias, comisiones, exámenes de contenido (import Moodle XML), config por examen,
destino Moodle y sincronización manual de resultados. Requiere roles de gestión
(guard a nivel router). Extraído de router.py al partir el god-file en sub-routers.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import func

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)

from app.application.audit.service import registrar_seguro
from app.application.exam_content.export import (
    COLUMNAS_INSCRIPTOS,
    COLUMNAS_NOTAS,
    filas_inscriptos,
    filas_notas,
    tabla_a_pdf,
    tabla_a_xlsx,
)
from app.application.audit.acciones import AccionAuditoria, EntidadAuditoria, ModuloAuditoria
from app.domain.auth.identity import AuthenticatedPrincipal

from app.application.exam_content.asociacion_service import AsociacionComisionService
from app.application.exam_content.sorteo_por_intento import (
    MODO_FIJO,
    MODO_SORTEO_POR_INTENTO,
)
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
from app.application.exam_content.impacto_baja import (
    impacto_baja_comision,
    impacto_baja_examen,
    impacto_baja_materia,
)
from app.application.exam_content.import_service import ImportacionMoodleService
from app.application.exam_content.inscripcion_service import (
    InscripcionService,
)
from app.application.exam_content.materia_comision_service import (
    MateriaComisionService,
)
from app.application.moodle.resultados_query import (
    ARCHIVADO_VALIDOS,
    ESTADO_MANUAL,
    ESTADOS_ENTREGA_VALIDOS,
    archivado_filtro,
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
from app.domain.exam_content.visibilidad import (
    MOSTRAR_NOTA_AL_CERRAR,
    MOSTRAR_NOTA_NUNCA,
    transicion_visibilidad_permitida,
)
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
    ComisionActualizarRequest,
    ComisionCrearRequest,
    ComisionTutorRequest,
    ComisionResponse,
    ExamenConfigPatchRequest,
    ExamenConfigResponse,
    ImportarBancoXmlResponse,
    ImportReporteResponse,
    PreguntaImportadaItemResponse,
    PreviewCategoriaResponse,
    PreviewImportBancoResponse,
    ImpactoBajaResponse,
    InscribirAlumnoRequest,
    InscripcionResponse,
    MateriaActualizarRequest,
    AlumnosComisionPaginadosResponse,
    MarcarNotaCargadaResponse,
    MateriaCoordinadorRequest,
    MateriaProfesorRequest,
    MateriaCrearRequest,
    MateriaResponse,
    MoodleTargetRequest,
    MoodleTargetResponse,
    TutorInfo,
    OmitidaItemResponse,
    PreguntaPoolItemResponse,
    PreguntasPoolResponse,
    PreguntasSeleccionRequest,
    ArchivarResultadoRequest,
    ArchivarResultadoResponse,
    ResultadoAlumnoResponse,
    SorteoRequest,
    ResultadosExamenPaginadosResponse,
    SincronizarMoodleRequest,
    SincronizarMoodleResponse,
    AgregarComisionExamenRequest,
    BlankPreviewResponse,
    ComisionDelExamenItem,
    ComisionesDelExamenResponse,
    OpcionPreviewResponse,
    PreguntaPreviewResponse,
    SorteoDelExamenResponse,
    TramoSorteoResponse,
    CrearDesdebancoRequest,
    CrearDesdebancoResponse,
    DuplicarExamenRequest,
    DuplicarExamenResponse,
    ExamenReplicaItem,
)


def _rechazar_si_hay_gente_rindiendo(
    sesiones_en_curso: int, *, error: str, que: str
) -> None:
    """409 si hay alguien rindiendo AHORA lo que se está por dar de baja.

    La baja bloquea la rendición server-side (el enforcement responde 410), así
    que hacerla con gente adentro le corta el examen a medio camino a alguien que
    no hizo nada mal. Se devuelve el número de sesiones para que quien lo intenta
    sepa a cuántos iba a afectar.

    OJO: la restricción es "en curso", NO "rendido alguna vez". Lo ya rendido sí
    se puede dar de baja — es el caso que motivó la baja lógica — y su evidencia
    queda intacta.
    """
    if sesiones_en_curso <= 0:
        return
    plural = "s" if sesiones_en_curso != 1 else ""
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error": error,
            "mensaje": (
                f"Hay {sesiones_en_curso} alumno{plural} rindiendo {que} en este "
                f"momento. Esperá a que termine{plural}, o cerrá el examen antes "
                "de darlo de baja."
            ),
            "sesiones_en_curso": sesiones_en_curso,
        },
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


def _titulo_base(titulo: str, codigo_comision: str | None) -> str:
    """El título sin el sufijo de comisión que le puso la replicación.

    Sin esto, agregar una comisión a «Parcial 1 (C1)» daría «Parcial 1 (C1) (C2)».
    Solo saca el sufijo si coincide EXACTO con el código de la comisión del examen:
    un título que termina en paréntesis por otro motivo («Parcial 1 (segunda
    fecha)») queda intacto.
    """
    if codigo_comision:
        sufijo = f" ({codigo_comision})"
        if titulo.endswith(sufijo):
            return titulo[: -len(sufijo)]
    return titulo


async def _clonar_examen(
    session,
    original,
    *,
    titulo: str,
    comision_id: str | None,
    lote_replica_id: str | None,
) -> tuple[str, int]:
    """Crea un examen nuevo con el contenido de ``original``. Devuelve (id, preguntas).

    Copia las preguntas (con opciones y blanks) y la configuración de mecánica y
    nota. NO copia lo que es del original y nada más que de él: los intentos, las
    notas ya publicadas y el destino de write-back en Moodle — heredar el `cmid`
    haría que la copia escriba encima de las notas del original.

    ``original`` tiene que venir con `preguntas`, sus `opciones` y sus
    `blanks_cloze` ya cargados (selectinload): esta función no consulta.

    No hace commit: el llamador decide la transacción.
    """
    import uuid as _uuid

    from app.infrastructure.persistence.models.exam_content import (
        ExamenContenidoModel,
        OpcionClozeBlancoModel,
        OpcionRespuestaModel,
        PreguntaClozeBlankModel,
        PreguntaExamenModel,
    )

    copia_id = str(_uuid.uuid4())
    session.add(
        ExamenContenidoModel(
            id=copia_id,
            titulo=titulo,
            comision_id=comision_id,
            lote_replica_id=lote_replica_id,
            tiempo_limite_min=original.tiempo_limite_min,
            intentos_permitidos=original.intentos_permitidos,
            apertura=original.apertura,
            cierre=original.cierre,
            nota_maxima=original.nota_maxima,
            nota_aprobacion=original.nota_aprobacion,
            mezclar_preguntas=original.mezclar_preguntas,
            limite_preguntas=original.limite_preguntas,
            mostrar_nota=original.mostrar_nota,
            revision_habilitada=original.revision_habilitada,
            mostrar_eventos_alumno=original.mostrar_eventos_alumno,
            politica_intentos=original.politica_intentos,
            # Explícito para que se lea de una qué NO se hereda. `eliminado_en`
            # nace en NULL: la copia está activa.
            moodle_courseid=None,
            moodle_cmid=None,
            moodle_component=None,
            notas_publicadas_en=None,
            notas_publicadas_por=None,
        )
    )
    await session.flush()

    preguntas_ordenadas = sorted(original.preguntas, key=lambda p: p.orden)
    for pregunta in preguntas_ordenadas:
        pregunta_id = str(_uuid.uuid4())
        session.add(
            PreguntaExamenModel(
                id=pregunta_id,
                examen_id=copia_id,
                enunciado=pregunta.enunciado,
                tipo=pregunta.tipo,
                orden=pregunta.orden,
                seleccionada=pregunta.seleccionada,
                categoria_id=pregunta.categoria_id,
                moodle_question_id=pregunta.moodle_question_id,
                pregunta_banco_id=pregunta.pregunta_banco_id,
            )
        )
        for opcion in pregunta.opciones:
            session.add(
                OpcionRespuestaModel(
                    id=str(_uuid.uuid4()),
                    pregunta_id=pregunta_id,
                    texto=opcion.texto,
                    es_correcta=opcion.es_correcta,
                    orden=opcion.orden,
                )
            )
        for blank in pregunta.blanks_cloze:
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
            for opcion_blank in blank.opciones_cloze:
                session.add(
                    OpcionClozeBlancoModel(
                        id=str(_uuid.uuid4()),
                        blank_id=blank_id,
                        texto=opcion_blank.texto,
                        es_correcta=opcion_blank.es_correcta,
                        peso=opcion_blank.peso,
                    )
                )

    return copia_id, len(preguntas_ordenadas)


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
    # materias, comisiones, notas) lo maneja quien tiene `gestionar_academico`.
    # Quienes la tienen sale de CAPABILITY_ROLES, no de esta lista — los roles
    # cambiaron dos veces (c-76 elimino "docente"/"admin_examenes", c-78 sumo
    # PROFESOR) y enumerarlos aca solo genera comentarios que mienten. Con la
    # lista hardcodeada anterior el tutor veia las pantallas pero comia 403 al
    # operar, que es el mismo desfasaje que dejaba la cola de revision inalcanzable.
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

    # -----------------------------------------------------------------------
    # Respuestas de materia/comisión CON sus responsables resueltos.
    #
    # Los endpoints que asignan o quitan un responsable devuelven la entidad
    # actualizada, y la UI usa esa respuesta para repintar los chips sin volver a
    # pedir el listado. Los tres helpers estaban siendo LLAMADOS pero nunca se
    # habían escrito: `NameError` en runtime, 500 en 7 endpoints (los 5 de
    # materia + los 2 de tutores de comisión). No lo agarraba ningún test porque
    # los que había verificaban la capa de repositorio, donde estos no participan.
    # -----------------------------------------------------------------------

    async def _tutor_infos(repo, ids: list[str]) -> list[TutorInfo]:
        """(id, nombre visible) de cada responsable, en UNA query (no N+1)."""
        if not ids:
            return []
        nombres = await repo.nombres_de_docentes(ids)
        return [TutorInfo(id=i, nombre=nombres.get(i, i)) for i in ids]

    async def _materia_response_con_coordinadores(session, materia) -> MateriaResponse:
        """Materia + sus coordinadores y profesores (N:M, c-78/c-79)."""
        from app.infrastructure.persistence.repositories.exam_content import (
            ComisionSqlRepository,
            MateriaSqlRepository,
        )

        materia_repo = MateriaSqlRepository(session)
        # `nombres_de_docentes` vive en el repo de comisión, pero resuelve nombres
        # de usuario sin importar el vínculo: sirve para los tres roles.
        nombres_repo = ComisionSqlRepository(session)

        coordinadores = (await materia_repo.coordinadores_de_materias([materia.id])).get(
            materia.id, []
        )
        profesores = (await materia_repo.profesores_de_materias([materia.id])).get(
            materia.id, []
        )
        return MateriaResponse(
            id=materia.id,
            codigo=materia.codigo,
            nombre=materia.nombre,
            activa=materia.activa,
            coordinadores=await _tutor_infos(nombres_repo, coordinadores),
            profesores=await _tutor_infos(nombres_repo, profesores),
        )

    async def _comision_response_con_tutores(repo, comision) -> ComisionResponse:
        """Comisión + sus tutores a cargo (N:M desde c-79)."""
        tutores = await repo.tutores_de_comision(comision.id)
        return ComisionResponse(
            id=comision.id,
            materia_id=comision.materia_id,
            codigo=comision.codigo,
            nombre=comision.nombre,
            periodo=comision.periodo,
            anio=comision.anio,
            codigo_matriculacion=comision.codigo_matriculacion,
            activa=comision.activa,
            tutores=await _tutor_infos(repo, tutores),
        )

    async def _validar_usuario_tutor(session, tutor_id: str) -> None:
        """422 si el usuario no existe o no tiene rol tutor.

        Se valida ANTES de escribir en `comision_tutor`: la FK sola dejaría
        asignar a cualquier usuario (un alumno, por ejemplo) como tutor de una
        comisión, y la pertenencia dejaría de significar algo.
        """
        from sqlalchemy import select

        from app.infrastructure.persistence.models.transactional import UsuarioModel

        usuario = (
            await session.execute(
                select(UsuarioModel).where(UsuarioModel.id == tutor_id)
            )
        ).scalar_one_or_none()
        if usuario is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "usuario_no_encontrado", "usuario_id": tutor_id},
            )
        if "tutor" not in (usuario.roles or []):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "rol_invalido",
                    "mensaje": "El usuario no tiene rol tutor.",
                },
            )

    @router.post(
        "/moodle-import",
        dependencies=[Depends(require_capability("crear_examenes"))],
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
            entidad=EntidadAuditoria.EXAMEN,
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
    # Import XML directo al banco de preguntas — SIN crear examen (C-74).
    # El banco es el destino; el examen se arma después por separado, sorteando
    # categorías/tipos desde el banco (crear-desde-banco).
    # -----------------------------------------------------------------------

    @router.post(
        "/banco/importar-xml/preview",
        dependencies=[Depends(require_capability("gestionar_banco"))],
        response_model=PreviewImportBancoResponse,
        status_code=status.HTTP_200_OK,
        summary="Preview de un XML antes de importarlo al banco — no persiste nada",
    )
    async def preview_importar_banco_xml(
        file: UploadFile = File(...),
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> PreviewImportBancoResponse:
        xml_bytes = await file.read()

        from app.application.exam_content.import_service import preview_import_banco

        try:
            report = preview_import_banco(xml_bytes)
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

        return PreviewImportBancoResponse(
            categorias=[
                PreviewCategoriaResponse(
                    ruta=c.ruta,
                    preguntas_por_tipo=c.preguntas_por_tipo,
                    preguntas=[
                        PreguntaImportadaItemResponse(enunciado=p.enunciado, tipo=p.tipo)
                        for p in c.preguntas
                    ],
                )
                for c in report.categorias
            ],
            sin_categoria_por_tipo=report.sin_categoria_por_tipo,
            omitidas=[
                OmitidaItemResponse(tipo=o.tipo, nombre=o.nombre, motivo=o.motivo)
                for o in report.omitidas
            ],
            total_preguntas=report.total_preguntas,
            sin_categoria_preguntas=[
                PreguntaImportadaItemResponse(enunciado=p.enunciado, tipo=p.tipo)
                for p in report.sin_categoria_preguntas
            ],
        )

    @router.post(
        "/banco/importar-xml",
        dependencies=[Depends(require_capability("gestionar_banco"))],
        response_model=ImportarBancoXmlResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Importa un XML de Moodle directo al banco de preguntas, sin crear examen",
    )
    async def importar_banco_xml(
        materia_id: str = Form(...),
        file: UploadFile = File(...),
        categorias_excluidas: str | None = Form(default=None),
        categoria_padre_id: str | None = Form(default=None),
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> ImportarBancoXmlResponse:
        await _exigir_pertenencia_materia(principal, materia_id)

        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        xml_bytes = await file.read()

        # categorias_excluidas viaja como JSON de rutas (list[list[str]]), igual
        # forma que PreviewCategoria.ruta — el docente las destildó en el preview.
        excluidas_set: set[tuple[str, ...]] | None = None
        if categorias_excluidas:
            import json as _json

            try:
                rutas_crudas = _json.loads(categorias_excluidas)
                excluidas_set = {tuple(r) for r in rutas_crudas}
            except (ValueError, TypeError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": "categorias_excluidas_invalido", "mensaje": str(exc)},
                ) from exc

        from app.application.exam_content.import_service import importar_banco_desde_xml
        from app.infrastructure.persistence.repositories.categoria_pregunta import (
            CategoriaPreguntaSqlRepository,
        )

        async with session_factory() as session:
            try:
                # categoria_padre_id es una categoría YA EXISTENTE elegida por el
                # docente (no un nombre tipeado): validamos que exista y sea de
                # ESTA materia antes de anidar nada ahí — evita que un id de otra
                # materia (typo/copy-paste) mezcle bancos de preguntas ajenos.
                if categoria_padre_id:
                    cat_repo = CategoriaPreguntaSqlRepository(session)
                    destino = await cat_repo.obtener(categoria_padre_id)
                    if destino is None or destino.materia_id != materia_id:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail={
                                "error": "categoria_padre_invalida",
                                "mensaje": "La categoría de destino no existe o pertenece a otra materia.",
                            },
                        )

                report = await importar_banco_desde_xml(
                    session,
                    xml_bytes,
                    materia_id,
                    categorias_excluidas=excluidas_set,
                    categoria_padre_id=categoria_padre_id,
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

        return ImportarBancoXmlResponse(
            preguntas_nuevas=report.preguntas_nuevas,
            preguntas_actualizadas=report.preguntas_actualizadas,
            omitidas=[
                OmitidaItemResponse(tipo=o.tipo, nombre=o.nombre, motivo=o.motivo)
                for o in report.omitidas
            ],
            nuevas=[
                PreguntaImportadaItemResponse(enunciado=p.enunciado, tipo=p.tipo)
                for p in report.nuevas
            ],
            actualizadas=[
                PreguntaImportadaItemResponse(enunciado=p.enunciado, tipo=p.tipo)
                for p in report.actualizadas
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
        dependencies=[Depends(require_capability("gestionar_estructura"))],
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
        dependencies=[Depends(require_capability("crear_examenes"))],
        response_model=AsociarComisionResponse,
        status_code=status.HTTP_200_OK,
        summary="Asociar un examen ya importado a una comisión existente",
    )
    async def asociar_examen_a_comision(
        examen_id: str,
        body: AsociarComisionRequest,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> AsociarComisionResponse:
        """Sin chequeo de pertenencia (bug real, C-74 post-cierre): cualquier
        docente con `gestionar_academico` podía asociar CUALQUIER examen a
        CUALQUIER comisión, sin dueño en ninguno de los dos extremos. Ahora exige
        que el docente dicte la comisión DESTINO (misma política que crear-desde-
        banco): es esa comisión la que decide a qué libreta va la nota."""
        await _exigir_pertenencia_comision(principal, body.comision_id)
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
        dependencies=[Depends(require_capability("gestionar_estructura"))],
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
            entidad=EntidadAuditoria.MATERIA,
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
        dependencies=[Depends(require_capability("gestionar_estructura"))],
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
        está en uso; 422 'validacion_dominio' si nombre/codigo son vacíos.
        Pertenencia (c-79): un coordinador solo puede editar SU materia."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        await _exigir_pertenencia_materia(principal, materia_id)

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
            entidad=EntidadAuditoria.MATERIA,
            entidad_id=str(materia_id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=f"Editó la materia {materia.nombre} ({materia.codigo})",
        )

        return MateriaResponse(
            id=materia.id, codigo=materia.codigo, nombre=materia.nombre, activa=materia.activa
        )

    # -----------------------------------------------------------------------
    # BAJA LÓGICA de materia (c-78). UN SOLO patrón en todo el sistema:
    #   DELETE /{id}            -> da de baja
    #   POST   /{id}/reactivar  -> la revierte
    # Igual que usuario y examen. Reemplaza al par anterior
    # (`PATCH /{id}/activa` + un DELETE que borraba físicamente si estaba vacía),
    # que obligaba a saber de antemano cuál de los dos usar.
    #
    # El borrado FÍSICO se eliminó a propósito: un DELETE que a veces borra y a
    # veces devuelve 409 según si la fila está vacía es un contrato impredecible.
    # Con la baja lógica la materia desaparece de todas las vistas igual, y se
    # puede volver atrás.
    # -----------------------------------------------------------------------

    @router.get(
        "/materias/{materia_id}/impacto-baja",
        dependencies=[Depends(require_capability("gestionar_estructura"))],
        response_model=ImpactoBajaResponse,
        summary="Qué alcanza dar de baja esta materia (aviso previo, no da de baja)",
    )
    async def impacto_baja_de_materia(
        materia_id: str,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> ImpactoBajaResponse:
        """Consulta para que el diálogo de confirmación diga qué se lleva puesto.

        No cambia nada: pedirla no da de baja la materia.
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        await _exigir_pertenencia_materia(principal, materia_id)

        async with session_factory() as session:
            impacto = await impacto_baja_materia(session, materia_id)
        return ImpactoBajaResponse(**asdict(impacto))

    @router.delete(
        "/materias/{materia_id}",
        dependencies=[Depends(require_capability("gestionar_estructura"))],
        status_code=status.HTTP_204_NO_CONTENT,
        response_model=None,
        summary="Dar de baja una materia (baja lógica; nada se borra)",
    )
    async def dar_de_baja_materia(
        materia_id: str,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> None:
        """Da de baja la materia: sale de los listados, no admite inscripciones
        nuevas y sus exámenes dejan de poder rendirse.

        404 si no existe o si ya estaba de baja (mismo contrato que usuario y
        examen). Nada se borra: comisiones, inscripciones, exámenes y evidencia
        quedan intactos y vuelven con `POST /{id}/reactivar`.
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        await _exigir_pertenencia_materia(principal, materia_id)

        from app.infrastructure.persistence.repositories.exam_content import (
            MateriaSqlRepository,
        )

        async with session_factory() as session:
            repo = MateriaSqlRepository(session)
            materia = await repo.obtener(materia_id)
            if materia is None or not materia.activa:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "materia_no_encontrada",
                        "mensaje": "La materia no existe o ya está dada de baja.",
                        "materia_id": materia_id,
                    },
                )
            # Misma restricción dura que el examen, un nivel más arriba: la baja
            # de la materia bloquea la rendición de TODOS sus exámenes
            # server-side, así que hacerla con gente adentro le corta el examen
            # a medio camino a alguien que no hizo nada mal.
            impacto = await impacto_baja_materia(session, materia_id)
            _rechazar_si_hay_gente_rindiendo(
                impacto.sesiones_en_curso, error="materia_en_curso", que="esta materia"
            )
            await repo.set_activa(materia_id, False)
            await session.commit()

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.MATERIA_BAJA,
            modulo=ModuloAuditoria.MATERIAS,
            entidad=EntidadAuditoria.MATERIA,
            entidad_id=str(materia_id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"Dio de baja la materia {materia.nombre} ({materia.codigo}). "
                "Nada se borró: sus comisiones y exámenes quedan conservados."
            ),
        )

    @router.post(
        "/materias/{materia_id}/reactivar",
        dependencies=[Depends(require_capability("gestionar_estructura"))],
        response_model=MateriaResponse,
        summary="Reactivar una materia dada de baja",
    )
    async def reactivar_materia(
        materia_id: str,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> MateriaResponse:
        """Revierte la baja. 404 si no existe o si ya estaba activa."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        await _exigir_pertenencia_materia(principal, materia_id)

        from app.infrastructure.persistence.repositories.exam_content import (
            MateriaSqlRepository,
        )

        async with session_factory() as session:
            repo = MateriaSqlRepository(session)
            materia = await repo.obtener(materia_id)
            if materia is None or materia.activa:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "materia_no_encontrada",
                        "mensaje": "La materia no existe o ya está activa.",
                        "materia_id": materia_id,
                    },
                )
            materia = await repo.set_activa(materia_id, True)
            respuesta = await _materia_response_con_coordinadores(session, materia)
            await session.commit()

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.MATERIA_ACTIVACION,
            modulo=ModuloAuditoria.MATERIAS,
            entidad=EntidadAuditoria.MATERIA,
            entidad_id=str(materia_id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=f"Reactivó la materia {materia.nombre} ({materia.codigo})",
        )
        return respuesta

    @router.post(
        "/materias/{materia_id}/profesores",
        dependencies=[Depends(require_capability("asignar_docente"))],
        response_model=MateriaResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Agregar un profesor a cargo de una materia (c-78, N:M)",
    )
    async def agregar_profesor_materia(
        materia_id: str,
        body: MateriaProfesorRequest,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> MateriaResponse:
        """Agrega un profesor a cargo de la materia (c-78 E-04).

        El PROFESOR arma los examenes y el banco de la materia, y supervisa en
        vivo — pero NO emite el veredicto de integridad (D11). 404 si la materia
        no existe. 422 si el usuario no existe, esta de baja, o no tiene rol
        profesor. Misma capacidad y misma pertenencia que asignar coordinador.
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        await _exigir_pertenencia_materia(principal, materia_id)

        from sqlalchemy import select

        from app.infrastructure.persistence.models.transactional import UsuarioModel
        from app.infrastructure.persistence.repositories.exam_content import (
            MateriaSqlRepository,
        )

        async with session_factory() as session:
            usuario = (
                await session.execute(
                    select(UsuarioModel).where(UsuarioModel.id == body.profesor_id)
                )
            ).scalar_one_or_none()
            if usuario is None or usuario.eliminado_en is not None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "profesor_invalido",
                        "mensaje": "El usuario no existe o esta dado de baja.",
                    },
                )
            if Rol.PROFESOR.value not in (usuario.roles or []):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "no_es_profesor",
                        "mensaje": "El usuario no tiene rol profesor.",
                    },
                )

            repo = MateriaSqlRepository(session)
            materia = await repo.obtener(materia_id)
            if materia is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "materia_no_encontrada", "materia_id": materia_id},
                )
            await repo.agregar_profesor(materia_id, body.profesor_id)
            respuesta = await _materia_response_con_coordinadores(session, materia)
            await session.commit()

        nombre_profesor = next(
            (x.nombre for x in respuesta.profesores if x.id == body.profesor_id),
            body.profesor_id,
        )
        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.MATERIA_PROFESOR,
            modulo=ModuloAuditoria.MATERIAS,
            entidad=EntidadAuditoria.MATERIA,
            entidad_id=str(materia_id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"Agrego a {nombre_profesor} como profesor de la materia "
                f"{materia.nombre} ({materia.codigo})"
            ),
        )
        return respuesta

    @router.delete(
        "/materias/{materia_id}/profesores/{profesor_id}",
        dependencies=[Depends(require_capability("asignar_docente"))],
        response_model=MateriaResponse,
        summary="Quitar un profesor a cargo de una materia (c-78, N:M)",
    )
    async def quitar_profesor_materia(
        materia_id: str,
        profesor_id: str,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> MateriaResponse:
        """Quita un profesor de la materia. 404 si la materia no existe."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        await _exigir_pertenencia_materia(principal, materia_id)

        from app.infrastructure.persistence.repositories.exam_content import (
            ComisionSqlRepository,
            MateriaSqlRepository,
        )

        async with session_factory() as session:
            repo = MateriaSqlRepository(session)
            materia = await repo.obtener(materia_id)
            if materia is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "materia_no_encontrada", "materia_id": materia_id},
                )
            nombres_antes = await ComisionSqlRepository(session).nombres_de_docentes(
                [profesor_id]
            )
            await repo.quitar_profesor(materia_id, profesor_id)
            respuesta = await _materia_response_con_coordinadores(session, materia)
            await session.commit()

        nombre_profesor = nombres_antes.get(profesor_id, profesor_id)
        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.MATERIA_PROFESOR,
            modulo=ModuloAuditoria.MATERIAS,
            entidad=EntidadAuditoria.MATERIA,
            entidad_id=str(materia_id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"Quito a {nombre_profesor} como profesor de la materia "
                f"{materia.nombre} ({materia.codigo})"
            ),
        )
        return respuesta

    @router.post(
        "/materias/{materia_id}/coordinadores",
        dependencies=[Depends(require_capability("asignar_docente"))],
        response_model=MateriaResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Agregar un coordinador a cargo de una materia (c-79, N:M)",
    )
    async def agregar_coordinador_materia(
        materia_id: str,
        body: MateriaCoordinadorRequest,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> MateriaResponse:
        """Agrega un coordinador a cargo de la materia. c-79: el coordinador dejó
        de tener alcance global — queda acotado a SUS materias asignadas, igual
        que el tutor a sus comisiones. Una materia puede tener varios
        coordinadores. 404 si la materia no existe. 422 si el usuario no existe,
        está de baja, o no tiene rol coordinador. Pertenencia: un coordinador
        solo puede agregar coordinadores a SU PROPIA materia (no a una ajena);
        una materia sin coordinador asignado todavía solo puede recibir el
        primero de la mano de admin_sistema (mismo patrón que `asignar_docente`
        sobre una comisión sin dueño)."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        await _exigir_pertenencia_materia(principal, materia_id)

        from sqlalchemy import select

        from app.infrastructure.persistence.models.transactional import UsuarioModel
        from app.infrastructure.persistence.repositories.exam_content import (
            MateriaSqlRepository,
        )

        async with session_factory() as session:
            usuario = (
                await session.execute(
                    select(UsuarioModel).where(UsuarioModel.id == body.coordinador_id)
                )
            ).scalar_one_or_none()
            if usuario is None or usuario.eliminado_en is not None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "coordinador_invalido",
                        "mensaje": "El usuario no existe o está dado de baja.",
                    },
                )
            if Rol.COORDINADOR.value not in (usuario.roles or []):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "no_es_coordinador",
                        "mensaje": "El usuario no tiene rol coordinador.",
                    },
                )

            repo = MateriaSqlRepository(session)
            materia = await repo.obtener(materia_id)
            if materia is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "materia_no_encontrada", "materia_id": materia_id},
                )
            await repo.agregar_coordinador(materia_id, body.coordinador_id)
            respuesta = await _materia_response_con_coordinadores(session, materia)
            await session.commit()

        nombre_coordinador = next(
            (c.nombre for c in respuesta.coordinadores if c.id == body.coordinador_id),
            body.coordinador_id,
        )
        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.MATERIA_COORDINADOR,
            modulo=ModuloAuditoria.MATERIAS,
            entidad=EntidadAuditoria.MATERIA,
            entidad_id=str(materia_id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"Agregó a {nombre_coordinador} como coordinador de la materia "
                f"{materia.nombre} ({materia.codigo})"
            ),
        )
        return respuesta

    @router.delete(
        "/materias/{materia_id}/coordinadores/{coordinador_id}",
        dependencies=[Depends(require_capability("asignar_docente"))],
        response_model=MateriaResponse,
        summary="Quitar un coordinador a cargo de una materia (c-79, N:M)",
    )
    async def quitar_coordinador_materia(
        materia_id: str,
        coordinador_id: str,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> MateriaResponse:
        """Quita un coordinador de la materia. 404 si la materia no existe.
        Pertenencia: acotado a SU materia (ver `agregar_coordinador_materia`)."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        await _exigir_pertenencia_materia(principal, materia_id)

        from app.infrastructure.persistence.repositories.exam_content import (
            ComisionSqlRepository,
            MateriaSqlRepository,
        )

        async with session_factory() as session:
            repo = MateriaSqlRepository(session)
            materia = await repo.obtener(materia_id)
            if materia is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "materia_no_encontrada", "materia_id": materia_id},
                )
            nombres_antes = await ComisionSqlRepository(session).nombres_de_docentes(
                [coordinador_id]
            )
            await repo.quitar_coordinador(materia_id, coordinador_id)
            respuesta = await _materia_response_con_coordinadores(session, materia)
            await session.commit()

        nombre_coordinador = nombres_antes.get(coordinador_id, coordinador_id)
        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.MATERIA_COORDINADOR,
            modulo=ModuloAuditoria.MATERIAS,
            entidad=EntidadAuditoria.MATERIA,
            entidad_id=str(materia_id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"Quitó a {nombre_coordinador} como coordinador de la materia "
                f"{materia.nombre} ({materia.codigo})"
            ),
        )
        return respuesta

    @router.post(
        "/materias/{materia_id}/comisiones",
        dependencies=[Depends(require_capability("gestionar_estructura"))],
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
        'validacion_dominio' si codigo/nombre son vacíos. Pertenencia (c-79): un
        coordinador solo puede crear comisiones en SU materia."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        await _exigir_pertenencia_materia(principal, materia_id)

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
                # Para el propósito del audit log (qué materia recibió la comisión).
                from app.infrastructure.persistence.repositories.exam_content import (
                    MateriaSqlRepository,
                )

                materia_de_comision = await MateriaSqlRepository(session).obtener(materia_id)
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
            entidad=EntidadAuditoria.COMISION,
            entidad_id=str(comision.id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"Creó la comisión {comision.nombre} ({comision.codigo}) "
                f"en {materia_de_comision.nombre if materia_de_comision else materia_id}"
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

    @router.patch(
        "/comisiones/{comision_id}",
        response_model=ComisionResponse,
        dependencies=[Depends(require_capability("gestionar_estructura"))],
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
        materia NO se tocan. Pertenencia (c-79): tutor de esa comisión, o
        coordinador de su materia (GAP real: antes de c-79 este endpoint no
        tenía NINGÚN chequeo de pertenencia — cualquier tutor editaba la
        comisión de otro)."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        await _exigir_pertenencia_comision(principal, comision_id)

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
            entidad=EntidadAuditoria.COMISION,
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

    @router.post(
        "/comisiones/{comision_id}/tutores",
        dependencies=[Depends(require_capability("gestionar_estructura"))],
        response_model=ComisionResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Agregar un tutor a cargo de una comisión (c-79, N:M)",
    )
    async def agregar_tutor_comision(
        comision_id: str,
        body: ComisionTutorRequest,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(
            require_capability("asignar_docente")
        ),
    ) -> ComisionResponse:
        """Agrega un tutor a cargo de la comisión. Una comisión puede tener
        VARIOS tutores (co-dictado, cobertura de licencias) — reemplaza al viejo
        PUT .../docente que solo permitía uno (c-79).

        Requiere la capacidad `asignar_docente`, que NO tiene el rol TUTOR: si un
        tutor pudiera asignarse a sí mismo, la validación de pertenencia dejaría
        de ser un control.

        404 si la comisión no existe. 422 si el usuario no existe, está dado de
        baja, o no tiene rol tutor. Idempotente: agregar dos veces al mismo tutor
        no duplica ni falla. Pertenencia: un coordinador solo puede agregar
        tutores a comisiones de SU materia (no a una ajena)."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        await _exigir_pertenencia_comision(principal, comision_id)

        from app.infrastructure.persistence.repositories.exam_content import (
            ComisionSqlRepository,
        )

        async with session_factory() as session:
            await _validar_usuario_tutor(session, body.tutor_id)
            repo = ComisionSqlRepository(session)
            comision = await repo.obtener(comision_id)
            if comision is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "comision_no_encontrada",
                        "comision_id": comision_id,
                    },
                )
            await repo.agregar_tutor(comision_id, body.tutor_id)
            respuesta = await _comision_response_con_tutores(repo, comision)
            await session.commit()

        nombre_tutor = next(
            (t.nombre for t in respuesta.tutores if t.id == body.tutor_id), body.tutor_id
        )
        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.COMISION_DOCENTE,
            modulo=ModuloAuditoria.MATERIAS,
            entidad=EntidadAuditoria.COMISION,
            entidad_id=str(comision_id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"Agregó a {nombre_tutor} como tutor a cargo de la comisión "
                f"{comision.nombre} ({comision.codigo})"
            ),
        )
        return respuesta

    @router.delete(
        "/comisiones/{comision_id}/tutores/{tutor_id}",
        dependencies=[Depends(require_capability("gestionar_estructura"))],
        response_model=ComisionResponse,
        summary="Quitar un tutor a cargo de una comisión (c-79, N:M)",
    )
    async def quitar_tutor_comision(
        comision_id: str,
        tutor_id: str,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(
            require_capability("asignar_docente")
        ),
    ) -> ComisionResponse:
        """Quita un tutor de la comisión. 404 si la comisión no existe. Idempotente:
        quitar a alguien que no estaba a cargo no falla, solo no cambia nada.
        Pertenencia: acotado a SU materia (ver `agregar_tutor_comision`)."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        await _exigir_pertenencia_comision(principal, comision_id)

        from app.infrastructure.persistence.repositories.exam_content import (
            ComisionSqlRepository,
        )

        async with session_factory() as session:
            repo = ComisionSqlRepository(session)
            comision = await repo.obtener(comision_id)
            if comision is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "comision_no_encontrada",
                        "comision_id": comision_id,
                    },
                )
            nombres_antes = await repo.nombres_de_docentes([tutor_id])
            await repo.quitar_tutor(comision_id, tutor_id)
            respuesta = await _comision_response_con_tutores(repo, comision)
            await session.commit()

        nombre_tutor = nombres_antes.get(tutor_id, tutor_id)
        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.COMISION_DOCENTE,
            modulo=ModuloAuditoria.MATERIAS,
            entidad=EntidadAuditoria.COMISION,
            entidad_id=str(comision_id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"Quitó a {nombre_tutor} como tutor a cargo de la comisión "
                f"{comision.nombre} ({comision.codigo})"
            ),
        )
        return respuesta

    @router.get(
        "/comisiones/{comision_id}/impacto-baja",
        dependencies=[Depends(require_capability("gestionar_estructura"))],
        response_model=ImpactoBajaResponse,
        summary="Qué alcanza dar de baja esta comisión (aviso previo, no da de baja)",
    )
    async def impacto_baja_de_comision(
        comision_id: str,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> ImpactoBajaResponse:
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        await _exigir_pertenencia_comision(principal, comision_id)

        async with session_factory() as session:
            impacto = await impacto_baja_comision(session, comision_id)
        return ImpactoBajaResponse(**asdict(impacto))

    @router.delete(
        "/comisiones/{comision_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(require_capability("gestionar_estructura"))],
        response_model=None,
        summary="Dar de baja una comisión (baja lógica; nada se borra)",
    )
    async def dar_de_baja_comision(
        comision_id: str,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> None:
        """Da de baja la comisión: no admite inscripciones nuevas por su código y
        sus exámenes dejan de poder rendirse. La materia y las demás comisiones
        siguen igual.

        404 si no existe o si ya estaba de baja (mismo contrato que materia,
        usuario y examen). No desmatricula a nadie ni borra nada: todo vuelve con
        `POST /{id}/reactivar`.
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        await _exigir_pertenencia_comision(principal, comision_id)

        from app.infrastructure.persistence.repositories.exam_content import (
            ComisionSqlRepository,
        )

        async with session_factory() as session:
            repo = ComisionSqlRepository(session)
            comision = await repo.obtener(comision_id)
            if comision is None or not comision.activa:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "comision_no_encontrada",
                        "mensaje": "La comisión no existe o ya está dada de baja.",
                        "comision_id": comision_id,
                    },
                )
            impacto = await impacto_baja_comision(session, comision_id)
            _rechazar_si_hay_gente_rindiendo(
                impacto.sesiones_en_curso,
                error="comision_en_curso",
                que="esta comisión",
            )
            await repo.set_activa(comision_id, False)
            await session.commit()

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.COMISION_BAJA,
            modulo=ModuloAuditoria.MATERIAS,
            entidad=EntidadAuditoria.COMISION,
            entidad_id=str(comision_id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"Dio de baja la comisión {comision.nombre} ({comision.codigo}). "
                "Nada se borró: sus inscriptos y exámenes quedan conservados."
            ),
        )

    @router.post(
        "/comisiones/{comision_id}/reactivar",
        dependencies=[Depends(require_capability("gestionar_estructura"))],
        response_model=ComisionResponse,
        summary="Reactivar una comisión dada de baja",
    )
    async def reactivar_comision(
        comision_id: str,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> ComisionResponse:
        """Revierte la baja. 404 si no existe o si ya estaba activa."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        await _exigir_pertenencia_comision(principal, comision_id)

        from app.infrastructure.persistence.repositories.exam_content import (
            ComisionSqlRepository,
        )

        async with session_factory() as session:
            repo = ComisionSqlRepository(session)
            comision = await repo.obtener(comision_id)
            if comision is None or comision.activa:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "comision_no_encontrada",
                        "mensaje": "La comisión no existe o ya está activa.",
                        "comision_id": comision_id,
                    },
                )
            comision = await repo.set_activa(comision_id, True)
            respuesta = ComisionResponse(
                id=comision.id,
                materia_id=comision.materia_id,
                codigo=comision.codigo,
                nombre=comision.nombre,
                periodo=comision.periodo,
                anio=comision.anio,
                codigo_matriculacion=comision.codigo_matriculacion,
                activa=comision.activa,
            )
            await session.commit()

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.COMISION_ACTIVACION,
            modulo=ModuloAuditoria.MATERIAS,
            entidad=EntidadAuditoria.COMISION,
            entidad_id=str(comision_id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=f"Reactivó la comisión {comision.nombre} ({comision.codigo})",
        )
        return respuesta

    # -----------------------------------------------------------------------
    # Rotación del código de matriculación (C-70, D5) — admin-only.
    # Regenera un código único y reemplaza el anterior; las inscripciones
    # existentes quedan INTACTAS (rotar no desmatricula a nadie).
    # -----------------------------------------------------------------------

    @router.post(
        "/comisiones/{comision_id}/rotar-codigo",
        dependencies=[Depends(require_capability("gestionar_estructura"))],
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
        dependencies=[Depends(require_capability("gestionar_estructura"))],
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
        Pertenencia (c-79): tutor de esa comisión, o coordinador de su materia.
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        await _exigir_pertenencia_comision(principal, comision_id)

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
            # MATERIAS, no EXAMENES: coincide con modulo_de_accion() (prefijo
            # "inscripcion.") y con la categorización del filtro de Auditoría en el
            # frontend (ACCIONES_POR_MODULO.MATERIAS incluye inscripcion.create) —
            # antes quedaba en EXAMENES y el filtro por módulo Materias no la traía.
            modulo=ModuloAuditoria.MATERIAS,
            entidad=EntidadAuditoria.INSCRIPCION,
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
        dependencies=[Depends(require_capability("gestionar_estructura"))],
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
        Pertenencia (c-79): tutor de esa comisión, o coordinador de su materia.
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        await _exigir_pertenencia_comision(principal, comision_id)

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
            modulo=ModuloAuditoria.MATERIAS,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=f"Quitó al alumno {usuario_id} de la comisión {comision_id}",
        )

    def _subtitulo_comision(comision, materia) -> str:
        """Encabezado del export: de qué comisión y materia es este listado."""
        if comision is None:
            return "Comisión no encontrada"
        partes = [f"{comision.codigo} - {comision.nombre}"]
        if materia is not None:
            partes.append(f"{materia.codigo} - {materia.nombre}")
        if comision.periodo or comision.anio:
            partes.append(
                " ".join(str(x) for x in (comision.periodo, comision.anio) if x)
            )
        return " | ".join(partes)

    def _slug(obj) -> str:
        """Trozo seguro para el nombre de archivo (sin acentos ni espacios)."""
        import re
        import unicodedata

        crudo = getattr(obj, "codigo", None) or getattr(obj, "titulo", None) or "listado"
        plano = unicodedata.normalize("NFKD", str(crudo)).encode("ascii", "ignore").decode()
        return re.sub(r"[^A-Za-z0-9._-]+", "-", plano).strip("-").lower() or "listado"

    def _alumno_a_response(a) -> AlumnoElegibilidadResponse:
        return AlumnoElegibilidadResponse(
            usuario_id=a.usuario_id,
            username=a.username,
            nombre=a.nombre,
            apellido=a.apellido,
            email=a.email,
            consentimiento_vigente=a.consentimiento_vigente,
            biometria_vigente=a.biometria_vigente,
            puede_rendir=a.puede_rendir,
            razon=a.razon,
            inscripto_en=getattr(a, "inscripto_en", None),
        )

    async def _alumnos_de_comision(principal, comision_id: str) -> list:
        """Inscriptos con elegibilidad, tras validar pertenencia. 404 si no existe."""
        await _exigir_pertenencia_comision(principal, comision_id)
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        async with session_factory() as session:
            service = _build_inscripcion_service(session)
            try:
                return await service.listar_alumnos_con_elegibilidad(comision_id)
            except ComisionNoEncontradaError as exc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "comision_no_encontrada", "comision_id": comision_id},
                ) from exc

    async def _comision_para_export(comision_id: str):
        """Comisión + nombre de materia, para el encabezado de los exports."""
        from app.infrastructure.persistence.repositories.exam_content import (
            ComisionSqlRepository,
            MateriaSqlRepository,
        )

        async with session_factory() as session:
            comision = await ComisionSqlRepository(session).obtener(comision_id)
            materia = (
                await MateriaSqlRepository(session).obtener(comision.materia_id)
                if comision
                else None
            )
        return comision, materia

    @router.get(
        "/comisiones/{comision_id}/alumnos",
        response_model=AlumnosComisionPaginadosResponse,
        summary="Listar los inscriptos de una comisión (paginado) con su elegibilidad",
    )
    async def listar_alumnos_de_comision(
        comision_id: str,
        page: int = 1,
        page_size: int = 25,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> AlumnosComisionPaginadosResponse:
        """Lista PAGINADA de los alumnos inscriptos, con su elegibilidad.

        Por cada alumno: puede_rendir = consentimiento vigente + biometría vigente
        (resuelto server-side); razon describe qué falta cuando no puede. 404
        'comision_no_encontrada' si la comisión no existe.

        c-78 §13.2: la paginación es NUEVA. Con 40 alumnos por comisión el listado
        completo era ilegible. `page_size` alto (>= total) devuelve todo, así que
        un consumidor que quiera la lista entera la sigue pudiendo pedir.

        La elegibilidad se resuelve por alumno (consentimiento + biometría), así
        que el recorte se hace DESPUÉS de calcularla: `total` cuenta a todos los
        inscriptos, no solo a los de la página.
        """
        alumnos = await _alumnos_de_comision(principal, comision_id)
        pagina_actual = max(1, page)
        tamano = max(1, page_size)
        inicio = (pagina_actual - 1) * tamano
        return AlumnosComisionPaginadosResponse(
            items=[_alumno_a_response(a) for a in alumnos[inicio : inicio + tamano]],
            total=len(alumnos),
            page=pagina_actual,
            page_size=tamano,
        )

    # -----------------------------------------------------------------------
    # Exports académicos (c-78 §13.4/§13.5, E-10)
    #
    # Existen porque hay campus SIN API: la nota se carga a mano y para eso hace
    # falta el listado en un archivo. El PDF es para mirar/imprimir (recorta los
    # textos largos); el Excel es el archivo completo.
    #
    # PRIVACIDAD: llevan datos personales de alumnos. Va lo MÍNIMO para el
    # propósito declarado (identificar a la persona en el campus): ni scores de
    # proctoring, ni eventos, ni evidencia.
    # -----------------------------------------------------------------------

    @router.get(
        "/comisiones/{comision_id}/alumnos/export.xlsx",
        summary="Exportar los inscriptos de una comisión a Excel",
    )
    async def exportar_alumnos_comision_xlsx(
        comision_id: str,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> Response:
        alumnos = await _alumnos_de_comision(principal, comision_id)
        comision, materia = await _comision_para_export(comision_id)
        contenido = tabla_a_xlsx(
            titulo="Inscriptos de la comisión — Active Exam",
            subtitulo=_subtitulo_comision(comision, materia),
            columnas=COLUMNAS_INSCRIPTOS,
            filas=filas_inscriptos(alumnos),
            nombre_hoja="Inscriptos",
        )
        return Response(
            content=contenido,
            media_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            headers={
                "Content-Disposition": (
                    f'attachment; filename="inscriptos-{_slug(comision)}.xlsx"'
                )
            },
        )

    @router.get(
        "/comisiones/{comision_id}/alumnos/export.pdf",
        summary="Exportar los inscriptos de una comisión a PDF",
    )
    async def exportar_alumnos_comision_pdf(
        comision_id: str,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> Response:
        alumnos = await _alumnos_de_comision(principal, comision_id)
        comision, materia = await _comision_para_export(comision_id)
        contenido = tabla_a_pdf(
            titulo="Inscriptos de la comisión - Active Exam",
            subtitulo=_subtitulo_comision(comision, materia),
            columnas=COLUMNAS_INSCRIPTOS,
            filas=filas_inscriptos(alumnos),
        )
        return Response(
            content=contenido,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="inscriptos-{_slug(comision)}.pdf"'
                )
            },
        )

    # -----------------------------------------------------------------------
    # Destino de write-back a Moodle POR EXAMEN (C-69, D12 parte B) — admin-only.
    # Permite fijar/leer moodle_courseid/cmid de un examen ya importado. Valores
    # AUTORITATIVOS: el write-back los usa; NULL → fallback al global de config_activeexam.
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
        """C-73 §9: el TUTOR solo opera los exámenes de SUS comisiones; el
        COORDINADOR, los de SUS materias (c-79, N:M).

        La capacidad (`gestionar_academico`) dice QUÉ puede hacer el rol; esto dice
        SOBRE QUÉ. Sin esta segunda pregunta, un tutor/coordinador redirige la nota
        de un examen ajeno a la libreta que quiera. Solo admin_sistema es de
        alcance institucional (ver `autorizar_docente_sobre_examen`)."""
        from app.domain.auth.authorization import (
            _ROLES_SIN_LIMITE_DE_PERTENENCIA,
            autorizar_docente_sobre_examen,
        )
        from app.domain.auth.errors import ForbiddenError
        from app.domain.auth.roles import Rol
        from app.infrastructure.persistence.repositories.exam_content import (
            ComisionSqlRepository,
        )

        if principal.tiene_algun_rol(_ROLES_SIN_LIMITE_DE_PERTENENCIA):
            autorizar_docente_sobre_examen(principal, True)
            return
        es_coordinador = principal.tiene_rol(Rol.COORDINADOR)
        # c-78: el PROFESOR es rol de MATERIA (materia_profesor). Se consulta
        # aparte del coordinador a propósito — son membresías distintas que
        # otorgan cosas distintas (D11: el profesor NO emite veredicto).
        es_profesor = principal.tiene_rol(Rol.PROFESOR)
        async with session_factory() as session:
            tiene_pertenencia = await ComisionSqlRepository(
                session
            ).tiene_pertenencia_sobre_examen(
                principal.subject or "",
                examen_id,
                es_coordinador=es_coordinador,
                es_profesor=es_profesor,
            )
        try:
            autorizar_docente_sobre_examen(principal, tiene_pertenencia)
        except ForbiddenError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "examen_ajeno", "mensaje": str(exc)},
            ) from exc

    async def _exigir_pertenencia_materia(principal, materia_id: str) -> None:
        """C-74: tutor solo opera el banco de su propia materia (compartido por
        todas SUS comisiones de esa materia — el banco no se re-sube por comisión).
        Coordinador: su propia materia asignada (c-79)."""
        from app.domain.auth.authorization import (
            _ROLES_SIN_LIMITE_DE_PERTENENCIA,
            autorizar_docente_sobre_materia,
        )
        from app.domain.auth.errors import ForbiddenError
        from app.domain.auth.roles import Rol
        from app.infrastructure.persistence.repositories.exam_content import (
            ComisionSqlRepository,
            MateriaSqlRepository,
        )
        # Corta ANTES de tocar la DB para los roles de alcance institucional: la
        # query mete `principal.subject` en un WHERE tipado UUID, y ese subject
        # no es un UUID real para roles que no son docente (staff, tests, etc.) —
        # evaluarla igual rompe con un error de tipo en vez de simplemente pasar.
        if principal.tiene_algun_rol(_ROLES_SIN_LIMITE_DE_PERTENENCIA):
            autorizar_docente_sobre_materia(principal, True)
            return
        async with session_factory() as session:
            materia_repo = MateriaSqlRepository(session)
            if principal.tiene_rol(Rol.PROFESOR):
                # c-78: el banco es materia-wide y el PROFESOR es exactamente el
                # rol que lo arma — pertenece si tiene la materia asignada.
                es_miembro = await materia_repo.es_profesor_de_materia(
                    principal.subject or "", materia_id
                )
            elif principal.tiene_rol(Rol.COORDINADOR):
                es_miembro = await materia_repo.es_coordinador_de_materia(
                    principal.subject or "", materia_id
                )
            else:
                es_miembro = await ComisionSqlRepository(session).es_docente_de_materia(
                    principal.subject or "", materia_id
                )
        try:
            autorizar_docente_sobre_materia(principal, es_miembro)
        except ForbiddenError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "materia_ajena", "mensaje": str(exc)},
            ) from exc

    async def _exigir_pertenencia_comision(principal, comision_id: str) -> None:
        """C-74 post-cierre: un examen apunta a UNA comisión — el tutor debe
        dictar ESA comisión puntual (o el coordinador, tener su materia), no
        alcanza con compartir materia/banco con otro tutor de una comisión
        distinta de la misma materia (c-79)."""
        from app.domain.auth.authorization import (
            _ROLES_SIN_LIMITE_DE_PERTENENCIA,
            autorizar_docente_sobre_comision,
        )
        from app.domain.auth.errors import ForbiddenError
        from app.domain.auth.roles import Rol
        from app.infrastructure.persistence.repositories.exam_content import (
            ComisionSqlRepository,
        )
        if principal.tiene_algun_rol(_ROLES_SIN_LIMITE_DE_PERTENENCIA):
            autorizar_docente_sobre_comision(principal, True)
            return
        es_coordinador = principal.tiene_rol(Rol.COORDINADOR)
        es_profesor = principal.tiene_rol(Rol.PROFESOR)
        async with session_factory() as session:
            tiene_pertenencia = await ComisionSqlRepository(
                session
            ).tiene_pertenencia_sobre_comision(
                principal.subject or "",
                comision_id,
                es_coordinador=es_coordinador,
                es_profesor=es_profesor,
            )
        try:
            autorizar_docente_sobre_comision(principal, tiene_pertenencia)
        except ForbiddenError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "comision_ajena", "mensaje": str(exc)},
            ) from exc

    # -----------------------------------------------------------------------
    # Baja lógica / reactivación del examen (c-78 D1). Mismo par que
    # DELETE /users/{id} + POST /users/{id}/reactivar: soft-delete sobre
    # `eliminado_en`, 404 si la operación ya está aplicada, y auditoría.
    #
    # D2: la baja es ADMINISTRATIVA. No toca sesiones, eventos, capturas ni
    # notas — esa evidencia sigue existiendo y consultable por id (reglas duras
    # #6/#7). Solo saca al examen de los listados y del conteo de inventario.
    # -----------------------------------------------------------------------

    async def _titulo_de_examen(examen_id: str) -> str:
        """Título visible del examen para el propósito auditado; cae al id."""
        from app.infrastructure.persistence.repositories.exam_content import (
            ExamenContenidoSqlRepository,
        )

        async with session_factory() as session:
            resumen = await ExamenContenidoSqlRepository(session).obtener_resumen(
                examen_id
            )
        return getattr(resumen, "titulo", None) or examen_id

    @router.get(
        "/{examen_id}/impacto-baja",
        dependencies=[Depends(require_capability("crear_examenes"))],
        response_model=ImpactoBajaResponse,
        summary="Qué alcanza dar de baja este examen (aviso previo, no da de baja)",
    )
    async def impacto_baja_de_examen(
        examen_id: str,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> ImpactoBajaResponse:
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        await _exigir_pertenencia(principal, examen_id)

        async with session_factory() as session:
            impacto = await impacto_baja_examen(session, examen_id)
        return ImpactoBajaResponse(**asdict(impacto))

    @router.delete(
        "/{examen_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(require_capability("crear_examenes"))],
        response_model=None,
        summary="Dar de baja un examen (baja lógica; la evidencia se conserva)",
    )
    async def dar_de_baja_examen(
        examen_id: str,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> None:
        """Baja lógica del examen: setea ``eliminado_en = now()``.

        404 si el examen no existe o ya estaba dado de baja. La fila NO se borra:
        sus sesiones, eventos, capturas y notas quedan intactas (D2).
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        await _exigir_pertenencia(principal, examen_id)

        from app.infrastructure.persistence.repositories.exam_content import (
            ExamenContenidoSqlRepository,
        )

        # El título se lee ANTES de la baja: después sigue disponible, pero
        # leerlo acá deja el propósito auditado con el nombre que tenía al
        # momento de la operación.
        titulo = await _titulo_de_examen(examen_id)

        # RESTRICCIÓN DURA (c-78): no se da de baja un examen que se está
        # rindiendo AHORA. La baja bloquea la rendición server-side (el
        # enforcement responde 410), así que hacerla con gente adentro le corta
        # el examen a medio camino a alguien que no hizo nada mal. Se rechaza
        # con 409 y el número de sesiones en curso, para que quien lo intenta
        # sepa a cuántos iba a afectar.
        #
        # OJO: la restricción es "en curso", NO "rendido alguna vez". Un examen
        # con sesiones YA FINALIZADAS sí se puede dar de baja — ese es
        # justamente el caso que motivó la baja lógica (el hard-delete exigía
        # estar vacío y por eso era inservible). La evidencia queda intacta.
        async with session_factory() as session:
            impacto = await impacto_baja_examen(session, examen_id)
            _rechazar_si_hay_gente_rindiendo(
                impacto.sesiones_en_curso, error="examen_en_curso", que="este examen"
            )

        async with session_factory() as session:
            dado_de_baja = await ExamenContenidoSqlRepository(session).dar_de_baja(
                examen_id
            )
            if not dado_de_baja:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "examen_no_encontrado",
                        "mensaje": "El examen no existe o ya está dado de baja.",
                        "examen_id": examen_id,
                    },
                )
            await session.commit()

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.EXAMEN_BAJA,
            modulo=ModuloAuditoria.EXAMENES,
            entidad=EntidadAuditoria.EXAMEN,
            entidad_id=str(examen_id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"Dio de baja el examen «{titulo}» "
                "(sale del catálogo; su evidencia se conserva)"
            ),
        )

    @router.post(
        "/{examen_id}/reactivar",
        dependencies=[Depends(require_capability("crear_examenes"))],
        status_code=status.HTTP_204_NO_CONTENT,
        response_model=None,
        summary="Reactivar un examen dado de baja",
    )
    async def reactivar_examen(
        examen_id: str,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> None:
        """Revierte la baja lógica: ``eliminado_en = NULL``.

        404 si el examen no existe o ya estaba activo.
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        await _exigir_pertenencia(principal, examen_id)

        from app.infrastructure.persistence.repositories.exam_content import (
            ExamenContenidoSqlRepository,
        )

        titulo = await _titulo_de_examen(examen_id)

        async with session_factory() as session:
            reactivado = await ExamenContenidoSqlRepository(session).reactivar(examen_id)
            if not reactivado:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "examen_no_encontrado",
                        "mensaje": "El examen no existe o ya está activo.",
                        "examen_id": examen_id,
                    },
                )
            await session.commit()

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.EXAMEN_REACTIVAR,
            modulo=ModuloAuditoria.EXAMENES,
            entidad=EntidadAuditoria.EXAMEN,
            entidad_id=str(examen_id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=f"Reactivó el examen «{titulo}» (vuelve al catálogo)",
        )

    # -----------------------------------------------------------------------
    # Duplicar un examen (c-78 E-06, task 14.2).
    #
    # Lo que la copia hereda: las preguntas (con sus opciones y blanks) y la
    # configuración de mecánica y nota. Lo que NO hereda es todo lo que le
    # pertenece al original y nada más que a él: los intentos rendidos, las notas
    # ya publicadas y el destino de write-back en Moodle. Heredar el `cmid` haría
    # que la copia escriba encima de las notas del original.
    # -----------------------------------------------------------------------

    @router.post(
        "/{examen_id}/duplicar",
        dependencies=[Depends(require_capability("crear_examenes"))],
        response_model=DuplicarExamenResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Duplicar un examen con sus preguntas, sin arrastrar intentos ni notas",
    )
    async def duplicar_examen(
        examen_id: str,
        body: DuplicarExamenRequest,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> DuplicarExamenResponse:
        """Crea un examen nuevo con el contenido del original.

        Sin ``titulo`` la copia se llama «… (copia)»; sin ``comision_id`` queda en
        la comisión del original. La comisión destino tiene que ser de la misma
        materia: el contenido salió de ESE banco.

        404 si el examen no existe o está dado de baja (primero se reactiva).
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        await _exigir_pertenencia(principal, examen_id)
        if body.comision_id is not None:
            await _exigir_pertenencia_comision(principal, body.comision_id)

        from sqlalchemy import select as _select
        from sqlalchemy.orm import selectinload as _selectinload
        from app.infrastructure.persistence.models.exam_content import (
            ComisionModel,
            ExamenContenidoModel,
            PreguntaClozeBlankModel,
            PreguntaExamenModel,
        )

        async with session_factory() as session:
            original = (
                await session.execute(
                    _select(ExamenContenidoModel)
                    .where(
                        ExamenContenidoModel.id == examen_id,
                        ExamenContenidoModel.eliminado_en.is_(None),
                    )
                    .options(
                        _selectinload(ExamenContenidoModel.preguntas).selectinload(
                            PreguntaExamenModel.opciones
                        ),
                        _selectinload(ExamenContenidoModel.preguntas)
                        .selectinload(PreguntaExamenModel.blanks_cloze)
                        .selectinload(PreguntaClozeBlankModel.opciones_cloze),
                    )
                )
            ).scalar_one_or_none()

            if original is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "examen_no_encontrado",
                        "mensaje": "El examen no existe o está dado de baja.",
                        "examen_id": examen_id,
                    },
                )

            destino_comision = (
                body.comision_id if body.comision_id is not None else original.comision_id
            )

            # La copia no puede cruzar de materia: sus preguntas salieron del banco
            # de la materia del original y en otra no significan nada.
            if body.comision_id is not None and original.comision_id is not None:
                materias = await session.execute(
                    _select(ComisionModel.id, ComisionModel.materia_id).where(
                        ComisionModel.id.in_([body.comision_id, original.comision_id])
                    )
                )
                por_comision = {r[0]: r[1] for r in materias.all()}
                if por_comision.get(body.comision_id) != por_comision.get(
                    original.comision_id
                ):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={
                            "error": "comision_de_otra_materia",
                            "mensaje": (
                                "La copia tiene que quedar en una comisión de la misma "
                                "materia: sus preguntas salieron de ese banco."
                            ),
                            "comision_id": body.comision_id,
                        },
                    )

            titulo_copia = body.titulo or f"{original.titulo} (copia)"
            titulo_original = original.titulo
            # La copia es un examen suelto: no entra al lote del original. Duplicar
            # es "otra fecha / otra toma", no "una comisión más de este examen"
            # (eso es POST /{examen_id}/comisiones).
            copia_id, total_preguntas = await _clonar_examen(
                session,
                original,
                titulo=titulo_copia,
                comision_id=destino_comision,
                lote_replica_id=None,
            )
            await session.commit()

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.EXAMEN_DUPLICACION,
            modulo=ModuloAuditoria.EXAMENES,
            entidad=EntidadAuditoria.EXAMEN,
            entidad_id=copia_id,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"Duplicó el examen «{titulo_original}» como «{titulo_copia}» "
                f"({total_preguntas} preguntas, sin intentos ni destino de Moodle)"
            ),
        )

        return DuplicarExamenResponse(
            examen_id=copia_id,
            titulo=titulo_copia,
            comision_id=destino_comision,
            total_preguntas=total_preguntas,
        )

    # -----------------------------------------------------------------------
    # Cómo resuelve sus preguntas un examen (c-78 E-07/E-08, tasks 15.1/15.4).
    #
    # Devuelve el desglose por tramo (cuántas hay en el pool contra cuántas se
    # sortean) y si el banco creció desde que se armó. El pool queda CONGELADO a
    # propósito: es lo que garantiza que tocar el banco no rompa un examen. Este
    # endpoint es el que hace visible esa decisión en vez de dejarla silenciosa.
    # -----------------------------------------------------------------------

    @router.get(
        "/{examen_id}/sorteo",
        dependencies=[Depends(require_capability("crear_examenes"))],
        response_model=SorteoDelExamenResponse,
        summary="Desglose del sorteo del examen y estado de su pool",
    )
    async def leer_sorteo_del_examen(
        examen_id: str,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> SorteoDelExamenResponse:
        if session_factory is None:
            raise HTTPException(status_code=500, detail="Persistencia no inicializada.")

        await _exigir_pertenencia(principal, examen_id)

        from sqlalchemy import func as _func, select as _select

        from app.infrastructure.persistence.models.exam_content import (
            CategoriaPreguntaModel,
            ComisionModel,
            ExamenContenidoModel,
            PreguntaBancoModel,
            PreguntaExamenModel,
            TramoSorteoExamenModel,
        )
        from app.infrastructure.persistence.models.proctoring import (
            ProctoringSessionModel,
        )

        async with session_factory() as session:
            fila = (
                await session.execute(
                    _select(
                        ExamenContenidoModel.modo_preguntas,
                        ExamenContenidoModel.comision_id,
                    ).where(ExamenContenidoModel.id == examen_id)
                )
            ).one_or_none()
            if fila is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "examen_no_encontrado", "examen_id": examen_id},
                )
            modo, comision_id = fila

            intentos = (
                await session.execute(
                    _select(_func.count(ProctoringSessionModel.id)).where(
                        ProctoringSessionModel.examen_contenido_id == examen_id
                    )
                )
            ).scalar_one()

            pool_total = (
                await session.execute(
                    _select(_func.count(PreguntaExamenModel.id)).where(
                        PreguntaExamenModel.examen_id == examen_id
                    )
                )
            ).scalar_one()

            if modo != MODO_SORTEO_POR_INTENTO:
                return SorteoDelExamenResponse(
                    modo_preguntas=modo,
                    pool_total=pool_total,
                    pool_editable=intentos == 0,
                    total_intentos=intentos,
                )

            tramos = (
                (
                    await session.execute(
                        _select(TramoSorteoExamenModel)
                        .where(TramoSorteoExamenModel.examen_id == examen_id)
                        .order_by(TramoSorteoExamenModel.orden)
                    )
                )
                .scalars()
                .all()
            )

            # La materia sale de la comisión del examen: es el banco contra el que
            # se compara. Sin comisión no hay banco que mirar y el aviso queda en 0.
            materia_id = None
            if comision_id is not None:
                materia_id = (
                    await session.execute(
                        _select(ComisionModel.materia_id).where(
                            ComisionModel.id == comision_id
                        )
                    )
                ).scalar_one_or_none()

            hijos: dict[str, list[str]] = {}
            nombres: dict[str, str] = {}
            if materia_id is not None:
                cats = await session.execute(
                    _select(
                        CategoriaPreguntaModel.id,
                        CategoriaPreguntaModel.categoria_padre_id,
                        CategoriaPreguntaModel.nombre,
                    ).where(CategoriaPreguntaModel.materia_id == materia_id)
                )
                for cat_id, padre_id, nombre in cats.all():
                    nombres[str(cat_id)] = nombre
                    if padre_id:
                        hijos.setdefault(str(padre_id), []).append(str(cat_id))

            def _descendencia(raiz: str) -> set[str]:
                acumulado: set[str] = set()
                pendientes = [raiz]
                while pendientes:
                    actual = pendientes.pop()
                    if actual in acumulado:
                        continue
                    acumulado.add(actual)
                    pendientes.extend(hijos.get(actual, []))
                return acumulado

            # Pool y banco se traen enteros y se cuentan en Python: son decenas o
            # cientos de filas, y así el conteo por tramo no dispara una consulta
            # por tramo (con solapamiento entre tramos anidados, además, el SQL
            # tendría que repetir la misma expansión de categorías).
            pool = (
                await session.execute(
                    _select(
                        PreguntaExamenModel.categoria_id,
                        PreguntaExamenModel.tipo,
                        PreguntaExamenModel.pregunta_banco_id,
                    ).where(PreguntaExamenModel.examen_id == examen_id)
                )
            ).all()
            banco = []
            if materia_id is not None:
                banco = (
                    await session.execute(
                        _select(
                            PreguntaBancoModel.id,
                            PreguntaBancoModel.categoria_id,
                            PreguntaBancoModel.tipo,
                        ).where(PreguntaBancoModel.materia_id == materia_id)
                    )
                ).all()
            ya_en_el_pool = {
                str(b) for _, _, b in pool if b is not None
            }

            items: list[TramoSorteoResponse] = []
            nuevas_totales: set[str] = set()
            for tramo in tramos:
                if tramo.categoria_id is None:
                    admitidas: set[str | None] = {None}
                elif tramo.incluir_subcategorias:
                    admitidas = set(_descendencia(str(tramo.categoria_id)))
                else:
                    admitidas = {str(tramo.categoria_id)}
                tipos = set(tramo.tipos) if tramo.tipos else None

                def _califica(cat, tipo) -> bool:
                    return (str(cat) if cat else None) in admitidas and (
                        tipos is None or tipo in tipos
                    )

                en_pool = sum(1 for cat, tipo, _ in pool if _califica(cat, tipo))
                en_banco = sum(1 for _, cat, tipo in banco if _califica(cat, tipo))
                nuevas_totales |= {
                    str(pid)
                    for pid, cat, tipo in banco
                    if _califica(cat, tipo) and str(pid) not in ya_en_el_pool
                }

                items.append(
                    TramoSorteoResponse(
                        categoria_id=(
                            str(tramo.categoria_id) if tramo.categoria_id else None
                        ),
                        categoria_nombre=(
                            nombres.get(str(tramo.categoria_id))
                            if tramo.categoria_id
                            else None
                        ),
                        incluir_subcategorias=tramo.incluir_subcategorias,
                        tipos=list(tramo.tipos) if tramo.tipos else None,
                        cantidad=tramo.cantidad,
                        en_el_pool=en_pool,
                        en_el_banco=en_banco,
                    )
                )

            return SorteoDelExamenResponse(
                modo_preguntas=modo,
                tramos=items,
                largo_del_examen=sum(t.cantidad for t in tramos),
                pool_total=pool_total,
                nuevas_en_el_banco=len(nuevas_totales),
                # Cambiar el pool con intentos ya rendidos haría que dos alumnos
                # sorteen de conjuntos distintos: dejaria de ser el mismo examen.
                pool_editable=intentos == 0,
                total_intentos=intentos,
            )

    @router.post(
        "/{examen_id}/sorteo/actualizar-pool",
        dependencies=[Depends(require_capability("crear_examenes"))],
        response_model=SorteoDelExamenResponse,
        summary="Incorporar al examen las preguntas nuevas del banco (c-78 E-07)",
    )
    async def actualizar_pool_del_examen(
        examen_id: str,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> SorteoDelExamenResponse:
        """Copia al pool las preguntas del banco que calificarían y no estaban.

        El pool está congelado a propósito: si no, tocar el banco podría dejar a un
        alumno sin examen. Actualizarlo es una decisión explícita del docente.

        409 si el examen ya tiene intentos: cambiar el pool ahí haría que dos
        alumnos sorteen de conjuntos distintos.
        """
        if session_factory is None:
            raise HTTPException(status_code=500, detail="Persistencia no inicializada.")

        await _exigir_pertenencia(principal, examen_id)

        import uuid as _uuid

        from sqlalchemy import func as _func, select as _select
        from sqlalchemy.orm import selectinload as _selectinload

        from app.infrastructure.persistence.models.exam_content import (
            BlankBancoModel,
            CategoriaPreguntaModel,
            ComisionModel,
            ExamenContenidoModel,
            OpcionClozeBlancoModel,
            OpcionRespuestaModel,
            PreguntaBancoModel,
            PreguntaClozeBlankModel,
            PreguntaExamenModel,
            TramoSorteoExamenModel,
        )
        from app.infrastructure.persistence.models.proctoring import (
            ProctoringSessionModel,
        )

        async with session_factory() as session:
            fila = (
                await session.execute(
                    _select(
                        ExamenContenidoModel.modo_preguntas,
                        ExamenContenidoModel.comision_id,
                        ExamenContenidoModel.titulo,
                    ).where(ExamenContenidoModel.id == examen_id)
                )
            ).one_or_none()
            if fila is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "examen_no_encontrado", "examen_id": examen_id},
                )
            modo, comision_id, titulo = fila
            if modo != MODO_SORTEO_POR_INTENTO:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "examen_sin_sorteo",
                        "mensaje": (
                            "Este examen tiene preguntas fijas: no sortea de un pool."
                        ),
                    },
                )

            intentos = (
                await session.execute(
                    _select(_func.count(ProctoringSessionModel.id)).where(
                        ProctoringSessionModel.examen_contenido_id == examen_id
                    )
                )
            ).scalar_one()
            if intentos:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "pool_bloqueado",
                        "mensaje": (
                            f"El examen ya tiene {intentos} intento(s). Cambiar el "
                            "conjunto de preguntas haria que dos alumnos rindan "
                            "exámenes distintos."
                        ),
                        "total_intentos": intentos,
                    },
                )

            materia_id = None
            if comision_id is not None:
                materia_id = (
                    await session.execute(
                        _select(ComisionModel.materia_id).where(
                            ComisionModel.id == comision_id
                        )
                    )
                ).scalar_one_or_none()
            if materia_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "sin_materia",
                        "mensaje": (
                            "El examen no tiene comisión asociada, así que no hay "
                            "banco contra el cual actualizarlo."
                        ),
                    },
                )

            hijos: dict[str, list[str]] = {}
            cats = await session.execute(
                _select(
                    CategoriaPreguntaModel.id,
                    CategoriaPreguntaModel.categoria_padre_id,
                ).where(CategoriaPreguntaModel.materia_id == materia_id)
            )
            for cat_id, padre_id in cats.all():
                if padre_id:
                    hijos.setdefault(str(padre_id), []).append(str(cat_id))

            def _descendencia(raiz: str) -> set[str]:
                acumulado: set[str] = set()
                pendientes = [raiz]
                while pendientes:
                    actual = pendientes.pop()
                    if actual in acumulado:
                        continue
                    acumulado.add(actual)
                    pendientes.extend(hijos.get(actual, []))
                return acumulado

            tramos = (
                (
                    await session.execute(
                        _select(TramoSorteoExamenModel)
                        .where(TramoSorteoExamenModel.examen_id == examen_id)
                        .order_by(TramoSorteoExamenModel.orden)
                    )
                )
                .scalars()
                .all()
            )

            ya_en_el_pool = {
                str(r[0])
                for r in (
                    await session.execute(
                        _select(PreguntaExamenModel.pregunta_banco_id).where(
                            PreguntaExamenModel.examen_id == examen_id,
                            PreguntaExamenModel.pregunta_banco_id.is_not(None),
                        )
                    )
                ).all()
            }
            proximo_orden = (
                await session.execute(
                    _select(_func.coalesce(_func.max(PreguntaExamenModel.orden), -1)).where(
                        PreguntaExamenModel.examen_id == examen_id
                    )
                )
            ).scalar_one() + 1

            banco = (
                (
                    await session.execute(
                        _select(PreguntaBancoModel)
                        .where(PreguntaBancoModel.materia_id == materia_id)
                        .options(
                            _selectinload(PreguntaBancoModel.opciones_banco),
                            _selectinload(
                                PreguntaBancoModel.blanks_banco
                            ).selectinload(BlankBancoModel.opciones_blank_banco),
                        )
                    )
                )
                .scalars()
                .all()
            )

            a_sumar: dict[str, PreguntaBancoModel] = {}
            for tramo in tramos:
                if tramo.categoria_id is None:
                    admitidas: set[str | None] = {None}
                elif tramo.incluir_subcategorias:
                    admitidas = set(_descendencia(str(tramo.categoria_id)))
                else:
                    admitidas = {str(tramo.categoria_id)}
                tipos = set(tramo.tipos) if tramo.tipos else None
                for pb in banco:
                    if str(pb.id) in ya_en_el_pool or str(pb.id) in a_sumar:
                        continue
                    cat = str(pb.categoria_id) if pb.categoria_id else None
                    if cat in admitidas and (tipos is None or pb.tipo in tipos):
                        a_sumar[str(pb.id)] = pb

            for i, pb in enumerate(a_sumar.values()):
                pregunta_id = str(_uuid.uuid4())
                session.add(
                    PreguntaExamenModel(
                        id=pregunta_id,
                        examen_id=examen_id,
                        enunciado=pb.enunciado,
                        tipo=pb.tipo,
                        orden=proximo_orden + i,
                        # Igual que al armar: en modo sorteo nada queda marcado.
                        seleccionada=False,
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
                    for ob in blank.opciones_blank_banco:
                        session.add(
                            OpcionClozeBlancoModel(
                                id=str(_uuid.uuid4()),
                                blank_id=blank_id,
                                texto=ob.texto,
                                es_correcta=ob.es_correcta,
                                peso=ob.peso,
                            )
                        )

            sumadas = len(a_sumar)
            await session.commit()

        if sumadas:
            await registrar_seguro(
                session_factory,
                actor=principal.email,
                accion=AccionAuditoria.EXAMEN_POOL_ACTUALIZADO,
                modulo=ModuloAuditoria.EXAMENES,
                entidad=EntidadAuditoria.EXAMEN,
                entidad_id=str(examen_id),
                ip=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                proposito=(
                    f"Incorporó {sumadas} pregunta(s) nueva(s) del banco al examen "
                    f"«{titulo}»: entran al sorteo de los proximos intentos"
                ),
            )

        return await leer_sorteo_del_examen(examen_id, principal)

    # -----------------------------------------------------------------------
    # Habilitar un examen en borrador (c-78 E-07).
    #
    # Es de IDA, igual que publicar notas: volver a esconder un examen que los
    # alumnos ya pudieron ver no deshace nada. Para sacarlo de circulación está la
    # baja lógica, que es explícita y conserva la evidencia.
    # -----------------------------------------------------------------------

    @router.post(
        "/{examen_id}/habilitar",
        dependencies=[Depends(require_capability("crear_examenes"))],
        status_code=status.HTTP_204_NO_CONTENT,
        response_model=None,
        summary="Habilitar un examen en borrador para que los alumnos lo rindan",
    )
    async def habilitar_examen(
        examen_id: str,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> None:
        """Saca el examen del borrador. 404 si no existe o ya estaba habilitado."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        await _exigir_pertenencia(principal, examen_id)

        from sqlalchemy import select as _select

        from app.infrastructure.persistence.models.exam_content import (
            ExamenContenidoModel,
        )

        async with session_factory() as session:
            examen = (
                await session.execute(
                    _select(ExamenContenidoModel).where(
                        ExamenContenidoModel.id == examen_id,
                        ExamenContenidoModel.eliminado_en.is_(None),
                        ExamenContenidoModel.borrador.is_(True),
                    )
                )
            ).scalar_one_or_none()
            if examen is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "examen_no_encontrado",
                        "mensaje": "El examen no existe o ya está habilitado.",
                        "examen_id": examen_id,
                    },
                )
            examen.borrador = False
            titulo = examen.titulo
            await session.commit()

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.EXAMEN_HABILITAR,
            modulo=ModuloAuditoria.EXAMENES,
            entidad=EntidadAuditoria.EXAMEN,
            entidad_id=str(examen_id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"Habilitó el examen «{titulo}»: deja el borrador y los alumnos "
                "ya lo pueden rendir"
            ),
        )

    # -----------------------------------------------------------------------
    # Comisiones que rinden un examen (c-78 E-06, task 14.4).
    #
    # Decisión del dueño: la comisión no se elige al duplicar, se administra desde
    # el examen. Bajo el modelo replicado (D12) el examen y sus réplicas forman un
    # lote (`lote_replica_id`); agregar una comisión crea otra réplica con las
    # MISMAS preguntas dentro del lote.
    #
    # Quitar una comisión SOLO se permite si nadie rindió en ella (regla del
    # dueño). Cuando se permite, la réplica sale del lote y queda dada de baja: no
    # se borra, así que si fue un error se recupera desde "Dados de baja".
    # -----------------------------------------------------------------------

    async def _lote_del_examen(session, examen_id: str):
        """(examen, ids del lote). Un examen sin lote es un lote de uno."""
        from sqlalchemy import select as _select

        from app.infrastructure.persistence.models.exam_content import (
            ExamenContenidoModel,
        )

        examen = (
            await session.execute(
                _select(ExamenContenidoModel).where(
                    ExamenContenidoModel.id == examen_id
                )
            )
        ).scalar_one_or_none()
        if examen is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "examen_no_encontrado",
                    "mensaje": "El examen no existe.",
                    "examen_id": examen_id,
                },
            )
        if examen.lote_replica_id is None:
            return examen, [examen.id]
        hermanas = await session.execute(
            _select(ExamenContenidoModel.id).where(
                ExamenContenidoModel.lote_replica_id == examen.lote_replica_id
            )
        )
        return examen, [r[0] for r in hermanas.all()]

    @router.get(
        "/{examen_id}/comisiones",
        dependencies=[Depends(require_capability("crear_examenes"))],
        response_model=ComisionesDelExamenResponse,
        summary="Comisiones que rinden este examen (el lote de réplicas)",
    )
    async def listar_comisiones_del_examen(
        examen_id: str,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> ComisionesDelExamenResponse:
        """Un examen sin réplicas devuelve una sola comisión: la suya."""
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        await _exigir_pertenencia(principal, examen_id)

        from sqlalchemy import func as _func, select as _select

        from app.infrastructure.persistence.models.exam_content import (
            ComisionModel,
            ExamenContenidoModel,
        )
        from app.infrastructure.persistence.models.proctoring import (
            ProctoringSessionModel,
        )

        async with session_factory() as session:
            _, ids_lote = await _lote_del_examen(session, examen_id)

            # Los intentos se cuentan en la MISMA consulta: la UI los necesita para
            # explicar por qué una comisión no se puede quitar, y un lote de tres
            # no justifica tres viajes más a la base.
            filas = await session.execute(
                _select(
                    ExamenContenidoModel.id,
                    ExamenContenidoModel.titulo,
                    ExamenContenidoModel.eliminado_en,
                    ComisionModel.id,
                    ComisionModel.codigo,
                    ComisionModel.nombre,
                    _func.count(ProctoringSessionModel.id),
                )
                .join(ComisionModel, ComisionModel.id == ExamenContenidoModel.comision_id)
                .outerjoin(
                    ProctoringSessionModel,
                    ProctoringSessionModel.examen_contenido_id == ExamenContenidoModel.id,
                )
                .where(ExamenContenidoModel.id.in_(ids_lote))
                .group_by(
                    ExamenContenidoModel.id,
                    ExamenContenidoModel.titulo,
                    ExamenContenidoModel.eliminado_en,
                    ComisionModel.id,
                    ComisionModel.codigo,
                    ComisionModel.nombre,
                )
                .order_by(ComisionModel.codigo)
            )

            return ComisionesDelExamenResponse(
                items=[
                    ComisionDelExamenItem(
                        examen_id=str(eid),
                        comision_id=str(cid),
                        comision_codigo=codigo,
                        comision_nombre=nombre,
                        titulo=titulo,
                        dado_de_baja=eliminado_en is not None,
                        total_intentos=intentos,
                        es_el_actual=str(eid) == examen_id,
                    )
                    for eid, titulo, eliminado_en, cid, codigo, nombre, intentos in filas.all()
                ]
            )

    @router.post(
        "/{examen_id}/comisiones",
        dependencies=[Depends(require_capability("crear_examenes"))],
        response_model=ExamenReplicaItem,
        status_code=status.HTTP_201_CREATED,
        summary="Sumar una comisión al examen (crea una réplica con las mismas preguntas)",
    )
    async def agregar_comision_al_examen(
        examen_id: str,
        body: AgregarComisionExamenRequest,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> ExamenReplicaItem:
        """Crea la réplica del examen para esa comisión, dentro del mismo lote.

        La comisión tiene que ser de la misma materia: el contenido salió de ESE
        banco. 409 si esa comisión ya rinde el examen.
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        await _exigir_pertenencia(principal, examen_id)
        await _exigir_pertenencia_comision(principal, body.comision_id)

        import uuid as _uuid

        from sqlalchemy import select as _select
        from sqlalchemy.orm import selectinload as _selectinload

        from app.infrastructure.persistence.models.exam_content import (
            ComisionModel,
            ExamenContenidoModel,
            PreguntaClozeBlankModel,
            PreguntaExamenModel,
        )

        async with session_factory() as session:
            original = (
                await session.execute(
                    _select(ExamenContenidoModel)
                    .where(
                        ExamenContenidoModel.id == examen_id,
                        ExamenContenidoModel.eliminado_en.is_(None),
                    )
                    .options(
                        _selectinload(ExamenContenidoModel.preguntas).selectinload(
                            PreguntaExamenModel.opciones
                        ),
                        _selectinload(ExamenContenidoModel.preguntas)
                        .selectinload(PreguntaExamenModel.blanks_cloze)
                        .selectinload(PreguntaClozeBlankModel.opciones_cloze),
                    )
                )
            ).scalar_one_or_none()
            if original is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "examen_no_encontrado",
                        "mensaje": "El examen no existe o está dado de baja.",
                        "examen_id": examen_id,
                    },
                )

            comisiones = await session.execute(
                _select(
                    ComisionModel.id, ComisionModel.codigo, ComisionModel.materia_id
                ).where(
                    ComisionModel.id.in_(
                        [c for c in (body.comision_id, original.comision_id) if c]
                    )
                )
            )
            datos_comision = {r[0]: (r[1], r[2]) for r in comisiones.all()}

            if body.comision_id not in datos_comision:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "comision_inexistente",
                        "mensaje": "La comisión no existe.",
                        "comision_id": body.comision_id,
                    },
                )
            if original.comision_id is not None and (
                datos_comision[body.comision_id][1]
                != datos_comision.get(original.comision_id, (None, None))[1]
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "comision_de_otra_materia",
                        "mensaje": (
                            "La comisión tiene que ser de la misma materia: las "
                            "preguntas del examen salieron de ese banco."
                        ),
                        "comision_id": body.comision_id,
                    },
                )

            # ¿Esa comisión ya rinde el examen? Se mira el lote entero, no solo el
            # examen desde el que se pidió. Las réplicas dadas de baja no cuentan:
            # una comisión quitada se puede volver a agregar.
            lote_actual = original.lote_replica_id
            ya_incluidas = await session.execute(
                _select(ExamenContenidoModel.comision_id).where(
                    ExamenContenidoModel.eliminado_en.is_(None),
                    ExamenContenidoModel.lote_replica_id == lote_actual
                    if lote_actual is not None
                    else ExamenContenidoModel.id == original.id,
                )
            )
            if body.comision_id in {str(r[0]) for r in ya_incluidas.all() if r[0]}:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "comision_ya_incluida",
                        "mensaje": "Esa comisión ya rinde este examen.",
                        "comision_id": body.comision_id,
                    },
                )

            # El examen que estaba solo entra al lote junto con la réplica nueva:
            # si no, seguiría diciendo que se toma en una comisión sola.
            if lote_actual is None:
                lote_actual = str(_uuid.uuid4())
                original.lote_replica_id = lote_actual

            codigo_nuevo = datos_comision[body.comision_id][0]
            codigo_original = datos_comision.get(original.comision_id, (None, None))[0]
            titulo_replica = (
                f"{_titulo_base(original.titulo, codigo_original)} ({codigo_nuevo})"
            )
            titulo_original = original.titulo

            replica_id, total_preguntas = await _clonar_examen(
                session,
                original,
                titulo=titulo_replica,
                comision_id=body.comision_id,
                lote_replica_id=lote_actual,
            )
            await session.commit()

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.EXAMEN_COMISION_AGREGADA,
            modulo=ModuloAuditoria.EXAMENES,
            entidad=EntidadAuditoria.EXAMEN,
            entidad_id=replica_id,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"Sumó la comisión {codigo_nuevo} al examen «{titulo_original}»: "
                f"creó «{titulo_replica}» con las mismas {total_preguntas} preguntas"
            ),
        )

        return ExamenReplicaItem(
            examen_id=replica_id,
            comision_id=body.comision_id,
            titulo=titulo_replica,
        )

    @router.delete(
        "/{examen_id}/comisiones/{comision_id}",
        dependencies=[Depends(require_capability("crear_examenes"))],
        status_code=status.HTTP_204_NO_CONTENT,
        response_model=None,
        summary="Quitar una comisión del examen (solo si no rindió nadie)",
    )
    async def quitar_comision_del_examen(
        examen_id: str,
        comision_id: str,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> None:
        """Saca la réplica de esa comisión del lote y la da de baja.

        409 si esa comisión ya tiene aunque sea un intento: sacarla dejaría
        evidencia viva colgando de un examen fuera del catálogo. 409 también si es
        la única comisión del examen.
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        await _exigir_pertenencia(principal, examen_id)

        from sqlalchemy import func as _func, select as _select

        from app.infrastructure.persistence.models.exam_content import (
            ComisionModel,
            ExamenContenidoModel,
        )
        from app.infrastructure.persistence.models.proctoring import (
            ProctoringSessionModel,
        )

        async with session_factory() as session:
            _, ids_lote = await _lote_del_examen(session, examen_id)

            activas = await session.execute(
                _select(ExamenContenidoModel).where(
                    ExamenContenidoModel.id.in_(ids_lote),
                    ExamenContenidoModel.eliminado_en.is_(None),
                )
            )
            replicas = list(activas.scalars().all())
            objetivo = next(
                (r for r in replicas if str(r.comision_id) == comision_id), None
            )
            if objetivo is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "comision_no_incluida",
                        "mensaje": "Esa comisión no rinde este examen.",
                        "comision_id": comision_id,
                    },
                )
            if len(replicas) == 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "unica_comision",
                        "mensaje": (
                            "Es la única comisión del examen. Para sacarlo de "
                            "circulación, dá de baja el examen."
                        ),
                        "comision_id": comision_id,
                    },
                )

            intentos = await session.execute(
                _select(_func.count(ProctoringSessionModel.id)).where(
                    ProctoringSessionModel.examen_contenido_id == objetivo.id
                )
            )
            total_intentos = intentos.scalar_one()
            if total_intentos:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "comision_con_intentos",
                        "mensaje": (
                            f"Esa comisión ya tiene {total_intentos} intento(s) de este "
                            "examen. No se puede quitar."
                        ),
                        "comision_id": comision_id,
                        "total_intentos": total_intentos,
                    },
                )

            codigo = (
                await session.execute(
                    _select(ComisionModel.codigo).where(ComisionModel.id == comision_id)
                )
            ).scalar_one_or_none() or comision_id

            # Sale del lote y queda de baja. No se borra: si fue un error, se
            # recupera desde el filtro "Dados de baja".
            objetivo.lote_replica_id = None
            objetivo.eliminado_en = datetime.now(UTC)
            titulo_quitado = objetivo.titulo
            await session.commit()

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.EXAMEN_COMISION_QUITADA,
            modulo=ModuloAuditoria.EXAMENES,
            entidad=EntidadAuditoria.EXAMEN,
            entidad_id=examen_id,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"Quitó la comisión {codigo} del examen: dio de baja «{titulo_quitado}» "
                "(no tenía ningún intento rendido)"
            ),
        )

    @router.post(
        "/{examen_id}/publicar-notas",
        dependencies=[Depends(require_capability("gestionar_notas"))],
        response_model=ExamenConfigResponse,
        summary="Publicar las notas del examen (c-78 D9: camino de ida)",
    )
    async def publicar_notas_examen(
        examen_id: str,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> ExamenConfigResponse:
        """Hace visible la nota a los alumnos, en el momento en que se decide.

        c-78 D9 (E-01): el enum `mostrar_nota` solo no alcanza — el docente no
        razona en enums, razona en "reviso y publico". Esta es esa acción; el
        enum es el estado que mueve.

        - `nunca` → `al_cerrar`: la nota pasa a verse cuando cierre el examen.
          Si el examen ya cerró, se ve de inmediato.
        - Es CAMINO DE IDA: un examen ya publicado responde 409. No se puede
          volver a ocultar una nota que el alumno pudo haber visto.
        - Queda auditado quién publicó y cuándo (también persistido en el examen,
          para que el detalle lo muestre sin ir al audit log).

        Requiere `gestionar_notas`: publicar la nota es cerrar la nota, y ese es
        el trabajo de quien la devuelve — no exige poder crear exámenes.
        """
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        await _exigir_pertenencia(principal, examen_id)

        from app.infrastructure.persistence.repositories.exam_content import (
            ExamenContenidoSqlRepository,
        )

        ahora = datetime.now(UTC)
        async with session_factory() as session:
            repo = ExamenContenidoSqlRepository(session)
            actual = await repo.obtener(examen_id)
            if actual is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "examen_no_encontrado", "examen_id": examen_id},
                )
            if actual.mostrar_nota != MOSTRAR_NOTA_NUNCA:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "notas_ya_publicadas",
                        "mensaje": "Las notas de este examen ya están publicadas.",
                        "publicadas_en": (
                            actual.notas_publicadas_en.isoformat()
                            if actual.notas_publicadas_en
                            else None
                        ),
                        "publicadas_por": actual.notas_publicadas_por,
                    },
                )

            examen = await repo.actualizar_config(
                examen_id,
                {
                    "mostrar_nota": MOSTRAR_NOTA_AL_CERRAR,
                    "notas_publicadas_en": ahora,
                    "notas_publicadas_por": principal.email,
                },
            )
            ya_rendido = await _seleccion_bloqueada(session, examen_id)
            await session.commit()

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.EXAMEN_PUBLICAR_NOTAS,
            modulo=ModuloAuditoria.EXAMENES,
            entidad=EntidadAuditoria.EXAMEN,
            entidad_id=str(examen_id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"Publicó las notas del examen «{await _titulo_de_examen(examen_id)}» "
                "(los alumnos pasan a ver su nota)"
            ),
        )

        return _config_to_response(examen, bloqueada=ya_rendido)

    @router.post(
        "/{examen_id}/moodle-target",
        response_model=MoodleTargetResponse,
        dependencies=[Depends(require_capability("crear_examenes"))],
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
            entidad=EntidadAuditoria.EXAMEN,
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
    async def leer_moodle_target(
        examen_id: str,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> MoodleTargetResponse:
        """Devuelve moodle_courseid/cmid del examen (null = fallback global). 404 si no existe.

        c-79: le faltaba `_exigir_pertenencia` (a diferencia de su POST y de
        GET .../config, que sí la tienen) — un tutor podía leer el destino
        Moodle de un examen de una comisión ajena conociendo el id.
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
            notas_publicadas_en=examen.notas_publicadas_en,
            notas_publicadas_por=examen.notas_publicadas_por,
            mostrar_eventos_alumno=examen.mostrar_eventos_alumno,
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
    async def leer_config_examen(
        examen_id: str,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> ExamenConfigResponse:
        """Devuelve los 7 campos de configuración del examen. 404 si no existe."""
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
        dependencies=[Depends(require_capability("crear_examenes"))],
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

            # c-78 D9: publicar es camino de IDA. El orden permitido es
            # nunca → al_cerrar → inmediata; volver atrás se rechaza. Esconder una
            # nota que el alumno ya vio no tiene efecto útil (ya la vio) y sí
            # genera reclamos. Se valida acá y no en el schema porque la regla
            # necesita el valor ANTERIOR.
            if "mostrar_nota" in cambios and not transicion_visibilidad_permitida(
                actual.mostrar_nota, cambios["mostrar_nota"]
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "visibilidad_no_retrocede",
                        "mensaje": (
                            "Las notas ya se publicaron: no se pueden volver a "
                            "ocultar. El orden permitido es 'nunca' → 'al cerrar' "
                            "→ 'inmediata', siempre hacia adelante."
                        ),
                        "actual": actual.mostrar_nota,
                        "solicitado": cambios["mostrar_nota"],
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

            # c-78 D9: si esta edición saca la nota de 'nunca', queda registrado
            # quién la publicó y cuándo (el detalle lo muestra; también se audita).
            if (
                actual.mostrar_nota == MOSTRAR_NOTA_NUNCA
                and cambios.get("mostrar_nota", MOSTRAR_NOTA_NUNCA) != MOSTRAR_NOTA_NUNCA
            ):
                cambios["notas_publicadas_en"] = datetime.now(UTC)
                cambios["notas_publicadas_por"] = principal.email

            examen = await repo.actualizar_config(examen_id, cambios)
            await session.commit()

        # La config define mecánica/nota del examen → cambios auditados (qué campos).
        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.EXAMEN_CONFIG_ACTUALIZACION,
            modulo=ModuloAuditoria.EXAMENES,
            entidad=EntidadAuditoria.EXAMEN,
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
        dependencies=[Depends(require_capability("gestionar_banco"))],
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
        dependencies=[Depends(require_capability("gestionar_banco"))],
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
        dependencies=[Depends(require_capability("gestionar_banco"))],
        summary="Editar categoría del banco: renombrar y/o re-anidar (C-74 §4)",
    )
    async def editar_categoria_banco(
        categoria_id: str,
        body: dict,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ):
        # Dos acciones combinables: renombrar (nombre) y/o re-anidar
        # (categoria_padre_id). La clave `categoria_padre_id` presente en el body
        # dispara el re-anidado (su valor puede ser null → mover a raíz).
        nombre = body.get("nombre")
        if nombre is not None:
            nombre = nombre.strip()
        reanidar = "categoria_padre_id" in body
        nuevo_padre_id = body.get("categoria_padre_id") or None
        if not nombre and not reanidar:
            raise HTTPException(status_code=422, detail="nombre o categoria_padre_id requerido.")
        if session_factory is None:
            raise HTTPException(status_code=500, detail="Persistencia no inicializada.")
        from app.infrastructure.persistence.models.exam_content import CategoriaPreguntaModel
        from app.infrastructure.persistence.repositories.categoria_pregunta import (
            CategoriaNoEncontradaError,
            CategoriaPreguntaSqlRepository,
            CicloCategoriaError,
            MateriaDistintaError,
        )
        from sqlalchemy import update as _update
        async with session_factory() as session:
            repo = CategoriaPreguntaSqlRepository(session)
            cat = await repo.obtener(categoria_id)
            if cat is None:
                raise HTTPException(status_code=404, detail="categoria_no_encontrada")
            await _exigir_pertenencia_materia(principal, cat.materia_id)
            if nombre:
                await session.execute(
                    _update(CategoriaPreguntaModel)
                    .where(CategoriaPreguntaModel.id == categoria_id)
                    .values(nombre=nombre)
                )
            if reanidar:
                try:
                    await repo.mover(categoria_id, nuevo_padre_id)
                except CategoriaNoEncontradaError as exc:
                    raise HTTPException(
                        status_code=404, detail="categoria_destino_no_encontrada"
                    ) from exc
                except CicloCategoriaError as exc:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "error": "ciclo_categoria",
                            "mensaje": "No podés mover una categoría dentro de sí misma o de una subcategoría suya.",
                        },
                    ) from exc
                except MateriaDistintaError as exc:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "error": "materia_distinta",
                            "mensaje": "La categoría destino es de otra materia.",
                        },
                    ) from exc
            await session.commit()
            cat_act = await repo.obtener(categoria_id)
        return {
            "id": cat_act.id,
            "nombre": cat_act.nombre,
            "materia_id": cat_act.materia_id,
            "categoria_padre_id": cat_act.categoria_padre_id,
        }

    @router.delete(
        "/categorias/{categoria_id}",
        dependencies=[Depends(require_capability("gestionar_banco"))],
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
        dependencies=[Depends(require_capability("gestionar_banco"))],
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

    @router.get(
        "/preguntas/{pregunta_id}/preview",
        dependencies=[Depends(require_capability("gestionar_banco"))],
        response_model=PreguntaPreviewResponse,
        summary="Ver una pregunta del banco como la ve el alumno (c-78 E-08)",
    )
    async def preview_pregunta_banco(
        pregunta_id: str,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> PreguntaPreviewResponse:
        """La pregunta con sus opciones y blanks, para revisarla antes de tomarla.

        Sin esto, la única forma de ver si una pregunta quedó bien importada era
        tomar el examen. Las opciones van en su orden de banco; en la rendición
        real se barajan por alumno, pero eso no cambia el contenido.
        """
        if session_factory is None:
            raise HTTPException(status_code=500, detail="Persistencia no inicializada.")

        from sqlalchemy import select as _select
        from sqlalchemy.orm import selectinload as _selectinload

        from app.infrastructure.persistence.models.exam_content import (
            BlankBancoModel,
            PreguntaBancoModel,
        )

        async with session_factory() as session:
            pregunta = (
                await session.execute(
                    _select(PreguntaBancoModel)
                    .where(PreguntaBancoModel.id == pregunta_id)
                    .options(
                        _selectinload(PreguntaBancoModel.opciones_banco),
                        _selectinload(PreguntaBancoModel.blanks_banco).selectinload(
                            BlankBancoModel.opciones_blank_banco
                        ),
                    )
                )
            ).scalar_one_or_none()
            if pregunta is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "pregunta_no_encontrada",
                        "pregunta_id": pregunta_id,
                    },
                )
            # La pertenencia se valida sobre la MATERIA de la pregunta: el banco es
            # materia-wide y el gate de capacidad solo dice "puede ver bancos",
            # no "puede ver ESTE banco".
            await _exigir_pertenencia_materia(principal, str(pregunta.materia_id))

            return PreguntaPreviewResponse(
                id=str(pregunta.id),
                enunciado=pregunta.enunciado,
                tipo=pregunta.tipo,
                opciones=[
                    OpcionPreviewResponse(
                        texto=o.texto, orden=o.orden, es_correcta=o.es_correcta
                    )
                    for o in sorted(pregunta.opciones_banco, key=lambda x: x.orden)
                ],
                blanks=[
                    BlankPreviewResponse(
                        orden=b.orden,
                        tipo=b.tipo,
                        texto_antes=b.texto_antes,
                        texto_despues=b.texto_despues,
                        opciones=[
                            OpcionPreviewResponse(
                                texto=ob.texto, orden=i, es_correcta=ob.es_correcta
                            )
                            for i, ob in enumerate(b.opciones_blank_banco)
                        ],
                    )
                    for b in sorted(pregunta.blanks_banco, key=lambda x: x.orden)
                ],
            )

    @router.patch(
        "/preguntas/{pregunta_id}/categoria",
        dependencies=[Depends(require_capability("gestionar_banco"))],
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
    async def listar_preguntas_pool(
        examen_id: str,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> PreguntasPoolResponse:
        """Devuelve TODO el pool del examen para la pantalla de selección del docente.

        D3: sin es_correcta ni opciones — el docente identifica por enunciado.
        404 si el examen no existe.
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
        dependencies=[Depends(require_capability("crear_examenes"))],
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
            entidad=EntidadAuditoria.EXAMEN,
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
        dependencies=[Depends(require_capability("crear_examenes"))],
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
        estado_entrega: str | None = None,
        archivado: str = "false",
        fecha_desde: datetime | None = None,
        fecha_hasta: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> ResultadosExamenPaginadosResponse:
        """Lista paginada de los alumnos que rindieron el examen.

        Deriva de las sesiones vinculadas + la nota persistida + el estado de
        write-back. Filtrado/orden SIEMPRE serverside.
        - q:              búsqueda por alumno (idnumber/email).
        - estado:         filtro por estado de SYNC a Moodle
                          (pendiente/enviado/fallido/sin_token).
        - estado_entrega: filtro por estado de la ENTREGA (C-76 tarea 14),
                          DERIVADO — no_finalizada/en_revision/revisada/finalizada.
                          Ortogonal a `estado` (sync a Moodle).
        - archivado:      TRI-ESTADO (c-78 D6) — 'false' (default, solo filas NO
                          archivadas; soft-hide administrativo, no disciplinario) |
                          'true' (solo archivadas) | 'todas' (sin filtro). 422 con
                          error 'archivado_invalido' fuera de ese conjunto.
        - fecha_desde/fecha_hasta: rango sobre `finalizada_en`.
        estado_moodle = 'sin_token' cuando Moodle no está configurado.
        D3: es_correcta NUNCA expuesta.
        """
        await _exigir_pertenencia(principal, examen_id)
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )
        if estado_entrega is not None and estado_entrega not in ESTADOS_ENTREGA_VALIDOS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "estado_entrega_invalido",
                    "mensaje": f"estado_entrega debe ser uno de {sorted(ESTADOS_ENTREGA_VALIDOS)}",
                },
            )
        if archivado not in ARCHIVADO_VALIDOS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "archivado_invalido",
                    "mensaje": f"archivado debe ser uno de {sorted(ARCHIVADO_VALIDOS)}",
                },
            )

        moodle_configurado = writeback_svc is not None
        async with session_factory() as session:
            items, total = await listar_resultados_examen(
                db=session,
                examen_id=examen_id,
                q=q,
                estado=estado,
                estado_entrega_filtro=estado_entrega,
                # 'todas' → None = sin filtro (el servicio ya lo soporta:
                # `if archivado is not None`).
                archivado=archivado_filtro(archivado),
                fecha_desde=fecha_desde,
                fecha_hasta=fecha_hasta,
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
                    estado_entrega=r.estado_entrega,
                    archivado=r.archivado,
                    marcada_manual_por=r.marcada_manual_por,
                    marcada_manual_en=r.marcada_manual_en,
                )
                for r in items
            ],
            total=total,
            page=max(1, page),
            page_size=max(1, page_size),
        )

    # -----------------------------------------------------------------------
    # Export de notas del examen (c-78 §13.5, E-10) + marcado manual (§13.6, D14).
    # -----------------------------------------------------------------------

    async def _resultados_para_export(principal, examen_id: str) -> tuple[list, object]:
        """Todos los resultados del examen (sin paginar) + su resumen, tras pertenencia."""
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
            # `archivado=None` (todas) a propósito: quien exporta para cargar
            # notas a mano necesita el listado COMPLETO, no el recorte de la
            # pantalla. page_size alto para no paginar el archivo.
            items, _total = await listar_resultados_examen(
                db=session,
                examen_id=examen_id,
                archivado=None,
                page=1,
                page_size=10000,
                moodle_configurado=writeback_svc is not None,
                writeback_svc=writeback_svc,
            )
            resumen = await ExamenContenidoSqlRepository(session).obtener_resumen(
                examen_id
            )
        return items, resumen

    def _subtitulo_examen(resumen) -> str:
        if resumen is None:
            return "Examen no encontrado"
        partes = [resumen.titulo]
        if resumen.materia_nombre:
            partes.append(f"{resumen.materia_codigo or ''} {resumen.materia_nombre}".strip())
        if resumen.comision_nombre:
            partes.append(f"{resumen.comision_codigo or ''} {resumen.comision_nombre}".strip())
        return " | ".join(p for p in partes if p)

    @router.get(
        "/{examen_id}/notas/export.xlsx",
        dependencies=[Depends(require_capability("gestionar_notas"))],
        summary="Exportar las notas del examen a Excel",
    )
    async def exportar_notas_xlsx(
        examen_id: str,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> Response:
        items, resumen = await _resultados_para_export(principal, examen_id)
        contenido = tabla_a_xlsx(
            titulo="Notas del examen — Active Exam",
            subtitulo=_subtitulo_examen(resumen),
            columnas=COLUMNAS_NOTAS,
            filas=filas_notas(items),
            nombre_hoja="Notas",
        )
        return Response(
            content=contenido,
            media_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            headers={
                "Content-Disposition": f'attachment; filename="notas-{_slug(resumen)}.xlsx"'
            },
        )

    @router.get(
        "/{examen_id}/notas/export.pdf",
        dependencies=[Depends(require_capability("gestionar_notas"))],
        summary="Exportar las notas del examen a PDF",
    )
    async def exportar_notas_pdf(
        examen_id: str,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> Response:
        items, resumen = await _resultados_para_export(principal, examen_id)
        contenido = tabla_a_pdf(
            titulo="Notas del examen - Active Exam",
            subtitulo=_subtitulo_examen(resumen),
            columnas=COLUMNAS_NOTAS,
            filas=filas_notas(items),
            # Seis columnas con emails y etiquetas largas: en vertical se cortan.
            apaisado=True,
        )
        return Response(
            content=contenido,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="notas-{_slug(resumen)}.pdf"'
            },
        )

    @router.patch(
        "/{examen_id}/resultados/{session_id}/marcar-cargada",
        dependencies=[Depends(require_capability("gestionar_notas"))],
        response_model=MarcarNotaCargadaResponse,
        summary="Marcar a mano que la nota ya se cargó en el campus (c-78 D14)",
    )
    async def marcar_nota_cargada(
        examen_id: str,
        session_id: str,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> MarcarNotaCargadaResponse:
        """Marca la nota como cargada A MANO en el campus (c-78 §13.6, D14).

        Sin API del campus, la nota se carga a mano y quedaba 'pendiente' para
        siempre — un estado que dejaba de significar nada. Esta acción la mueve.

        Dos reglas que la hacen honesta:
        - Queda registrado QUIÉN la marcó y CUÁNDO (`marcada_manual_por/_en`), y
          el estado resultante es `manual`, distinguible de `enviado`.
        - NO puede pisar una confirmación real: si el estado ya es `enviado` (el
          campus confirmó), responde 409. Una afirmación humana y una
          confirmación del sistema no valen lo mismo.
        """
        await _exigir_pertenencia(principal, examen_id)
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        from sqlalchemy import select as _select

        from app.application.moodle.writeback_service import WritebackEstado
        from app.infrastructure.persistence.models.moodle_writeback import (
            MoodleWritebackEstadoModel,
        )
        from app.infrastructure.persistence.models.proctoring import (
            ProctoringSessionModel,
        )

        ahora = datetime.now(UTC)
        async with session_factory() as session:
            # La sesión tiene que pertenecer a ESTE examen (no alcanza el id suelto).
            sesion = (
                await session.execute(
                    _select(ProctoringSessionModel).where(
                        ProctoringSessionModel.id == session_id,
                        ProctoringSessionModel.examen_contenido_id == examen_id,
                    )
                )
            ).scalar_one_or_none()
            if sesion is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "resultado_no_encontrado", "session_id": session_id},
                )

            # Una nota RETENIDA por integridad no se puede dar por entregada a
            # mano. El sincronizado automatico ya se niega a mandarla; sin esta
            # guarda se podia marcar a mano exactamente lo que el sistema retiene,
            # y encima quedaba registrado que una persona afirmo haberla cargado
            # en el campus. Es saltear la decision humana (regla dura #5) por la
            # puerta de atras.
            #
            # Se reusa el motivo que ya calcula `_motivos_retencion` en vez de
            # recalcular un criterio propio, que es como se desincronizan las
            # reglas. `sin_destino` y `sin_credencial_docente` NO bloquean: son
            # justamente los casos en que cargar a mano es lo correcto.
            from app.application.moodle.marcado_manual import puede_marcarse_cargada
            from app.application.moodle.resultados_query import _motivos_retencion

            retenido_por = (await _motivos_retencion(session, [session_id])).get(
                session_id
            )
            if not puede_marcarse_cargada(retenido_por):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "nota_retenida",
                        "mensaje": (
                            "La nota está retenida"
                            + (
                                " porque la sesión superó el umbral y todavía "
                                "nadie la revisó."
                                if retenido_por == "en_riesgo"
                                else " porque la sesión fue anulada por fraude."
                            )
                            + " No se puede marcar como cargada hasta que haya "
                            "una decisión humana."
                        ),
                        "retenido_por": retenido_por,
                    },
                )

            fila = (
                await session.execute(
                    _select(MoodleWritebackEstadoModel).where(
                        MoodleWritebackEstadoModel.session_id == session_id
                    )
                )
            ).scalar_one_or_none()
            if fila is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "nota_no_calculada",
                        "mensaje": (
                            "Todavía no hay nota para esta sesión: no se puede "
                            "marcar como cargada."
                        ),
                    },
                )

            if fila.estado == WritebackEstado.ENVIADO:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "nota_confirmada_por_el_campus",
                        "mensaje": (
                            "El campus ya confirmó el envío de esta nota. Un "
                            "marcado a mano no puede reemplazar esa confirmación."
                        ),
                    },
                )

            fila.estado = ESTADO_MANUAL
            fila.marcada_manual_por = principal.email
            fila.marcada_manual_en = ahora
            await session.commit()

        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.MOODLE_NOTA_MANUAL,
            modulo=ModuloAuditoria.MOODLE,
            entidad=EntidadAuditoria.SESION,
            entidad_id=str(session_id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                "Marcó a mano que la nota ya fue cargada en el campus "
                f"(examen {examen_id})"
            ),
        )

        return MarcarNotaCargadaResponse(
            session_id=session_id,
            estado_moodle=ESTADO_MANUAL,
            marcada_manual_por=principal.email,
            marcada_manual_en=ahora,
        )

    # -----------------------------------------------------------------------
    # Archivar/desarchivar una fila de resultados (C-76 tarea 14) — soft-hide
    # administrativo, NO disciplinario.
    #
    # Scoping (corregido en c-78, F-08): ESTA ESCRITURA sí exige pertenencia
    # (`_exigir_pertenencia`, abajo), igual que todas las escrituras del panel
    # académico. La afirmación anterior — "mismo scoping por comisión que el resto
    # del panel" — era cierta para las escrituras y FALSA para las lecturas: cuatro
    # GET del router leían sin exigir pertenencia. Ese desbalance se corrigió
    # aparte (ver test_pertenencia_lectura_panel_academico.py) por ser RBAC sobre
    # datos de alumnos, no un número en pantalla; acá solo queda el texto diciendo
    # el estado real en vez de una generalización que no se cumplía.
    #
    # Y "coordinador global" ya no aplica: c-79 lo acotó a SUS materias asignadas
    # (materia_coordinador). Solo admin_sistema tiene alcance institucional.
    # -----------------------------------------------------------------------

    @router.patch(
        "/{examen_id}/resultados/{session_id}/archivar",
        response_model=ArchivarResultadoResponse,
        summary="Archiva o desarchiva una fila de resultados (soft-hide administrativo)",
    )
    async def archivar_resultado(
        examen_id: str,
        session_id: str,
        body: ArchivarResultadoRequest,
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> ArchivarResultadoResponse:
        await _exigir_pertenencia(principal, examen_id)
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        from sqlalchemy import select as _select
        from app.infrastructure.persistence.models.proctoring import (
            ProctoringSessionModel,
        )

        async with session_factory() as session:
            row = (
                await session.execute(
                    _select(ProctoringSessionModel).where(
                        ProctoringSessionModel.id == session_id,
                        ProctoringSessionModel.examen_contenido_id == examen_id,
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "sesion_no_encontrada",
                        "mensaje": "La sesión no existe o no pertenece a este examen.",
                    },
                )
            row.archivado = body.archivado
            await session.commit()

        # C-76 tarea 20.2: gap de auditoría detectado en la tarea 14 y nunca
        # corregido — archivar/desarchivar una fila de resultados no quedaba
        # trazado. Reusa ModuloAuditoria.SESIONES (mismo prefijo "sesion." que
        # el delete de sesión de test, tarea 20.1). Best-effort: no bloquea la
        # respuesta si el registro de auditoría falla.
        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.RESULTADO_ARCHIVAR,
            modulo=ModuloAuditoria.SESIONES,
            entidad=EntidadAuditoria.SESION,
            entidad_id=session_id,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"Archivó el resultado {session_id}"
                if body.archivado
                else f"Desarchivó el resultado {session_id}"
            ),
        )

        return ArchivarResultadoResponse(session_id=session_id, archivado=body.archivado)

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
        - ULTIMO     → por alumno, la sesión más RECIENTE por `creada_en`.
        - PRIMERO    → por alumno, la sesión más ANTIGUA por `creada_en`.

        c-78 D7: `creada_en` es el criterio real, no `session_id`. Los ids son
        UUID v4 (`gen_random_uuid()`), así que ordenar por id era ordenar al azar:
        con dos intentos, "la última" era la que saliera. Eso decide QUÉ NOTA se
        escribe en Moodle, o sea que el bug producía notas académicas equivocadas.

        El desempate es por `session_id` para que el resultado sea DETERMINÍSTICO
        cuando dos sesiones comparten timestamp (no para ordenarlas por tiempo).
        Una fila sin `sesion_creada_en` proyectado cae al final del orden temporal
        y queda decidida por el id: es el peor caso, pero nunca revienta el envío.

        La deduplicación es por `alumno_idnumber` (legajo). Si es None, se trata
        cada fila como alumno distinto (no hay forma de deduplicar sin identidad).
        """
        # Sentinelas para las filas sin timestamp proyectado (ver docstring). Se
        # comparan contra datetimes tz-aware, que es como los devuelve la columna.
        _MUY_VIEJO = datetime.min.replace(tzinfo=UTC)
        _MUY_NUEVO = datetime.max.replace(tzinfo=UTC)

        def _clave_temporal(fila, *, sin_fecha):
            """(creada_en, session_id): tiempo real primero, id solo para desempatar."""
            creada_en = getattr(fila, "sesion_creada_en", None)
            return (creada_en or sin_fecha, fila.session_id)

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
                # Sin fecha → al final, para no ganar "el primero" por omisión.
                elegida = min(
                    intentos, key=lambda f: _clave_temporal(f, sin_fecha=_MUY_NUEVO)
                )
            else:  # ULTIMO
                elegida = max(
                    intentos, key=lambda f: _clave_temporal(f, sin_fecha=_MUY_VIEJO)
                )
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
        body: SincronizarMoodleRequest | None = None,
    ) -> SincronizarMoodleResponse:
        """Envía a Moodle las notas en estado 'pendiente'/'fallido' del examen.

        Idempotente: las 'enviado' NO se re-mandan (las excluye la query). Si Moodle
        no está configurado (writeback_svc None), NO crashea: devuelve todo como
        'sin_token' y deja las notas en 'pendiente'.

        Body opcional (``SincronizarMoodleRequest``):
        - Ausente o ``session_ids`` vacío/None → todas las pendientes (comportamiento original).
        - ``session_ids`` con valores → sincroniza SOLO esas sesiones.
          Las retenciones D15 (en_riesgo/anulada) se aplican igual aunque la sesión esté en la lista.
        """

        await _exigir_pertenencia(principal, examen_id)
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada.",
            )

        # El titulo, para que la auditoria la lea una persona y no un UUID.
        titulo_examen = await _titulo_examen(session_factory, examen_id)

        # Extraer session_ids del body opcional (None = todas las pendientes).
        session_ids_filtro: list[str] | None = None
        if body is not None and body.session_ids:
            session_ids_filtro = body.session_ids

        async with session_factory() as session:
            pendientes = await listar_estados_sincronizables(
                db=session, examen_id=examen_id, session_ids=session_ids_filtro
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
        # El modo (lote completo / selección) también queda registrado.
        modo_sinc = (
            f"selección de {len(session_ids_filtro)} sesión(es)"
            if session_ids_filtro
            else "lote completo"
        )
        await registrar_seguro(
            session_factory,
            actor=principal.email,
            accion=AccionAuditoria.MOODLE_SYNC,
            modulo=ModuloAuditoria.MOODLE,
            entidad=EntidadAuditoria.EXAMEN,
            entidad_id=str(examen_id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            proposito=(
                f"Sincronizó las notas del examen «{titulo_examen}» a Moodle "
                f"({modo_sinc}): {enviadas} enviada(s), {fallidas} fallida(s) de {total}"
            ),
        )

        return SincronizarMoodleResponse(
            enviadas=enviadas,
            fallidas=fallidas,
            sin_token=0,
            total=total,
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
        """Crea uno o varios exámenes de contenido en un solo paso.

        Para cada item de ``sorteo``, extrae ``cantidad`` preguntas aleatorias del banco
        de la categoría indicada (None = sin clasificar). Todas quedan con seleccionada=True.

        c-78 E-06: con ``comision_ids`` el mismo examen se crea para varias comisiones
        de la materia. Se sortea UNA vez y ese set exacto se copia a N exámenes
        independientes (D12) — así las comisiones rinden lo mismo y las notas son
        comparables. Es todo o nada: cualquier error deja la base sin ningún examen.

        Errores:
        - 422 si alguna categoría tiene menos preguntas disponibles que las pedidas.
        - 422 si alguna comisión pedida no es de la materia del banco.
        - 404 si la materia o alguna comisión no existe, o el usuario no tiene acceso.
        """
        await _exigir_pertenencia_materia(principal, body.materia_id)
        # Una sola lista de destinos para las dos formas del body: `comision_id`
        # (una comisión, la forma de siempre) y `comision_ids` (varias). Un examen
        # sin comisión sigue siendo válido: la lista queda en [None].
        comisiones_destino: list[str | None] = (
            list(body.comision_ids)
            if body.comision_ids is not None
            else [body.comision_id]
        )
        for destino in comisiones_destino:
            if destino is not None:
                await _exigir_pertenencia_comision(principal, destino)
        if session_factory is None:
            raise HTTPException(status_code=500, detail="Persistencia no inicializada.")

        if body.nota_aprobacion > body.nota_maxima:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "config_invalida",
                    "mensaje": (
                        f"nota_aprobacion ({body.nota_aprobacion}) no puede superar "
                        f"nota_maxima ({body.nota_maxima})."
                    ),
                },
            )

        import random
        import uuid as _uuid
        from sqlalchemy import select as _select
        from sqlalchemy.orm import selectinload as _selectinload
        from app.infrastructure.persistence.models.exam_content import (
            BlankBancoModel,
            CategoriaPreguntaModel,
            ComisionModel,
            ExamenContenidoModel,
            OpcionClozeBlancoModel,
            OpcionRespuestaModel,
            PreguntaBancoModel,
            PreguntaClozeBlankModel,
            PreguntaExamenModel,
            TramoSorteoExamenModel,
        )

        async with session_factory() as session:
            # ── Validar las comisiones ANTES de sortear nada ─────────────────
            # Todo o nada: una comisión de otra materia recibiría preguntas de un
            # banco que esa comisión no cursa, y una que no existe reventaría
            # recién en el INSERT, con el sorteo ya hecho.
            codigo_por_comision: dict[str, str] = {}
            ids_pedidos = [c for c in comisiones_destino if c is not None]
            if ids_pedidos:
                # Un id que no es UUID no puede existir, y meterlo en un WHERE
                # tipado UUID rompe con un error de asyncpg en vez de un 404.
                for cid in ids_pedidos:
                    try:
                        _uuid.UUID(cid)
                    except ValueError:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail={
                                "error": "comision_inexistente",
                                "mensaje": f"La comisión '{cid}' no existe.",
                                "comision_ids": [cid],
                            },
                        ) from None

                filas = await session.execute(
                    _select(
                        ComisionModel.id,
                        ComisionModel.codigo,
                        ComisionModel.materia_id,
                    ).where(ComisionModel.id.in_(ids_pedidos))
                )
                encontradas = {r[0]: (r[1], r[2]) for r in filas.all()}

                faltantes = [c for c in ids_pedidos if c not in encontradas]
                if faltantes:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail={
                            "error": "comision_inexistente",
                            "mensaje": (
                                f"{len(faltantes)} comisión(es) pedida(s) no existe(n). "
                                "No se creó ningún examen."
                            ),
                            "comision_ids": faltantes,
                        },
                    )

                ajenas = [
                    c for c in ids_pedidos if encontradas[c][1] != body.materia_id
                ]
                if ajenas:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={
                            "error": "comision_de_otra_materia",
                            "mensaje": (
                                "Todas las comisiones tienen que ser de la materia del "
                                "banco: el examen se arma con SUS preguntas. No se creó "
                                "ningún examen."
                            ),
                            "comision_ids": ajenas,
                        },
                    )

                codigo_por_comision = {c: encontradas[c][0] for c in ids_pedidos}

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

                if tramo.tipos:
                    stmt = stmt.where(PreguntaBancoModel.tipo.in_(tramo.tipos))

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

                if body.sorteo_por_intento:
                    # c-78 E-07: el examen se lleva el POOL ENTERO del tramo, no
                    # las `cantidad` sorteadas. El sorteo lo hace después cada
                    # intento, contra esta copia — por eso tocar el banco más tarde
                    # no puede dejar a nadie sin examen.
                    preguntas_sorteadas.extend(disponibles)
                    ya_sorteadas.update(p.id for p in disponibles)
                else:
                    elegidas = random.sample(disponibles, tramo.cantidad)
                    preguntas_sorteadas.extend(elegidas)
                    ya_sorteadas.update(p.id for p in elegidas)

            # El tope del examen se valida ANTES de crear nada: es preferible un 422
            # claro a un examen a medio armar. Mismo criterio que el import de XML
            # (LimitePreguntasExcedidoError): no se trunca en silencio.
            #
            # c-78 E-07: con sorteo por intento el tope se compara contra lo que va
            # a RENDIR el alumno (la suma de los tramos), no contra el pool copiado
            # — el pool es a propósito más grande que el examen.
            largo_del_examen = (
                sum(t.cantidad for t in body.sorteo)
                if body.sorteo_por_intento
                else len(preguntas_sorteadas)
            )
            if body.limite_preguntas is not None and largo_del_examen > body.limite_preguntas:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "limite_preguntas_excedido",
                        "mensaje": (
                            f"El sorteo suma {largo_del_examen} preguntas pero el "
                            f"examen admite {body.limite_preguntas}. Ajustá las cantidades "
                            "por categoría o subí el límite."
                        ),
                        "sorteadas": largo_del_examen,
                        "limite": body.limite_preguntas,
                    },
                )

            def _copiar_preguntas_al_examen(examen_id: str) -> None:
                """Copia el set sorteado a un examen recién creado.

                La pregunta se COPIA, no se referencia: el examen queda congelado
                aunque después se edite el banco. Y hay que copiar TAMBIÉN opciones
                y blanks — sin ellos la pregunta llega al alumno sin nada que
                responder y sin nada con qué calificarla.

                Con varias comisiones esto corre una vez por réplica sobre el MISMO
                `preguntas_sorteadas`: todas rinden exactamente las mismas preguntas.

                c-78 E-07: con sorteo por intento esto copia el POOL entero y todo
                queda con `seleccionada=False` — quién entra al examen lo decide el
                sorteo de cada intento, no una marca del examen.
                """
                for orden, pb in enumerate(preguntas_sorteadas):
                    pregunta_id = str(_uuid.uuid4())
                    session.add(
                        PreguntaExamenModel(
                            id=pregunta_id,
                            examen_id=examen_id,
                            enunciado=pb.enunciado,
                            tipo=pb.tipo,
                            orden=orden,
                            seleccionada=not body.sorteo_por_intento,
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

            # ── Crear un examen_contenido por comisión ───────────────────────
            # Las réplicas comparten el lote para que el sistema sepa cuáles
            # nacieron juntas. Un examen solo no es un lote: no tiene hermanas.
            lote_replica_id = (
                str(_uuid.uuid4()) if len(comisiones_destino) > 1 else None
            )

            creados: list[ExamenReplicaItem] = []
            for destino in comisiones_destino:
                examen_id = str(_uuid.uuid4())
                codigo = codigo_por_comision.get(destino) if destino else None
                # El código de comisión entre paréntesis es lo único que distingue
                # a las réplicas donde no hay columna de comisión: el picker de
                # Notas, la auditoría, el buscador. Con un examen solo, sobra.
                titulo = (
                    f"{body.titulo} ({codigo})"
                    if lote_replica_id and codigo
                    else body.titulo
                )
                session.add(
                    ExamenContenidoModel(
                        id=examen_id,
                        titulo=titulo,
                        comision_id=destino,
                        lote_replica_id=lote_replica_id,
                        limite_preguntas=body.limite_preguntas,
                        # Escala configurable por examen (migración 0061): default
                        # 100/60 si el docente no la manda — nunca cae
                        # silenciosamente en "sobre 10". El docente puede pedir
                        # cualquier otra escala en el body.
                        nota_maxima=body.nota_maxima,
                        nota_aprobacion=body.nota_aprobacion,
                        # c-78 E-07
                        borrador=body.borrador,
                        modo_preguntas=(
                            MODO_SORTEO_POR_INTENTO
                            if body.sorteo_por_intento
                            else MODO_FIJO
                        ),
                    )
                )
                await session.flush()
                _copiar_preguntas_al_examen(examen_id)
                if body.sorteo_por_intento:
                    # La REGLA del sorteo viaja con cada réplica: es lo que antes se
                    # perdía (se guardaba el resultado y no la condición que lo
                    # generó), y sin ella el intento no sabría qué sortear.
                    for orden_tramo, tramo in enumerate(body.sorteo):
                        session.add(
                            TramoSorteoExamenModel(
                                id=str(_uuid.uuid4()),
                                examen_id=examen_id,
                                categoria_id=tramo.categoria_id,
                                incluir_subcategorias=tramo.incluir_subcategorias,
                                tipos=list(tramo.tipos) if tramo.tipos else None,
                                cantidad=tramo.cantidad,
                                orden=orden_tramo,
                            )
                        )
                creados.append(
                    ExamenReplicaItem(
                        examen_id=examen_id, comision_id=destino, titulo=titulo
                    )
                )

            # Un solo commit para las N réplicas: o entran todas o no entra ninguna.
            await session.commit()

        return CrearDesdebancoResponse(
            examen_id=creados[0].examen_id,
            titulo=creados[0].titulo,
            total_preguntas=len(preguntas_sorteadas),
            examenes=creados,
            lote_replica_id=lote_replica_id,
        )

    return router
