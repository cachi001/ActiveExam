"""Router de auditoría (C-20): lectura del registro de actividad (`04` Audit log).

GET /api/v1/admin/audit-log → entradas paginadas + filtradas + estado de la cadena
de custodia (íntegra o no). RBAC: admin_sistema. SOLO LECTURA — el registro es
append-only e inmutable (trigger de la base); acá no se muta nada.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict

from app.application.audit.service import AuditFiltros, listar_auditoria
from app.domain.auth.roles import Rol
from app.presentation.api.v1.auth.dependencies import require_roles

__all__ = ["create_audit_router"]


class AuditEventoOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    actor: str
    actor_nombre: str | None
    accion: str
    timestamp: str
    ip: str | None
    user_agent: str | None
    proposito: str | None


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AuditEventoOut]
    total: int
    limit: int
    offset: int
    cadena_valida: bool


def create_audit_router(session_factory=None) -> APIRouter:
    router = APIRouter(dependencies=[Depends(require_roles(Rol.ADMIN_SISTEMA))])

    @router.get("/audit-log", response_model=AuditLogResponse)
    async def audit_log(
        request: Request,
        actor: str | None = Query(default=None),
        accion: str | None = Query(default=None),
        desde: str | None = Query(default=None),
        hasta: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
    ) -> AuditLogResponse:
        factory = session_factory or getattr(request.app.state, "session_factory", None)
        if factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada (session_factory).",
            )
        filtros = AuditFiltros(actor=actor, accion=accion, desde=desde, hasta=hasta)
        async with factory() as db:
            pagina = await listar_auditoria(db, filtros, limit=limit, offset=offset)
        return AuditLogResponse(
            items=[
                AuditEventoOut(
                    id=e.id,
                    actor=e.actor,
                    actor_nombre=e.actor_nombre,
                    accion=e.accion,
                    timestamp=e.timestamp,
                    ip=e.ip,
                    user_agent=e.user_agent,
                    proposito=e.proposito,
                )
                for e in pagina.items
            ],
            total=pagina.total,
            limit=limit,
            offset=offset,
            cadena_valida=pagina.cadena_valida,
        )

    return router
