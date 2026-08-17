"""Router del consentimiento informado (FastAPI, C-08).

Endpoints del estudiante autenticado (C-06 ``get_current_principal``). El acuse se
asocia al ``username`` del principal (no se confia en un user_id del body).
Errores de dominio -> 422 (falta accion afirmativa / version desconocida) y 403
(gate no resuelto).

Endpoints adicionales de admin (C-08 ext, Ley 25.326):
- GET /text/versions: lista versiones (admin_sistema).
- POST /text/versions: publica nueva version (admin_sistema).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.application.consent.service import ConsentService
from app.application.consent.text_version_service import ConsentTextoVersionService
from app.application.config.service import ConfigService
from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol
from app.domain.consent_flow.errors import (
    ConsentNotResolvedError,
    MissingAffirmativeActionError,
    UnknownConsentVersionError,
)
from app.domain.consent_flow.rules import ResolucionConsentimiento
from app.presentation.api.v1.auth.dependencies import get_current_principal, require_roles
from app.presentation.api.v1.consent.dependencies import get_consent_service
from app.presentation.api.v1.consent.schemas import (
    AlternativeRequest,
    AlternativeResponse,
    BloqueConsentimiento,
    ConsentResponse,
    ConsentTextResponse,
    ConsentVersionCreate,
    ConsentVersionListItem,
    GateResponse,
    HabilitarAlternativaRequest,
    HabilitarAlternativaResponse,
    PendienteItem,
    PendientesResponse,
    RecordConsentRequest,
)

router = APIRouter()

_require_admin = require_roles(Rol.ADMIN_SISTEMA)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_session_factory(request: Request):
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de datos no disponible.",
        )
    return factory


def _get_config_service(request: Request) -> ConfigService:
    svc = getattr(request.app.state, "config_service", None)
    if svc is None:
        svc = ConfigService(_get_session_factory(request))
        request.app.state.config_service = svc
    return svc


@router.get("/text/versions", response_model=list[ConsentVersionListItem])
async def list_text_versions(
    request: Request,
    _principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> list[ConsentVersionListItem]:
    """Lista todas las versiones del texto de consentimiento (solo admin_sistema)."""
    factory = _get_session_factory(request)
    async with factory() as session:
        svc = ConsentTextoVersionService(session)
        items = await svc.list_versions()
    return [
        ConsentVersionListItem(
            version=item.version,
            hash_texto=item.hash_texto,
            created_at=item.created_at,
        )
        for item in items
    ]


@router.post(
    "/text/versions",
    response_model=ConsentTextResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_text_version(
    body: ConsentVersionCreate,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> ConsentTextResponse:
    """Publica una nueva version del texto de consentimiento (solo admin_sistema).

    409 si la version ya existe (append-only: el texto nunca muta).
    """
    factory = _get_session_factory(request)
    bloques_dict = [{"titulo": b.titulo, "cuerpo": b.cuerpo} for b in body.bloques]
    async with factory() as session:
        svc = ConsentTextoVersionService(session)
        try:
            vista = await svc.create_version(body.version, bloques_dict)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc
        await session.commit()
    return ConsentTextResponse(
        version=vista.version,
        bloques=[BloqueConsentimiento(titulo=b.titulo, cuerpo=b.cuerpo) for b in vista.bloques],
        hash_texto=vista.hash_texto,
    )


@router.get("/text", response_model=ConsentTextResponse)
async def get_text(
    request: Request,
    service: ConsentService = Depends(get_consent_service),
    version: str | None = Query(default=None),
    _principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> ConsentTextResponse:
    """Texto vigente del consentimiento (cinco bloques + version, RN-CO-01).

    Sin ?version: devuelve la version vigente segun config (consent_version_vigente).
    Con ?version=X: devuelve esa version especifica desde la DB.

    Prioriza la tabla ``consent_texto_version`` (DB). Fallback a text_catalog en
    memoria si la tabla no esta disponible o la version no existe.
    """
    factory = getattr(request.app.state, "session_factory", None)

    if factory is not None:
        async with factory() as session:
            tv_svc = ConsentTextoVersionService(session)
            try:
                if version is not None:
                    # version especifica
                    try:
                        vista = await tv_svc.get_version(version)
                    except KeyError as exc:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
                        ) from exc
                else:
                    # version vigente desde config
                    config_svc = _get_config_service(request)
                    cfg = await config_svc.get_efectiva()
                    vista = await tv_svc.get_vigente(cfg.consent_version_vigente)
                return ConsentTextResponse(
                    version=vista.version,
                    bloques=[
                        BloqueConsentimiento(titulo=b.titulo, cuerpo=b.cuerpo)
                        for b in vista.bloques
                    ],
                    hash_texto=vista.hash_texto,
                )
            except HTTPException:
                raise
            except Exception:
                # Fallback a catalogo en memoria si la tabla no existe aun
                pass

    # Fallback legacy: catalogo en memoria
    try:
        vista_legacy = service.get_text_view(version)
    except UnknownConsentVersionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return ConsentTextResponse(
        version=vista_legacy.version,
        bloques=vista_legacy.bloques,
        hash_texto=vista_legacy.hash_texto,
    )


@router.post("", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED)
async def record_consent(
    body: RecordConsentRequest,
    service: ConsentService = Depends(get_consent_service),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> ConsentResponse:
    """Registra el acuse inmutable; 422 si falta accion afirmativa (D2)."""
    try:
        acuse = await service.record_consent(
            user_id=principal.username,
            exam_id=body.exam_id,
            version_texto=body.version_texto,
            affirmative_action=body.affirmative_action,
            timestamp=_now_iso(),
        )
    except (MissingAffirmativeActionError, UnknownConsentVersionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except RuntimeError as exc:
        # Modulo activeexam: NoOpConsentRepository.add() no persiste el acuse
        # por-rendicion (tabla `consentimiento` no existe fuera del modulo
        # full). El consentimiento de perfil (RN-CO) ya quedo registrado via
        # /consent/profile; este endpoint es un extra no soportado en activeexam.
        # 501 controlado en vez de dejar que el RuntimeError explote como 500.
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)
        ) from exc
    return ConsentResponse(
        id=acuse.id,
        user_id=acuse.user_id,
        exam_id=acuse.exam_id,
        version_texto=acuse.version_texto,
        timestamp=acuse.timestamp,
        hash=acuse.hash,
    )


@router.post("/alternative", response_model=AlternativeResponse)
async def choose_alternative(
    body: AlternativeRequest,
    service: ConsentService = Depends(get_consent_service),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> AlternativeResponse:
    """Elige la via alternativa sin biometria; escala a coordinador, NO aborta (D3).

    C-63: registra la solicitud con estado pendiente_coordinador y retorna
    puede_rendir=False hasta que el coordinador habilite.
    """
    now = _now_iso()
    mensaje_id = await service.choose_alternative(
        user_id=principal.username,
        exam_id=body.exam_id,
        timestamp=now,
    )
    return AlternativeResponse(
        exam_id=body.exam_id,
        via_alternativa=True,
        escalado_a_coordinador=True,
        mensaje_id=mensaje_id,
        estado="pendiente_coordinador",
        puede_rendir=False,
    )


@router.post(
    "/alternative/{user_id}/habilitar",
    response_model=HabilitarAlternativaResponse,
)
async def habilitar_alternativa(
    user_id: str,
    body: HabilitarAlternativaRequest,
    service: ConsentService = Depends(get_consent_service),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> HabilitarAlternativaResponse:
    """Habilita la solicitud de via alternativa de un alumno (coordinador/admin).

    C-63 D-06: solo accesible por roles coordinador o admin.
    Transiciona pendiente_coordinador -> habilitado_por_coordinador.
    404 si no existe solicitud para el par (user_id, exam_id).
    403 si el principal no tiene rol coordinador ni admin.
    """
    roles = set(getattr(principal, "roles", []))
    if not roles.intersection({"coordinador", "admin", "admin_sistema"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol coordinador o admin para habilitar la via alternativa.",
        )
    try:
        solicitud = await service.habilitar_alternativa(
            user_id=user_id,
            exam_id=body.exam_id,
            habilitado_por=principal.username,
            timestamp=_now_iso(),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return HabilitarAlternativaResponse(
        user_id=solicitud.user_id,
        exam_id=solicitud.exam_id,
        estado=solicitud.estado.value,
        habilitado_por=solicitud.habilitado_por,
        timestamp_habilitacion=solicitud.timestamp_habilitacion,
    )


@router.get("/alternative/pendientes", response_model=PendientesResponse)
async def listar_pendientes(
    service: ConsentService = Depends(get_consent_service),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> PendientesResponse:
    """Lista solicitudes de via alternativa pendientes de habilitacion (coordinador/admin).

    C-63 D-06: solo accesible por roles coordinador o admin. Sin paginacion (D-08 Open Q).
    """
    roles = set(getattr(principal, "roles", []))
    if not roles.intersection({"coordinador", "admin", "admin_sistema"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol coordinador o admin para ver las solicitudes pendientes.",
        )
    solicitudes = await service.listar_pendientes()
    return PendientesResponse(
        items=[
            PendienteItem(
                user_id=s.user_id,
                exam_id=s.exam_id,
                timestamp_solicitud=s.timestamp_solicitud,
            )
            for s in solicitudes
        ]
    )


@router.get("/gate", response_model=GateResponse)
async def gate(
    service: ConsentService = Depends(get_consent_service),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    exam_id: str = Query(...),
) -> GateResponse:
    """Estado del gate de consentimiento (consumible por C-09, D4).

    C-63: VIA_ALTERNATIVA_PENDIENTE -> puede_avanzar=False (gate cerrado hasta habilitacion).
    VIA_ALTERNATIVA_HABILITADA -> puede_avanzar=True (coordinador habilito; biometria no requerida).
    """
    resolucion = await service.resolve(
        user_id=principal.username, exam_id=exam_id
    )
    # Gate: puede avanzar solo si no es NO_RESUELTO ni PENDIENTE
    puede_avanzar = resolucion not in (
        ResolucionConsentimiento.NO_RESUELTO,
        ResolucionConsentimiento.VIA_ALTERNATIVA_PENDIENTE,
    )
    return GateResponse(
        exam_id=exam_id,
        resolucion=resolucion.value,
        puede_avanzar=puede_avanzar,
        biometria_habilitada=resolucion == ResolucionConsentimiento.CONSENTIDO,
    )
