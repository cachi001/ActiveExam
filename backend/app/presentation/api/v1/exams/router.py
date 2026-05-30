"""Router de configuracion de examen (FastAPI, C-07).

Toda la superficie es ADMIN-ONLY + MFA: las dependencias de C-06
(``require_roles(ADMIN_EXAMENES)`` + ``require_mfa``) se aplican a nivel de router,
de modo que un rol no-admin -> 403 y un admin sin MFA -> 403, SIN logica de
autorizacion propia en C-07 (D1, single source of truth en C-06).

La validacion de parametros (D4) la levanta el dominio como ``InvalidExamConfigError``
y aqui se traduce a 422 con detalle por campo. Pydantic ``extra='forbid'`` (regla
dura) en los schemas -> 422 ante campos no declarados.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.application.exam_config.service import ExamConfigInput, ExamConfigService
from app.domain.auth.roles import Rol
from app.domain.exam_config.errors import InvalidExamConfigError
from app.presentation.api.v1.auth.dependencies import require_mfa, require_roles
from app.presentation.api.v1.exams.dependencies import (
    get_exam_service,
    get_presign_service,
)
from app.presentation.api.v1.exams.schemas import (
    AssignProctorsRequest,
    AssignProctorsResponse,
    EnabledStudentsRequest,
    EnabledStudentsResponse,
    ExamCreateRequest,
    ExamResponse,
    ReferencePhotoRequest,
    ReferencePhotoResponse,
)
from app.infrastructure.storage.presign import PresignService

# Guards admin-only + MFA (C-06) a nivel de router: aplican a TODOS los endpoints.
router = APIRouter(
    dependencies=[
        Depends(require_roles(Rol.ADMIN_EXAMENES)),
        Depends(require_mfa),
    ]
)


def _to_response(examen) -> ExamResponse:
    return ExamResponse(
        id=examen.id,
        nombre=examen.nombre,
        umbral_score=examen.umbral_score,
        detectores=list(examen.detectores),
        ventana=dict(examen.ventana),
        retencion=dict(examen.retencion),
        parametros=dict(examen.parametros),
    )


def _input(body: ExamCreateRequest) -> ExamConfigInput:
    return ExamConfigInput(
        nombre=body.nombre,
        inicio=body.inicio,
        fin=body.fin,
        umbral_score=body.umbral_score,
        detectores=tuple(body.detectores),
        umbrales_detector=dict(body.umbrales_detector),
        politica_retencion=body.politica_retencion,
        exige_biometria=body.exige_biometria,
    )


def _raise_422(exc: InvalidExamConfigError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"errores": exc.detalles},
    )


@router.post("", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
async def create_exam(
    body: ExamCreateRequest,
    service: ExamConfigService = Depends(get_exam_service),
) -> ExamResponse:
    try:
        examen = await service.create_exam(_input(body))
    except InvalidExamConfigError as exc:
        raise _raise_422(exc) from exc
    return _to_response(examen)


@router.get("", response_model=list[ExamResponse])
async def list_exams(
    service: ExamConfigService = Depends(get_exam_service),
    desde: str | None = Query(default=None, alias="from"),
    hasta: str | None = Query(default=None, alias="to"),
    estado: str | None = Query(default=None, alias="status"),
) -> list[ExamResponse]:
    examenes = await service.list_for_operations(desde=desde, hasta=hasta, estado=estado)
    return [_to_response(e) for e in examenes]


@router.get("/{exam_id}", response_model=ExamResponse)
async def get_exam(
    exam_id: str,
    service: ExamConfigService = Depends(get_exam_service),
) -> ExamResponse:
    examen = await service.get_exam(exam_id)
    if examen is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Examen no encontrado.")
    return _to_response(examen)


@router.patch("/{exam_id}", response_model=ExamResponse)
async def update_exam(
    exam_id: str,
    body: ExamCreateRequest,
    service: ExamConfigService = Depends(get_exam_service),
) -> ExamResponse:
    try:
        examen = await service.update_exam(exam_id, _input(body))
    except InvalidExamConfigError as exc:
        raise _raise_422(exc) from exc
    if examen is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Examen no encontrado.")
    return _to_response(examen)


@router.delete("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam(
    exam_id: str,
    service: ExamConfigService = Depends(get_exam_service),
) -> Response:
    existia = await service.delete_exam(exam_id)
    if not existia:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Examen no encontrado.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{exam_id}/students", response_model=EnabledStudentsResponse)
async def set_students(
    exam_id: str,
    body: EnabledStudentsRequest,
    service: ExamConfigService = Depends(get_exam_service),
) -> EnabledStudentsResponse:
    examen = await service.set_enabled_students(exam_id, body.estudiantes)
    if examen is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Examen no encontrado.")
    return EnabledStudentsResponse(
        estudiantes=list(examen.parametros.get("estudiantes_habilitados", []))
    )


@router.get("/{exam_id}/students", response_model=EnabledStudentsResponse)
async def get_students(
    exam_id: str,
    service: ExamConfigService = Depends(get_exam_service),
) -> EnabledStudentsResponse:
    estudiantes = await service.get_enabled_students(exam_id)
    if estudiantes is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Examen no encontrado.")
    return EnabledStudentsResponse(estudiantes=estudiantes)


@router.put("/{exam_id}/proctors", response_model=AssignProctorsResponse)
async def assign_proctors(
    exam_id: str,
    body: AssignProctorsRequest,
    service: ExamConfigService = Depends(get_exam_service),
) -> AssignProctorsResponse:
    await service.assign_proctors(exam_id, body.proctores)
    return AssignProctorsResponse(proctores=body.proctores)


@router.post("/{exam_id}/reference-photo", response_model=ReferencePhotoResponse)
async def reference_photo(
    exam_id: str,
    body: ReferencePhotoRequest,
    service: ExamConfigService = Depends(get_exam_service),
    presign: PresignService = Depends(get_presign_service),
) -> ReferencePhotoResponse:
    """Registra la referencia: presign URL (carga directa, D2) o precomputada."""
    upload_url = object_key = None
    expires_in = None
    uri = None
    if not body.precomputada:
        object_key = f"reference-photos/{exam_id}/{body.estudiante_id}"
        presigned = presign.presign_upload(object_key=object_key)
        upload_url = presigned.url
        expires_in = presigned.expires_in
        uri = presigned.url
    examen = await service.register_reference(
        exam_id,
        body.estudiante_id,
        uri=uri,
        hash_binario=body.hash_binario,
        precomputada=body.precomputada,
    )
    if examen is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Examen no encontrado.")
    return ReferencePhotoResponse(
        estudiante_id=body.estudiante_id,
        precomputada=body.precomputada,
        upload_url=upload_url,
        object_key=object_key,
        expires_in=expires_in,
    )
