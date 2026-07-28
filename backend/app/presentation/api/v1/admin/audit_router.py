"""Router de auditoría: lectura del registro de actividad (`04` Audit log).

GET /api/v1/admin/audit-log     → entradas paginadas + filtradas + estado de cadena
GET /api/v1/admin/audit-modulos → módulos distintos con actividad (para el dropdown)

RBAC: admin_sistema. SOLO LECTURA — el registro es append-only e inmutable (trigger).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict

from app.application.audit.export import auditoria_a_pdf, auditoria_a_xlsx
from app.application.audit.service import AuditFiltros, listar_auditoria, listar_modulos
from app.domain.entities.actividad_auditoria import ActividadAuditoria
from app.domain.auth.roles import Rol
from app.presentation.api.v1.auth.dependencies import require_roles

__all__ = ["create_audit_router"]


class AuditEventoOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    actor: str
    actor_nombre: str | None
    accion: str
    tipo_accion: str | None
    modulo: str | None
    entidad: str | None
    entidad_id: str | None
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
        modulo: str | None = Query(default=None),
        entidad: str | None = Query(default=None),
        tipo_accion: str | None = Query(default=None),
        accion: str | None = Query(default=None, description="Búsqueda libre en el detalle"),
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
        filtros = AuditFiltros(
            actor=actor,
            modulo=modulo,
            entidad=entidad,
            tipo_accion=tipo_accion,
            accion=accion,
            desde=desde,
            hasta=hasta,
        )
        async with factory() as db:
            pagina = await listar_auditoria(db, filtros, limit=limit, offset=offset)
        def _to_out(e: ActividadAuditoria) -> AuditEventoOut:
            return AuditEventoOut(
                id=e.id,
                actor=e.actor,
                actor_nombre=e.actor_nombre,
                accion=e.accion,
                tipo_accion=e.tipo_accion,
                modulo=e.modulo,
                entidad=e.entidad,
                entidad_id=e.entidad_id,
                timestamp=e.timestamp,
                ip=e.ip,
                user_agent=e.user_agent,
                proposito=e.proposito,
            )

        return AuditLogResponse(
            items=[_to_out(e) for e in pagina.items],
            total=pagina.total,
            limit=limit,
            offset=offset,
            cadena_valida=pagina.cadena_valida,
        )

    # Tope de filas por export. Un pedido sin filtros sobre un registro de años
    # no puede tumbar el proceso armando el archivo en memoria; quien necesite
    # más, acota el período (que es como se audita de todos modos).
    _MAX_EXPORT = 5000

    @router.get("/audit-modulos", response_model=list[str])
    async def audit_modulos(request: Request) -> list[str]:
        """Módulos distintos que tienen al menos una entrada auditada."""
        factory = session_factory or getattr(request.app.state, "session_factory", None)
        if factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada (session_factory).",
            )
        async with factory() as db:
            return await listar_modulos(db)

    async def _entradas_para_export(
        request: Request,
        actor: str | None,
        modulo: str | None,
        accion: str | None,
        desde: str | None,
        hasta: str | None,
    ):
        factory = session_factory or getattr(request.app.state, "session_factory", None)
        if factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada (session_factory).",
            )
        # El export respeta LOS MISMOS filtros que el listado: si se filtró por
        # módulo en pantalla, el archivo NO puede traer todo el registro.
        filtros = AuditFiltros(
            actor=actor, modulo=modulo, accion=accion, desde=desde, hasta=hasta
        )
        async with factory() as db:
            pagina = await listar_auditoria(db, filtros, limit=_MAX_EXPORT, offset=0)
        return pagina.items

    @router.get("/audit-log/export.xlsx", summary="Exportar auditoría a Excel")
    async def exportar_xlsx(
        request: Request,
        actor: str | None = Query(default=None),
        modulo: str | None = Query(default=None),
        accion: str | None = Query(default=None),
        desde: str | None = Query(default=None),
        hasta: str | None = Query(default=None),
    ) -> Response:
        entradas = await _entradas_para_export(
            request, actor, modulo, accion, desde, hasta
        )
        return Response(
            content=auditoria_a_xlsx(
                entradas,
                actor=actor,
                accion=accion,
                modulo=modulo,
                desde=desde,
                hasta=hasta,
            ),
            media_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            headers={"Content-Disposition": 'attachment; filename="auditoria.xlsx"'},
        )

    @router.get("/audit-log/export.pdf", summary="Exportar auditoría a PDF")
    async def exportar_pdf(
        request: Request,
        actor: str | None = Query(default=None),
        modulo: str | None = Query(default=None),
        accion: str | None = Query(default=None),
        desde: str | None = Query(default=None),
        hasta: str | None = Query(default=None),
    ) -> Response:
        entradas = await _entradas_para_export(
            request, actor, modulo, accion, desde, hasta
        )
        return Response(
            content=auditoria_a_pdf(
                entradas,
                actor=actor,
                accion=accion,
                modulo=modulo,
                desde=desde,
                hasta=hasta,
            ),
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="auditoria.pdf"'},
        )

    return router
