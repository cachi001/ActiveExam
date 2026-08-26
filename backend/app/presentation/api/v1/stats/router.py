"""Router de estadísticas institucionales (C-20 re-alcanzado, standalone).

GET /api/v1/stats/resumen     → sumario agregado (conteos + riesgo + desgloses).
GET /api/v1/stats/export.pdf  → el mismo sumario como PDF descargable.
GET /api/v1/stats/export.xlsx → el mismo sumario como Excel descargable.

Todos aceptan filtros por query param (materia_id / comision_id / examen_id /
desde / hasta), SIN scoping por pertenencia. RBAC: capacidad `ver_estadisticas`
(coordinador, admin_sistema) — vista institucional, deliberadamente SIN tutor
(c-79: los filtros son libres, no hay forma de acotar el docente a su propio
catálogo acá). Agregado SIN PII. L2.5: el "riesgo" prioriza la revisión
humana, NUNCA emite veredicto.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict

from app.application.stats.pdf_export import resumen_a_pdf
from app.application.stats.resumen_service import (
    FiltrosStats,
    ResumenStats,
    describir_alcance,
    obtener_resumen,
)
from app.application.stats.xlsx_export import resumen_a_xlsx
from app.presentation.api.v1.auth.dependencies import require_capability

__all__ = ["create_stats_router"]


class MateriaStatOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    materia_id: str
    nombre: str
    sesiones: int
    en_riesgo: int


class ComisionStatOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comision_id: str
    nombre: str
    sesiones: int
    en_riesgo: int


class ElegibilidadStatsOut(BaseModel):
    """Padrón de inscriptos y cuántos pueden / NO pueden rendir."""

    model_config = ConfigDict(extra="forbid")

    total_inscriptos: int
    con_consentimiento: int
    sin_consentimiento: int
    con_biometria: int
    sin_biometria: int
    pueden_rendir: int
    no_pueden_rendir: int


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
    por_comision: list[ComisionStatOut]
    top_eventos: list[EventoStatOut]
    por_dia: list[DiaStatOut]
    decisiones: dict[str, int]
    elegibilidad: ElegibilidadStatsOut


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
        por_comision=[
            ComisionStatOut(
                comision_id=c.comision_id,
                nombre=c.nombre,
                sesiones=c.sesiones,
                en_riesgo=c.en_riesgo,
            )
            for c in r.por_comision
        ],
        top_eventos=[EventoStatOut(tipo=e.tipo, cantidad=e.cantidad) for e in r.top_eventos],
        por_dia=[DiaStatOut(fecha=d.fecha, sesiones=d.sesiones) for d in r.por_dia],
        decisiones=r.decisiones,
        elegibilidad=ElegibilidadStatsOut(
            total_inscriptos=r.elegibilidad.total_inscriptos,
            con_consentimiento=r.elegibilidad.con_consentimiento,
            sin_consentimiento=r.elegibilidad.sin_consentimiento,
            con_biometria=r.elegibilidad.con_biometria,
            sin_biometria=r.elegibilidad.sin_biometria,
            pueden_rendir=r.elegibilidad.pueden_rendir,
            no_pueden_rendir=r.elegibilidad.no_pueden_rendir,
        ),
    )


def create_stats_router(session_factory=None) -> APIRouter:
    """Factory del router de stats (permite inyectar session_factory en tests)."""
    # Estadisticas institucionales: agregados SIN PII, pero SIN scoping por
    # pertenencia (los filtros materia_id/comision_id/examen_id son query
    # params libres). Deliberadamente SIN TUTOR (c-79): antes usaba
    # `gestionar_academico`, que el tutor tiene para SU catalogo, pero acá
    # le permitía pedir el resumen de cualquier comision ajena.
    router = APIRouter(
        dependencies=[Depends(require_capability("ver_estadisticas"))]
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
            alcance = await describir_alcance(db, filtros)
        return Response(
            content=resumen_a_pdf(r, filtros, alcance=alcance),
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
            alcance = await describir_alcance(db, filtros)
        return Response(
            content=resumen_a_xlsx(r, filtros, alcance=alcance),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="estadisticas.xlsx"'},
        )

    return router
