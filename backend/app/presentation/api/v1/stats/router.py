"""Router de estadísticas institucionales (C-20 re-alcanzado, standalone).

GET /api/v1/stats/resumen     → sumario agregado (conteos + riesgo + desgloses).
GET /api/v1/stats/export.csv  → el mismo sumario como CSV descargable.

Ambos aceptan filtros por query param (materia_id / comision_id / examen_id /
desde / hasta). RBAC: admin_sistema / coordinador (vista institucional). Agregado
SIN PII. L2.5: el "riesgo" prioriza la revisión humana, NUNCA emite veredicto.
"""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict

from app.application.stats.pdf_export import resumen_a_pdf
from app.application.stats.resumen_service import (
    FiltrosStats,
    ResumenStats,
    obtener_resumen,
)
from app.application.stats.xlsx_export import resumen_a_xlsx
from app.domain.auth.roles import Rol
from app.presentation.api.v1.auth.dependencies import require_roles

__all__ = ["create_stats_router"]


class MateriaStatOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    materia_id: str
    nombre: str
    sesiones: int
    en_riesgo: int


class EventoStatOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: str
    cantidad: int


class DiaStatOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fecha: str
    sesiones: int


class ResumenStatsResponse(BaseModel):
    """Sumario institucional agregado (sin PII)."""

    model_config = ConfigDict(extra="forbid")

    total_examenes: int
    total_materias: int
    total_comisiones: int
    total_sesiones: int
    sesiones_finalizadas: int
    sesiones_en_riesgo: int
    umbral_riesgo: int
    distribucion_scores: dict[str, int]
    por_materia: list[MateriaStatOut]
    top_eventos: list[EventoStatOut]
    por_dia: list[DiaStatOut]
    decisiones: dict[str, int]


def _to_response(r: ResumenStats) -> ResumenStatsResponse:
    return ResumenStatsResponse(
        total_examenes=r.total_examenes,
        total_materias=r.total_materias,
        total_comisiones=r.total_comisiones,
        total_sesiones=r.total_sesiones,
        sesiones_finalizadas=r.sesiones_finalizadas,
        sesiones_en_riesgo=r.sesiones_en_riesgo,
        umbral_riesgo=r.umbral_riesgo,
        distribucion_scores=r.distribucion_scores,
        por_materia=[
            MateriaStatOut(
                materia_id=m.materia_id,
                nombre=m.nombre,
                sesiones=m.sesiones,
                en_riesgo=m.en_riesgo,
            )
            for m in r.por_materia
        ],
        top_eventos=[EventoStatOut(tipo=e.tipo, cantidad=e.cantidad) for e in r.top_eventos],
        por_dia=[DiaStatOut(fecha=d.fecha, sesiones=d.sesiones) for d in r.por_dia],
        decisiones=r.decisiones,
    )


def _resumen_a_csv(r: ResumenStats) -> str:
    """Serializa el sumario a un CSV tidy (seccion, detalle, valor)."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["seccion", "detalle", "valor"])
    w.writerow(["resumen", "total_examenes", r.total_examenes])
    w.writerow(["resumen", "total_materias", r.total_materias])
    w.writerow(["resumen", "total_comisiones", r.total_comisiones])
    w.writerow(["resumen", "total_sesiones", r.total_sesiones])
    w.writerow(["resumen", "sesiones_finalizadas", r.sesiones_finalizadas])
    w.writerow(["resumen", "sesiones_en_riesgo", r.sesiones_en_riesgo])
    w.writerow(["resumen", "umbral_riesgo", r.umbral_riesgo])
    for rango, n in r.distribucion_scores.items():
        w.writerow(["distribucion_scores", rango, n])
    for m in r.por_materia:
        w.writerow(["por_materia", f"{m.nombre} (en riesgo {m.en_riesgo})", m.sesiones])
    for e in r.top_eventos:
        w.writerow(["top_eventos", e.tipo, e.cantidad])
    for d in r.por_dia:
        w.writerow(["por_dia", d.fecha, d.sesiones])
    for clave, n in r.decisiones.items():
        w.writerow(["decisiones", clave, n])
    return buf.getvalue()


def create_stats_router(session_factory=None) -> APIRouter:
    """Factory del router de stats (permite inyectar session_factory en tests)."""
    router = APIRouter(
        dependencies=[Depends(require_roles(Rol.ADMIN_SISTEMA, Rol.COORDINADOR))]
    )

    def _factory(request: Request):
        factory = session_factory or getattr(request.app.state, "session_factory", None)
        if factory is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Persistencia no inicializada (session_factory).",
            )
        return factory

    def _filtros(
        materia_id: str | None,
        comision_id: str | None,
        examen_id: str | None,
        desde: str | None,
        hasta: str | None,
    ) -> FiltrosStats:
        return FiltrosStats(
            materia_id=materia_id,
            comision_id=comision_id,
            examen_contenido_id=examen_id,
            desde=desde,
            hasta=hasta,
        )

    @router.get("/resumen", response_model=ResumenStatsResponse)
    async def resumen(
        request: Request,
        materia_id: str | None = Query(default=None),
        comision_id: str | None = Query(default=None),
        examen_id: str | None = Query(default=None),
        desde: str | None = Query(default=None),
        hasta: str | None = Query(default=None),
    ) -> ResumenStatsResponse:
        factory = _factory(request)
        filtros = _filtros(materia_id, comision_id, examen_id, desde, hasta)
        async with factory() as db:
            r = await obtener_resumen(db, filtros)
        return _to_response(r)

    @router.get("/export.csv")
    async def export_csv(
        request: Request,
        materia_id: str | None = Query(default=None),
        comision_id: str | None = Query(default=None),
        examen_id: str | None = Query(default=None),
        desde: str | None = Query(default=None),
        hasta: str | None = Query(default=None),
    ) -> Response:
        factory = _factory(request)
        filtros = _filtros(materia_id, comision_id, examen_id, desde, hasta)
        async with factory() as db:
            r = await obtener_resumen(db, filtros)
        return Response(
            content=_resumen_a_csv(r),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="estadisticas.csv"'},
        )

    @router.get("/export.pdf")
    async def export_pdf(
        request: Request,
        materia_id: str | None = Query(default=None),
        comision_id: str | None = Query(default=None),
        examen_id: str | None = Query(default=None),
        desde: str | None = Query(default=None),
        hasta: str | None = Query(default=None),
    ) -> Response:
        factory = _factory(request)
        filtros = _filtros(materia_id, comision_id, examen_id, desde, hasta)
        async with factory() as db:
            r = await obtener_resumen(db, filtros)
        return Response(
            content=resumen_a_pdf(r, filtros),
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="estadisticas.pdf"'},
        )

    @router.get("/export.xlsx")
    async def export_xlsx(
        request: Request,
        materia_id: str | None = Query(default=None),
        comision_id: str | None = Query(default=None),
        examen_id: str | None = Query(default=None),
        desde: str | None = Query(default=None),
        hasta: str | None = Query(default=None),
    ) -> Response:
        factory = _factory(request)
        filtros = _filtros(materia_id, comision_id, examen_id, desde, hasta)
        async with factory() as db:
            r = await obtener_resumen(db, filtros)
        return Response(
            content=resumen_a_xlsx(r, filtros),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="estadisticas.xlsx"'},
        )

    return router
