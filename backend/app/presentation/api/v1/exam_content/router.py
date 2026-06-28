"""Routers de exam_content (FastAPI, C-69).

Admin router:
  POST /moodle-import — admin-only + MFA: importa XML, crea ExamenContenido.

Taking router (student-facing):
  GET /{examen_id} — cualquier principal autenticado: preguntas+opciones sin es_correcta (D3).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.application.exam_content.asociacion_service import AsociacionComisionService
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
    ExamenRendicionResponse,
    ImportReporteResponse,
    MateriaResponse,
    OmitidaItemResponse,
    OpcionRendicionResponse,
    PreguntaRendicionResponse,
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


def create_exam_content_router(session_factory=None) -> APIRouter:
    """Factory que permite inyectar session_factory en tests."""
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
    ) -> ImportReporteResponse:
        """Importa un archivo Moodle XML y crea el examen de contenido."""
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
                report = await service.importar(xml_bytes, titulo=titulo)
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
        response_model=list[ExamenContenidoResumenResponse],
        summary="Listar exámenes de contenido importados (catálogo del alumno)",
    )
    @router.get(
        "/",
        response_model=list[ExamenContenidoResumenResponse],
        include_in_schema=False,
    )
    async def listar_examenes_contenido(
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> list[ExamenContenidoResumenResponse]:
        """Lista todos los exámenes de contenido disponibles para rendir.

        Cualquier principal autenticado puede consultar el catálogo (sin admin ni MFA).
        Devuelve id, titulo y cantidad_preguntas en orden alfabético.
        D3: es_correcta NUNCA incluida — solo metadatos del examen.
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
            resumenes = await repo.listar()

        return [_resumen_to_response(r) for r in resumenes]

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
