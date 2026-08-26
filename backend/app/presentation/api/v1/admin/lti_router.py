"""Administración admin-only del allowlist LTI (C-75, sección 6).

CRUD de `lti_deployment_confiable`: la allowlist de deployments Moodle de
confianza (design D2). Sólo `admin_sistema` puede gestionarla — es el mecanismo
por el que un operador da de alta un Moodle real (o su mapeo curso→comisión) para
que sus launches dejen de fallar cerrado.

DOMINIO CRÍTICO (Auth): estas filas SON la raíz de confianza del flujo LTI. Una
fila de más = un Moodle capaz de crear cuentas en ActiveExam. Por eso el guard es
`require_roles(ADMIN_SISTEMA)` sin excepción y todo schema es `extra='forbid'`.

Endpoints (prefijo del include: `/api/v1/admin`):
  GET    /lti/salud              -> estado de la allowlist (c-78 §10.2)
  POST   /lti/deployments        -> alta (201)
  GET    /lti/deployments        -> listado
  PATCH  /lti/deployments/{id}   -> edición parcial (activo, mapeo, jwks_uri…)
  DELETE /lti/deployments/{id}   -> baja (204)

c-78 §10.1/§10.2/§10.3: las filas ya no se cargan solo a mano — el registro
dinámico (`POST /api/v1/lti/dynamic-registration`) crea la fila con `activo=false`
y desde acá un admin la habilita. `GET /lti/salud` avisa si la allowlist quedó sin
ninguna fila activa, y la pantalla `/admin/lti` opera todo esto sin armar requests.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol
from app.infrastructure.persistence.models.lti import LtiDeploymentConfiableModel
from app.presentation.api.v1.auth.dependencies import require_roles


# ---------------------------------------------------------------------------
# Schemas (extra='forbid' — regla dura del proyecto)
# ---------------------------------------------------------------------------


class DeploymentConfiableCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    iss: str = Field(min_length=1)
    deployment_id: str = Field(min_length=1)
    client_id: str = Field(min_length=1)
    jwks_uri: str = Field(min_length=1)
    context_id: str | None = None
    comision_id: str | None = None
    activo: bool = True


class DeploymentConfiableUpdate(BaseModel):
    """Edición parcial: todos los campos opcionales; sólo se aplican los enviados."""

    model_config = ConfigDict(extra="forbid")

    iss: str | None = Field(default=None, min_length=1)
    deployment_id: str | None = Field(default=None, min_length=1)
    client_id: str | None = Field(default=None, min_length=1)
    jwks_uri: str | None = Field(default=None, min_length=1)
    context_id: str | None = None
    comision_id: str | None = None
    activo: bool | None = None


class DeploymentConfiableResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    iss: str
    deployment_id: str
    client_id: str
    jwks_uri: str
    context_id: str | None
    comision_id: str | None
    activo: bool
    creado_en: str  # ISO 8601


class SaludAllowlistResponse(BaseModel):
    """Estado de la allowlist LTI, en lenguaje que se entiende sin ser técnico."""

    model_config = ConfigDict(extra="forbid")

    deployments_activos: int
    deployments_totales: int
    #: ``True`` cuando NO hay ninguno activo → ningún launch de Moodle va a entrar.
    allowlist_vacia: bool
    #: Explicación lista para mostrar en pantalla (qué pasa y qué hacer).
    mensaje: str


def _to_response(fila: LtiDeploymentConfiableModel) -> DeploymentConfiableResponse:
    return DeploymentConfiableResponse(
        id=str(fila.id),
        iss=fila.iss,
        deployment_id=fila.deployment_id,
        client_id=fila.client_id,
        jwks_uri=fila.jwks_uri,
        context_id=fila.context_id,
        comision_id=fila.comision_id,
        activo=fila.activo,
        creado_en=fila.creado_en.isoformat(),
    )


def create_lti_admin_router(session_factory=None) -> APIRouter:
    """Factory del router admin del allowlist LTI.

    Args:
        session_factory: sessionmaker async; si es None se toma de
            ``request.app.state.session_factory`` (patrón session-per-request).
    """
    router = APIRouter()
    _require_admin = require_roles(Rol.ADMIN_SISTEMA)

    def _factory(request: Request) -> async_sessionmaker[AsyncSession]:
        factory = session_factory or getattr(
            request.app.state, "session_factory", None
        )
        if factory is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Base de datos no disponible.",
            )
        return factory

    @router.get(
        "/lti/salud",
        response_model=SaludAllowlistResponse,
        summary="Estado de la allowlist LTI (avisa si quedó sin deployments activos)",
    )
    async def salud_allowlist(
        request: Request,
        _admin: AuthenticatedPrincipal = Depends(_require_admin),
    ) -> SaludAllowlistResponse:
        """Señal de salud de la raíz de confianza LTI (c-78 §10.2).

        Con la allowlist sin ninguna fila ACTIVA, todo launch responde 403
        `lti_iss_no_confiable`. Pasaba cada vez que se recreaba la base, y la
        única señal era un alumno que no podía entrar — o sea, el peor momento
        posible para enterarse. Acá se puede mirar antes.
        """
        async with _factory(request)() as session:
            totales = (
                await session.execute(
                    select(func.count()).select_from(LtiDeploymentConfiableModel)
                )
            ).scalar_one()
            activos = (
                await session.execute(
                    select(func.count())
                    .select_from(LtiDeploymentConfiableModel)
                    .where(LtiDeploymentConfiableModel.activo.is_(True))
                )
            ).scalar_one()

        activos = int(activos or 0)
        totales = int(totales or 0)
        if activos > 0:
            mensaje = (
                f"La integración LTI está operativa: {activos} "
                f"{'campus habilitado' if activos == 1 else 'campus habilitados'}."
            )
        elif totales > 0:
            mensaje = (
                f"Hay {totales} registro(s) de campus pero NINGUNO está habilitado. "
                "Los alumnos no van a poder entrar desde Moodle hasta que habilites "
                "al menos uno."
            )
        else:
            mensaje = (
                "No hay ningún campus registrado. Registrá ActiveExam desde Moodle "
                "(registro dinámico) y después habilitá el registro que aparezca acá. "
                "Mientras tanto, ningún alumno puede entrar desde Moodle."
            )

        return SaludAllowlistResponse(
            deployments_activos=activos,
            deployments_totales=totales,
            allowlist_vacia=activos == 0,
            mensaje=mensaje,
        )

    @router.post(
        "/lti/deployments",
        status_code=status.HTTP_201_CREATED,
        response_model=DeploymentConfiableResponse,
        summary="Da de alta un deployment Moodle confiable (allowlist LTI)",
    )
    async def crear_deployment(
        request: Request,
        body: DeploymentConfiableCreate,
        _admin: AuthenticatedPrincipal = Depends(_require_admin),
    ) -> DeploymentConfiableResponse:
        async with _factory(request)() as session:
            fila = LtiDeploymentConfiableModel(
                iss=body.iss,
                deployment_id=body.deployment_id,
                client_id=body.client_id,
                jwks_uri=body.jwks_uri,
                context_id=body.context_id,
                comision_id=body.comision_id,
                activo=body.activo,
            )
            session.add(fila)
            await session.commit()
            await session.refresh(fila)
            return _to_response(fila)

    @router.get(
        "/lti/deployments",
        response_model=list[DeploymentConfiableResponse],
        summary="Lista los deployments confiables del allowlist LTI",
    )
    async def listar_deployments(
        request: Request,
        _admin: AuthenticatedPrincipal = Depends(_require_admin),
    ) -> list[DeploymentConfiableResponse]:
        async with _factory(request)() as session:
            filas = (
                await session.execute(
                    select(LtiDeploymentConfiableModel).order_by(
                        LtiDeploymentConfiableModel.creado_en.desc()
                    )
                )
            ).scalars().all()
            return [_to_response(f) for f in filas]

    @router.patch(
        "/lti/deployments/{dep_id}",
        response_model=DeploymentConfiableResponse,
        summary="Edita un deployment confiable (parcial)",
    )
    async def editar_deployment(
        request: Request,
        dep_id: str,
        body: DeploymentConfiableUpdate,
        _admin: AuthenticatedPrincipal = Depends(_require_admin),
    ) -> DeploymentConfiableResponse:
        cambios = body.model_dump(exclude_unset=True)
        async with _factory(request)() as session:
            fila = await session.get(LtiDeploymentConfiableModel, dep_id)
            if fila is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="deployment_no_encontrado",
                )
            for campo, valor in cambios.items():
                setattr(fila, campo, valor)
            await session.commit()
            await session.refresh(fila)
            return _to_response(fila)

    @router.delete(
        "/lti/deployments/{dep_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        response_model=None,
        summary="Baja de un deployment confiable",
    )
    async def borrar_deployment(
        request: Request,
        dep_id: str,
        _admin: AuthenticatedPrincipal = Depends(_require_admin),
    ) -> None:
        async with _factory(request)() as session:
            resultado = await session.execute(
                delete(LtiDeploymentConfiableModel).where(
                    LtiDeploymentConfiableModel.id == dep_id
                )
            )
            await session.commit()
            if resultado.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="deployment_no_encontrado",
                )

    return router
