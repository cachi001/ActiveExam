"""Router de configuracion de scoring por tipo de evento (#9 / #10).

Endpoints:
- ``GET    /config``               : lista los pesos configurados (admin_sistema).
- ``PATCH  /config/{tipo_evento}`` : actualiza peso / severidad / descripcion / activo.

Tabla underlying: ``evento_score_config`` (migracion 0011). Las filas se siembran
en el upgrade con los 8 tipos del catalogo y sus pesos default. Este router
solo edita; no agrega ni borra tipos (catalogo es codigo, no datos).

Reglas duras:
- ``extra='forbid'`` en todos los schemas.
- Solo ``admin_sistema`` accede a ambos endpoints.
- ``peso`` se valida en [0, 100] tanto en Pydantic como en CHECK constraint de Postgres.
- 404 si el ``tipo_evento`` no existe en la tabla (no auto-crea).
- El backend NO sanciona automaticamente (L2.5). El peso solo determina la prioridad
  para revision humana.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.auth.identity import AuthenticatedPrincipal
from app.domain.auth.roles import Rol
from app.infrastructure.persistence.models.transactional import EventoScoreConfigModel
from app.presentation.api.v1.auth.dependencies import get_current_principal, require_roles

router = APIRouter()

_require_admin = require_roles(Rol.ADMIN_SISTEMA)

_SEVERIDADES_VALIDAS = {"baseline", "baja", "media", "alta", "critica"}


# ---------------------------------------------------------------------------
# Schemas (extra='forbid' — regla dura)
# ---------------------------------------------------------------------------


class EventoScoreConfigResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo_evento: str
    severidad: str
    peso: int
    descripcion: str | None
    activo: bool
    updated_at: str


class ListarConfigResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[EventoScoreConfigResponse]


class PesosEventoResponse(BaseModel):
    """Mapa de pesos activos por tipo de evento. Lo que el cliente del examen
    necesita para puntuar — sin metadata (descripcion / updated_at)."""

    model_config = ConfigDict(extra="forbid")

    weights: dict[str, int]


class EditarEventoScoreConfigRequest(BaseModel):
    """Schema para PATCH /config/{tipo_evento}.

    Todos los campos son opcionales — solo se actualizan los que vienen. Si todos
    son None, devuelve 400 (no hay nada que cambiar)."""

    model_config = ConfigDict(extra="forbid")

    severidad: str | None = None
    peso: int | None = Field(default=None, ge=0, le=100)
    descripcion: str | None = None
    activo: bool | None = None

    @field_validator("severidad")
    @classmethod
    def severidad_valida(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in _SEVERIDADES_VALIDAS:
            raise ValueError(
                f"Severidad invalida: {v!r}. Validas: {sorted(_SEVERIDADES_VALIDAS)}"
            )
        return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de datos no disponible.",
        )
    return factory


def _to_response(m: EventoScoreConfigModel) -> EventoScoreConfigResponse:
    return EventoScoreConfigResponse(
        tipo_evento=m.tipo_evento,
        severidad=m.severidad,
        peso=m.peso,
        descripcion=m.descripcion,
        activo=m.activo,
        updated_at=str(m.updated_at),
    )


# ---------------------------------------------------------------------------
# GET /config — listar configs (admin_sistema)
# ---------------------------------------------------------------------------


@router.get("/config", response_model=ListarConfigResponse)
async def listar_configs(
    request: Request,
    _principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> ListarConfigResponse:
    """Lista todos los pesos configurados (uno por tipo de evento)."""
    session_factory = _get_session_factory(request)
    async with session_factory() as session:
        result = await session.execute(
            select(EventoScoreConfigModel).order_by(EventoScoreConfigModel.tipo_evento)
        )
        items = result.scalars().all()
    return ListarConfigResponse(items=[_to_response(it) for it in items])


# ---------------------------------------------------------------------------
# GET /weights — mapa { tipo: peso } solo de tipos activos (cualquier sesion)
# ---------------------------------------------------------------------------


@router.get("/weights", response_model=PesosEventoResponse)
async def obtener_pesos(
    request: Request,
    _principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> PesosEventoResponse:
    """Devuelve el mapa { tipo_evento: peso } SOLO de tipos activos.

    Cualquier usuario autenticado puede leerlo (lo necesita el cliente del examen
    para calcular el score acumulado en tiempo real, sin hardcodear los pesos).
    Tipos con activo=False NO aparecen en el mapa — el cliente trata su peso como 0.
    """
    session_factory = _get_session_factory(request)
    async with session_factory() as session:
        result = await session.execute(
            select(
                EventoScoreConfigModel.tipo_evento,
                EventoScoreConfigModel.peso,
            ).where(EventoScoreConfigModel.activo.is_(True))
        )
        rows = result.all()
    return PesosEventoResponse(weights={row.tipo_evento: row.peso for row in rows})


# ---------------------------------------------------------------------------
# PATCH /config/{tipo_evento} — editar peso / severidad / descripcion / activo
# ---------------------------------------------------------------------------


@router.patch("/config/{tipo_evento}", response_model=EventoScoreConfigResponse)
async def editar_config(
    tipo_evento: str,
    body: EditarEventoScoreConfigRequest,
    request: Request,
    _principal: AuthenticatedPrincipal = Depends(_require_admin),
) -> EventoScoreConfigResponse:
    """Edita el peso / severidad / descripcion / activo de un tipo de evento.

    400 si el body no trae ningun campo (no hay update).
    404 si el tipo_evento no existe (catalogo es codigo, no datos).
    """
    if (
        body.severidad is None
        and body.peso is None
        and body.descripcion is None
        and body.activo is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El body debe incluir al menos un campo a actualizar.",
        )

    session_factory = _get_session_factory(request)
    async with session_factory() as session:
        result = await session.execute(
            select(EventoScoreConfigModel).where(
                EventoScoreConfigModel.tipo_evento == tipo_evento
            )
        )
        cfg = result.scalar_one_or_none()
        if cfg is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tipo de evento {tipo_evento!r} no encontrado.",
            )

        if body.severidad is not None:
            cfg.severidad = body.severidad
        if body.peso is not None:
            cfg.peso = body.peso
        if body.descripcion is not None:
            cfg.descripcion = body.descripcion
        if body.activo is not None:
            cfg.activo = body.activo

        await session.commit()
        await session.refresh(cfg)

    return _to_response(cfg)
